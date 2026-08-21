from __future__ import annotations

import threading

import pytest

from meeting_minutes_agent.client.budgets import BudgetExceeded, BudgetLimits, CallBudget


class TestBudgetLimits:
    def test_rejects_non_positive_max_calls(self):
        with pytest.raises(ValueError, match="max_calls"):
            BudgetLimits(max_calls=0, max_audio_seconds=10.0).validate()

    def test_rejects_bool_max_calls(self):
        with pytest.raises(ValueError, match="max_calls"):
            BudgetLimits(max_calls=True, max_audio_seconds=10.0).validate()

    def test_rejects_non_finite_audio_seconds(self):
        with pytest.raises(ValueError, match="max_audio_seconds"):
            BudgetLimits(max_calls=1, max_audio_seconds=float("inf")).validate()


class TestCallBudgetSingleThread:
    def test_reserve_within_caps_succeeds_and_accumulates(self):
        budget = CallBudget(BudgetLimits(max_calls=3, max_audio_seconds=10.0))
        budget.reserve(2.0)
        budget.reserve(3.0)
        assert budget.totals == {
            "calls_used": 2,
            "audio_seconds_used": 5.0,
            "max_calls": 3,
            "max_audio_seconds": 10.0,
        }

    def test_call_cap_refuses_the_next_call(self):
        budget = CallBudget(BudgetLimits(max_calls=1, max_audio_seconds=100.0))
        budget.reserve(1.0)
        with pytest.raises(BudgetExceeded, match="call budget exhausted"):
            budget.reserve(1.0)
        # refusal never mutates state
        assert budget.totals["calls_used"] == 1

    def test_audio_seconds_cap_refuses_a_call_that_would_cross_it(self):
        budget = CallBudget(BudgetLimits(max_calls=10, max_audio_seconds=5.0))
        budget.reserve(4.0)
        with pytest.raises(BudgetExceeded, match="audio budget exhausted"):
            budget.reserve(1.5)
        assert budget.totals["audio_seconds_used"] == 4.0
        assert budget.totals["calls_used"] == 1

    def test_exact_boundary_is_allowed(self):
        budget = CallBudget(BudgetLimits(max_calls=1, max_audio_seconds=5.0))
        budget.reserve(5.0)  # exactly at the cap, not over
        assert budget.totals["audio_seconds_used"] == 5.0

    def test_float_residue_at_boundary_is_allowed_and_clamped(self):
        budget = CallBudget(BudgetLimits(max_calls=2, max_audio_seconds=0.3))
        budget.reserve(0.1)
        budget.reserve(0.2)
        assert budget.totals["audio_seconds_used"] == 0.3
        assert budget.totals["calls_used"] == 2

    def test_overrun_beyond_float_tolerance_is_refused(self):
        budget = CallBudget(BudgetLimits(max_calls=2, max_audio_seconds=0.3))
        budget.reserve(0.1)
        with pytest.raises(BudgetExceeded, match="audio budget exhausted"):
            budget.reserve(0.20000001)
        assert budget.totals["audio_seconds_used"] == 0.1
        assert budget.totals["calls_used"] == 1

    def test_rejects_negative_audio_seconds(self):
        budget = CallBudget(BudgetLimits(max_calls=1, max_audio_seconds=5.0))
        with pytest.raises(ValueError, match="non-negative"):
            budget.reserve(-1.0)

    def test_rejects_non_finite_audio_seconds(self):
        budget = CallBudget(BudgetLimits(max_calls=1, max_audio_seconds=5.0))
        with pytest.raises(ValueError, match="finite"):
            budget.reserve(float("nan"))


class TestCallBudgetConcurrency:
    def test_exactly_cap_threads_succeed_under_a_hammer(self):
        # Thread-safety hammer: N threads racing budget.reserve() against a
        # small cap -- exactly `max_calls` must succeed, the rest must be
        # refused, and the total mutation must never overshoot (the SAEA
        # metering lesson this module's docstring cites: one lock across
        # check-and-record).
        max_calls = 5
        thread_count = 50
        budget = CallBudget(BudgetLimits(max_calls=max_calls, max_audio_seconds=1_000_000.0))
        succeeded = []
        failed = []
        results_lock = threading.Lock()

        def worker() -> None:
            try:
                budget.reserve(1.0)
            except BudgetExceeded:
                with results_lock:
                    failed.append(1)
            else:
                with results_lock:
                    succeeded.append(1)

        threads = [threading.Thread(target=worker) for _ in range(thread_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(succeeded) == max_calls
        assert len(failed) == thread_count - max_calls
        assert budget.totals["calls_used"] == max_calls
        assert budget.totals["audio_seconds_used"] == float(max_calls)
