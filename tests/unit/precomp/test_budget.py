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
    wave_usage_from_receipts,
)
from meeting_minutes_agent.precomp.receipts import build_meeting_receipt


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


# ---------------------------------------------------------------------------
# wave_usage_from_receipts / PrecompBudget.precharge / check_all
# ---------------------------------------------------------------------------


def _receipt(
    meeting_id: str = "MTG1",
    *,
    ok: bool = True,
    diar_gpu_seconds: float = 0.0,
    cutting_wall_seconds: float = 0.0,
    encode_calls: int = 0,
    encode_gpu_seconds_per_call: float = 0.0,
) -> dict:
    """A fixture receipt shaped exactly like
    :func:`~meeting_minutes_agent.precomp.receipts.build_meeting_receipt`
    produces, with the four axes :func:`wave_usage_from_receipts` reads
    parameterized directly."""

    encode_outcomes = [{"gpu_seconds_estimate": encode_gpu_seconds_per_call} for _ in range(encode_calls)]
    return build_meeting_receipt(
        wave=1,
        meeting_id=meeting_id,
        ok=ok,
        error=None if ok else "boom",
        diar={"contact": None, "n_turns": 3, "wall_seconds": 1.0, "gpu_seconds_estimate": diar_gpu_seconds},
        slice_plans={"tool": {"n_slices": 2}, "oracle": {"n_slices": 2}},
        cutting={
            "tool": {"n_entries": 2}, "oracle": {"n_entries": 2},
            "wall_seconds": cutting_wall_seconds, "workers": 8,
        },
        encode_warm={"tool": encode_outcomes, "oracle": [], "wall_seconds": 0.2, "n_calls": encode_calls},
        metrics={},
        budget_after={},
        recorded_utc="2026-08-19T00:00:00+00:00",
    )


class TestWaveUsageFromReceipts:
    def test_sums_across_multiple_receipts(self):
        receipts = [
            _receipt("MTG1", diar_gpu_seconds=10.0, cutting_wall_seconds=1.0, encode_calls=2, encode_gpu_seconds_per_call=3.0),
            _receipt("MTG2", diar_gpu_seconds=5.0, cutting_wall_seconds=2.0, encode_calls=1, encode_gpu_seconds_per_call=4.0),
        ]
        used = wave_usage_from_receipts(receipts)
        assert used["diar_gpu_seconds_used"] == 15.0
        assert used["cutting_wall_seconds_used"] == 3.0
        assert used["encode_calls_used"] == 3
        assert used["encode_gpu_seconds_used"] == 10.0  # 2*3.0 + 1*4.0

    def test_counts_a_failed_receipts_completed_stages(self):
        # A meeting whose pipeline failed partway (ok=False) still spent
        # real diar/cutting resources for the stages that ran before the
        # failure -- never filtered out.
        receipt = _receipt("MTG1", ok=False, diar_gpu_seconds=7.0, cutting_wall_seconds=0.5, encode_calls=0)
        used = wave_usage_from_receipts([receipt])
        assert used["diar_gpu_seconds_used"] == 7.0
        assert used["cutting_wall_seconds_used"] == 0.5
        assert used["encode_calls_used"] == 0

    def test_missing_fields_default_to_zero(self):
        used = wave_usage_from_receipts([{"schema_version": "1.0.0", "ok": True}])
        assert used == {
            "diar_gpu_seconds_used": 0.0,
            "cutting_wall_seconds_used": 0.0,
            "encode_gpu_seconds_used": 0.0,
            "encode_calls_used": 0,
        }

    def test_empty_receipt_list_is_all_zero(self):
        assert wave_usage_from_receipts([]) == {
            "diar_gpu_seconds_used": 0.0,
            "cutting_wall_seconds_used": 0.0,
            "encode_gpu_seconds_used": 0.0,
            "encode_calls_used": 0,
        }

    def test_non_mapping_entries_are_skipped(self):
        used = wave_usage_from_receipts([None, "not-a-dict", 42, _receipt("MTG1", diar_gpu_seconds=1.0)])
        assert used["diar_gpu_seconds_used"] == 1.0


class TestPrecompBudgetPrecharge:
    def test_precharge_is_additive_into_a_fresh_budget(self):
        budget = PrecompBudget(ceilings_for_wave(1))
        receipts = [_receipt("MTG1", diar_gpu_seconds=100.0, cutting_wall_seconds=10.0, encode_calls=5, encode_gpu_seconds_per_call=2.0)]
        budget.precharge(receipts)
        assert budget.diar_gpu_seconds_used == 100.0
        assert budget.cutting_wall_seconds_used == 10.0
        assert budget.encode_calls_used == 5
        assert budget.encode_gpu_seconds_used == 10.0

    def test_precharge_adds_on_top_of_existing_usage_rather_than_replacing(self):
        budget = PrecompBudget(ceilings_for_wave(1))
        budget.record_diar(3.0)
        budget.precharge([_receipt("MTG1", diar_gpu_seconds=1.0)])
        assert budget.diar_gpu_seconds_used == 4.0

    def test_precharge_from_an_empty_receipt_set_leaves_budget_untouched(self):
        budget = PrecompBudget(ceilings_for_wave(1))
        budget.precharge([])
        d = budget.to_dict()
        assert d["diar_gpu_seconds_used"] == 0.0
        assert d["encode_calls_used"] == 0

    def test_a_would_exceed_meeting_refuses_after_precharge(self):
        # A fixture receipt set that, cumulatively, already exhausts the
        # wave's encode call-count ceiling.
        ceilings = WaveCeilings(wave=1, max_diar_gpu_hours=1.0, max_encode_gpu_hours=1.0, max_cutting_wall_hours=1.0, max_encode_calls=10)
        budget = PrecompBudget(ceilings)
        receipts = [_receipt(f"MTG{i}", encode_calls=5) for i in range(2)]  # 10 calls total == ceiling
        budget.precharge(receipts)
        assert budget.encode_calls_used == 10
        with pytest.raises(PrecompBudgetExceeded):
            budget.check_before_encode()  # the next meeting refuses before it starts

    def test_check_all_passes_when_precharge_stays_under_every_ceiling(self):
        budget = PrecompBudget(ceilings_for_wave(1))
        budget.precharge(
            [_receipt("MTG1", diar_gpu_seconds=1.0, cutting_wall_seconds=1.0, encode_calls=1, encode_gpu_seconds_per_call=1.0)]
        )
        budget.check_all()  # must not raise

    def test_check_all_refuses_when_precharge_alone_already_reached_the_diar_ceiling(self):
        ceilings = WaveCeilings(wave=1, max_diar_gpu_hours=0.5, max_encode_gpu_hours=2.0, max_cutting_wall_hours=2.0, max_encode_calls=900)
        budget = PrecompBudget(ceilings)
        receipts = [_receipt("MTG1", diar_gpu_seconds=1800.0)]  # 0.5h == 1800s, exactly the ceiling
        budget.precharge(receipts)
        with pytest.raises(PrecompBudgetExceeded):
            budget.check_all()

    def test_check_all_catches_a_non_diar_axis_breach_too(self):
        ceilings = WaveCeilings(wave=1, max_diar_gpu_hours=1.0, max_encode_gpu_hours=1.0, max_cutting_wall_hours=1.0, max_encode_calls=3)
        budget = PrecompBudget(ceilings)
        receipts = [_receipt("MTG1", encode_calls=3)]  # exactly at the call-count ceiling; diar/cutting untouched
        budget.precharge(receipts)
        with pytest.raises(PrecompBudgetExceeded):
            budget.check_all()
