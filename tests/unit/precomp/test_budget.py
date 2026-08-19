"""Tests for :mod:`meeting_minutes_agent.precomp.budget`: the registered
per-wave ceilings and the fail-closed, post-hoc budget guard."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.precomp.budget import (
    WAVE_1_CEILINGS,
    WAVE_2_CEILINGS,
    PrecompBudget,
    PrecompBudgetExceeded,
    WaveCeilings,
    ceilings_for_wave,
)


# ---------------------------------------------------------------------------
# registered ceilings (docs/readiness/2026-08-19-precomp-preregistration.md SS4)
# ---------------------------------------------------------------------------


class TestCeilingsForWave:
    def test_wave_1_matches_the_registration(self):
        c = ceilings_for_wave(1)
        assert c is WAVE_1_CEILINGS
        assert c.wave == 1
        assert c.max_diar_gpu_hours == 0.5
        assert c.max_encode_gpu_hours == 2.0
        assert c.max_cutting_wall_hours == 2.0
        assert c.max_encode_calls == 900

    def test_wave_2_matches_the_registration(self):
        c = ceilings_for_wave(2)
        assert c is WAVE_2_CEILINGS
        assert c.wave == 2
        assert c.max_diar_gpu_hours == 2.0
        assert c.max_encode_gpu_hours == 8.0
        assert c.max_cutting_wall_hours is None  # unregistered for wave-2
        assert c.max_encode_calls == 4500

    def test_unknown_wave_raises_key_error(self):
        with pytest.raises(KeyError):
            ceilings_for_wave(3)

    def test_to_dict_round_trips_every_field(self):
        d = WAVE_1_CEILINGS.to_dict()
        assert d == {
            "wave": 1,
            "max_diar_gpu_hours": 0.5,
            "max_encode_gpu_hours": 2.0,
            "max_cutting_wall_hours": 2.0,
            "max_encode_calls": 900,
        }


# ---------------------------------------------------------------------------
# PrecompBudget: diar
# ---------------------------------------------------------------------------


class TestDiarBudget:
    def test_check_before_diar_passes_when_under_ceiling(self):
        budget = PrecompBudget(WaveCeilings(wave=1, max_diar_gpu_hours=1.0, max_encode_gpu_hours=1.0, max_cutting_wall_hours=1.0, max_encode_calls=10))
        budget.check_before_diar()  # must not raise

    def test_check_before_diar_trips_once_ceiling_reached(self):
        budget = PrecompBudget(WaveCeilings(wave=1, max_diar_gpu_hours=0.0, max_encode_gpu_hours=1.0, max_cutting_wall_hours=1.0, max_encode_calls=10))
        with pytest.raises(PrecompBudgetExceeded):
            budget.check_before_diar()

    def test_record_diar_accumulates_and_never_goes_negative(self):
        budget = PrecompBudget(ceilings_for_wave(1))
        budget.record_diar(10.0)
        budget.record_diar(-100.0)  # a caller passing a negative sample never subtracts
        assert budget.diar_gpu_seconds_used == 10.0

    def test_check_before_diar_trips_after_enough_recorded_usage(self):
        budget = PrecompBudget(WaveCeilings(wave=1, max_diar_gpu_hours=1.0 / 3600.0, max_encode_gpu_hours=1.0, max_cutting_wall_hours=1.0, max_encode_calls=10))
        budget.check_before_diar()  # 0 used < 1s ceiling: passes
        budget.record_diar(1.0)
        with pytest.raises(PrecompBudgetExceeded):
            budget.check_before_diar()


# ---------------------------------------------------------------------------
# PrecompBudget: CPU cutting
# ---------------------------------------------------------------------------


class TestCuttingBudget:
    def test_wave_2_has_no_cutting_ceiling_and_never_trips(self):
        budget = PrecompBudget(WAVE_2_CEILINGS)
        budget.record_cutting(10_000_000.0)  # absurdly large
        budget.check_before_cutting()  # must not raise -- unregistered ceiling

    def test_wave_1_cutting_ceiling_trips(self):
        budget = PrecompBudget(WaveCeilings(wave=1, max_diar_gpu_hours=1.0, max_encode_gpu_hours=1.0, max_cutting_wall_hours=0.0, max_encode_calls=10))
        with pytest.raises(PrecompBudgetExceeded):
            budget.check_before_cutting()


# ---------------------------------------------------------------------------
# PrecompBudget: encode-warm (both GPU-hours and call count)
# ---------------------------------------------------------------------------


class TestEncodeBudget:
    def test_trips_on_gpu_hour_ceiling(self):
        budget = PrecompBudget(WaveCeilings(wave=1, max_diar_gpu_hours=1.0, max_encode_gpu_hours=0.0, max_cutting_wall_hours=1.0, max_encode_calls=10))
        with pytest.raises(PrecompBudgetExceeded):
            budget.check_before_encode()

    def test_trips_on_call_count_ceiling(self):
        budget = PrecompBudget(WaveCeilings(wave=1, max_diar_gpu_hours=1.0, max_encode_gpu_hours=1.0, max_cutting_wall_hours=1.0, max_encode_calls=2))
        budget.record_encode(gpu_seconds=0.0, n_calls=2)
        with pytest.raises(PrecompBudgetExceeded):
            budget.check_before_encode()

    def test_passes_below_both_ceilings(self):
        budget = PrecompBudget(ceilings_for_wave(2))
        budget.record_encode(gpu_seconds=1.0, n_calls=1)
        budget.check_before_encode()  # must not raise

    def test_record_encode_accumulates_calls_and_seconds(self):
        budget = PrecompBudget(ceilings_for_wave(2))
        budget.record_encode(gpu_seconds=1.5, n_calls=1)
        budget.record_encode(gpu_seconds=2.5, n_calls=1)
        assert budget.encode_gpu_seconds_used == 4.0
        assert budget.encode_calls_used == 2


# ---------------------------------------------------------------------------
# to_dict reporting
# ---------------------------------------------------------------------------


class TestBudgetToDict:
    def test_carries_ceilings_and_every_usage_field(self):
        budget = PrecompBudget(ceilings_for_wave(1))
        budget.record_diar(1.0)
        budget.record_cutting(2.0)
        budget.record_encode(gpu_seconds=3.0, n_calls=4)
        d = budget.to_dict()
        assert d["ceilings"] == WAVE_1_CEILINGS.to_dict()
        assert d["diar_gpu_seconds_used"] == 1.0
        assert d["cutting_wall_seconds_used"] == 2.0
        assert d["encode_gpu_seconds_used"] == 3.0
        assert d["encode_calls_used"] == 4
