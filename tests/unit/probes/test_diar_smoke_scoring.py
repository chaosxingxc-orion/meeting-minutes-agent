"""Tests for :mod:`meeting_minutes_agent.probes.diar_smoke_scoring`:
turn-boundary displacement, the packing-change metric (bound to the REAL
:func:`~meeting_minutes_agent.chunking.slicer.build_turn_aware_slice_plan`),
per-meeting metric wiring, pooling, and the five-verdict mechanical
evaluator -- including fixtures driving all five outcomes and the
parity-fail path."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.chunking.slicer import TurnSpan
from meeting_minutes_agent.probes.diar_smoke_scoring import (
    CAVEAT_MAX_DER,
    CONVENTION_NO_COLLAR_WITH_OVERLAP,
    DiarSmokeReadOutputExistsError,
    PARITY_ABS_THRESHOLD_DER,
    STATUS_FALLBACK_NEEDED,
    STATUS_TOOL_LOCKED_A,
    STATUS_TOOL_LOCKED_B,
    STATUS_TOOL_USABLE_WITH_CAVEAT,
    TOOL_LOCKED_MAX_DER,
    assert_one_shot_output_dir,
    boundary_displacements,
    displacement_summary,
    evaluate_diar_smoke_verdict,
    packing_change_for_meeting,
    pool_meeting_metrics_by_convention,
    score_meeting,
)


def _turn(speaker: str, start: float, end: float) -> TurnSpan:
    return TurnSpan(start=start, end=end, speaker=speaker)


# ---------------------------------------------------------------------------
# boundary displacement
# ---------------------------------------------------------------------------


class TestBoundaryDisplacements:
    def test_hand_computed_displacements(self):
        reference = (_turn("A", 0.0, 10.0), _turn("B", 10.0, 25.0))
        hypothesis = (_turn("A", 0.0, 12.0), _turn("B", 12.0, 25.0))
        # ref boundaries {0, 10, 25}; hyp boundaries {0, 12, 25}.
        # nearest-hyp distances: 0->0, 10->2 (|10-12|), 25->0.
        displacements = boundary_displacements(reference, hypothesis)
        assert sorted(displacements) == [0.0, 0.0, 2.0]

    def test_empty_hypothesis_yields_empty_distribution(self):
        reference = (_turn("A", 0.0, 10.0),)
        assert boundary_displacements(reference, ()) == ()

    def test_identical_turns_yield_all_zero_displacement(self):
        # boundaries {0, 10, 20} -- the shared A/B boundary at 10 counts
        # once (a set of distinct time points, not one per turn edge).
        turns = (_turn("A", 0.0, 10.0), _turn("B", 10.0, 20.0))
        assert boundary_displacements(turns, turns) == (0.0, 0.0, 0.0)


class TestDisplacementSummary:
    def test_empty_summary(self):
        assert displacement_summary(()) == {"n": 0, "mean": None, "median": None, "max": None}

    def test_hand_computed_summary(self):
        summary = displacement_summary((0.0, 2.0, 0.0))
        assert summary["n"] == 3
        assert summary["mean"] == pytest.approx(2.0 / 3.0)
        assert summary["median"] == pytest.approx(0.0)
        assert summary["max"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# packing-change metric -- bound to the real slicer
# ---------------------------------------------------------------------------


class TestPackingChangeForMeeting:
    def test_identical_turns_never_change_the_packing(self):
        turns = (_turn("A", 0.0, 90.0), _turn("B", 90.0, 180.0))
        result = packing_change_for_meeting("M1", turns, turns, total_duration_s=180.0)
        assert result.n_slices_oracle == result.n_slices_tool
        assert result.n_changed == 0
        assert result.fraction_changed == pytest.approx(0.0)

    def test_a_boundary_shift_changes_every_slice_bound(self):
        # Same slice COUNT (2 vs 2), but every bound differs by the shift.
        oracle_turns = (_turn("A", 0.0, 90.0), _turn("B", 90.0, 180.0))
        tool_turns = (_turn("A", 0.0, 95.0), _turn("B", 95.0, 180.0))
        result = packing_change_for_meeting("M1", oracle_turns, tool_turns, total_duration_s=180.0)
        assert result.n_slices_oracle == 2
        assert result.n_slices_tool == 2
        assert result.n_changed == 2
        assert result.fraction_changed == pytest.approx(1.0)
        assert result.changed_slice_indices == (0, 1)

    def test_a_missed_second_speaker_changes_the_slice_count(self):
        # oracle: two well-separated turns -> 2 slices; tool: only the
        # first turn survives -> 1 slice. Every compared index (including
        # the one only the oracle plan has) counts as changed.
        oracle_turns = (_turn("A", 0.0, 50.0), _turn("B", 160.0, 210.0))
        tool_turns = (_turn("A", 0.0, 50.0),)
        result = packing_change_for_meeting("M1", oracle_turns, tool_turns, total_duration_s=210.0)
        assert result.n_slices_oracle == 2
        assert result.n_slices_tool == 1
        assert result.n_compared == 2
        assert result.n_changed == 2
        assert result.fraction_changed == pytest.approx(1.0)

    def test_uses_boundary_provenance_admissible_to_the_real_gate(self):
        # No exception means the oracle-tagged plan went through
        # allow_oracle_turns=True and the tool-tagged plan needed no such
        # admission -- the actual admissibility gate the slicer enforces
        # (meeting_minutes_agent.chunking.leakage) is exercised here for
        # real, not mocked.
        turns = (_turn("A", 0.0, 90.0),)
        result = packing_change_for_meeting("M1", turns, turns, total_duration_s=90.0)
        assert result.n_slices_oracle == 1


# ---------------------------------------------------------------------------
# score_meeting wiring
# ---------------------------------------------------------------------------


class TestScoreMeeting:
    def test_wires_der_jer_speaker_count_displacement_and_packing(self):
        reference = (_turn("A", 0.0, 10.0), _turn("B", 10.0, 20.0))
        hypothesis = (_turn("A", 0.0, 9.0), _turn("B", 9.0, 20.0))  # the shift fixture: DER=0.05

        metrics = score_meeting("M1", reference, hypothesis, total_duration_s=20.0)

        assert metrics.meeting_id == "M1"
        assert metrics.n_reference_speakers == 2
        assert metrics.n_hypothesis_speakers == 2
        assert metrics.speaker_count_correct is True
        assert metrics.der_by_convention[CONVENTION_NO_COLLAR_WITH_OVERLAP].der == pytest.approx(1.0 / 20.0)
        assert metrics.boundary_displacement_seconds == (0.0, 1.0, 0.0)
        assert metrics.packing.meeting_id == "M1"
        payload = metrics.to_dict()
        assert payload["speaker_count_correct"] is True
        assert "der_by_convention" in payload and "jer_by_convention" in payload


# ---------------------------------------------------------------------------
# pooling
# ---------------------------------------------------------------------------


class TestPoolMeetingMetricsByConvention:
    def test_pools_across_meetings(self):
        m1 = score_meeting("M1", (_turn("A", 0.0, 10.0),), (_turn("A", 0.0, 10.0),))
        m2 = score_meeting(
            "M2",
            (_turn("A", 0.0, 10.0), _turn("B", 10.0, 20.0)),
            (_turn("A", 0.0, 10.0),),
        )
        pooled = pool_meeting_metrics_by_convention([m1, m2], CONVENTION_NO_COLLAR_WITH_OVERLAP)
        # m1: perfect (0 error / 10 total); m2: 10s missed / 20 total.
        assert pooled.total_reference_seconds == pytest.approx(30.0)
        assert pooled.missed_seconds == pytest.approx(10.0)
        assert pooled.der == pytest.approx(10.0 / 30.0)


# ---------------------------------------------------------------------------
# the five mechanical verdicts
# ---------------------------------------------------------------------------


class TestEvaluateDiarSmokeVerdict:
    def test_tool_locked_b(self):
        # parity: |21-20|=1 <= 2 -> passes. B=21 <= 22 -> TOOL-LOCKED(B).
        verdict = evaluate_diar_smoke_verdict(der_a=20.0, der_b=21.0)
        assert verdict.status == STATUS_TOOL_LOCKED_B
        assert verdict.clauses["parity"].fires is True
        assert verdict.clauses["tool_locked_b"].fires is True
        assert verdict.clauses["tool_locked_b"].margin == pytest.approx(1.0)

    def test_tool_locked_a_via_parity_failure(self):
        # parity: |25-15|=10 > 2 -> fails. A=15 <= 22 -> TOOL-LOCKED(A).
        verdict = evaluate_diar_smoke_verdict(der_a=15.0, der_b=25.0)
        assert verdict.status == STATUS_TOOL_LOCKED_A
        assert verdict.clauses["parity"].fires is False
        assert verdict.clauses["tool_locked_a"].fires is True

    def test_parity_fail_path_explicitly(self):
        # Dedicated parity-fail-path fixture: parity fails even though B's
        # OWN DER would satisfy the TOOL-LOCKED(B) DER threshold -- parity
        # failing must still block TOOL-LOCKED(B).
        verdict = evaluate_diar_smoke_verdict(der_a=10.0, der_b=20.0)
        gap = abs(20.0 - 10.0)
        assert gap > PARITY_ABS_THRESHOLD_DER
        assert verdict.clauses["parity"].fires is False
        assert verdict.clauses["tool_locked_b"].fires is False
        assert verdict.status == STATUS_TOOL_LOCKED_A  # A alone still qualifies

    def test_tool_usable_with_caveat(self):
        # parity fails (gap 3 > 2); A=25 > 22 so neither lock fires;
        # best arm (A, 25.0) is in (22, 30] -> caveat.
        verdict = evaluate_diar_smoke_verdict(der_a=25.0, der_b=28.0)
        assert verdict.status == STATUS_TOOL_USABLE_WITH_CAVEAT
        assert verdict.best_arm == "A"
        assert verdict.best_arm_der == pytest.approx(25.0)
        assert verdict.clauses["tool_usable_with_caveat"].fires is True

    def test_fallback_needed_when_best_der_exceeds_caveat_ceiling(self):
        verdict = evaluate_diar_smoke_verdict(der_a=35.0, der_b=40.0)
        assert verdict.status == STATUS_FALLBACK_NEEDED
        assert verdict.best_arm_der == pytest.approx(35.0)
        assert verdict.clauses["fallback_needed"].fires is True

    def test_fallback_needed_when_both_arms_fail_to_load(self):
        verdict = evaluate_diar_smoke_verdict(der_a=None, der_b=None, a_load_failed=True, b_load_failed=True)
        assert verdict.status == STATUS_FALLBACK_NEEDED
        assert verdict.best_arm is None
        assert verdict.clauses["parity"].fires is False
        assert verdict.in_domain_caveat  # carried in every outcome

    def test_fallback_needed_when_one_arm_fails_and_the_other_exceeds_caveat(self):
        verdict = evaluate_diar_smoke_verdict(der_a=None, der_b=40.0, a_load_failed=True)
        assert verdict.status == STATUS_FALLBACK_NEEDED
        assert verdict.best_arm == "B"

    def test_boundary_values_at_exactly_the_thresholds(self):
        # DER(B) exactly at the TOOL_LOCKED_MAX_DER boundary still locks.
        verdict = evaluate_diar_smoke_verdict(der_a=TOOL_LOCKED_MAX_DER, der_b=TOOL_LOCKED_MAX_DER)
        assert verdict.status == STATUS_TOOL_LOCKED_B
        assert verdict.clauses["tool_locked_b"].margin == pytest.approx(0.0)

    def test_caveat_upper_boundary_is_inclusive(self):
        verdict = evaluate_diar_smoke_verdict(der_a=CAVEAT_MAX_DER, der_b=CAVEAT_MAX_DER + 20.0)
        assert verdict.status == STATUS_TOOL_USABLE_WITH_CAVEAT

    def test_in_domain_caveat_is_present_in_every_outcome(self):
        outcomes = [
            evaluate_diar_smoke_verdict(der_a=20.0, der_b=21.0),
            evaluate_diar_smoke_verdict(der_a=15.0, der_b=25.0),
            evaluate_diar_smoke_verdict(der_a=25.0, der_b=28.0),
            evaluate_diar_smoke_verdict(der_a=35.0, der_b=40.0),
            evaluate_diar_smoke_verdict(der_a=None, der_b=None, a_load_failed=True, b_load_failed=True),
        ]
        for verdict in outcomes:
            assert verdict.in_domain_caveat
            payload = verdict.to_dict()
            assert payload["in_domain_caveat"] == verdict.in_domain_caveat
            assert set(payload["clauses"]) == {
                "parity", "tool_locked_b", "tool_locked_a", "tool_usable_with_caveat", "fallback_needed",
            }


# ---------------------------------------------------------------------------
# one-shot read output-dir guard
# ---------------------------------------------------------------------------


class TestAssertOneShotOutputDir:
    def test_missing_dir_passes(self, tmp_path):
        assert_one_shot_output_dir(tmp_path / "nope")

    def test_empty_dir_passes(self, tmp_path):
        assert_one_shot_output_dir(tmp_path)

    def test_existing_verdict_raises_without_force(self, tmp_path):
        (tmp_path / "verdict.json").write_text("{}", encoding="utf-8")
        with pytest.raises(DiarSmokeReadOutputExistsError):
            assert_one_shot_output_dir(tmp_path)

    def test_force_bypasses_the_guard(self, tmp_path):
        (tmp_path / "verdict.json").write_text("{}", encoding="utf-8")
        assert_one_shot_output_dir(tmp_path, force=True)
