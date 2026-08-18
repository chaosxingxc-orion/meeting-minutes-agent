"""Tests for :mod:`meeting_minutes_agent.probes.pprompt_scoring`: grammar
compliance, per-slice scoring, per-cell aggregation, the mechanical winner
rule (prereg SS4, every branch), the corrupt-context verdict rule (all three
outcomes), and the one-shot output-dir guard."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.metrics.timestamps import PerSpeakerSegment
from meeting_minutes_agent.probes.pprompt import ARM_X1, ARM_X2, GRID_CELLS, REFERENCE_CELL
from meeting_minutes_agent.probes.pprompt_scoring import (
    GRAMMAR_BLOCKED,
    CellScore,
    PromptSweepOutputExistsError,
    SliceScore,
    aggregate_by_arm,
    aggregate_cell,
    apply_winner_rule,
    assert_one_shot_output_dir,
    evaluate_all_corrupt_arms,
    evaluate_corrupt_arm,
    grammar_compliance,
    score_slice,
)

# ---------------------------------------------------------------------------
# grammar compliance
# ---------------------------------------------------------------------------


def test_grammar_compliance_full_strict_reply():
    rate, parsed = grammar_compliance("A|hello\nB|world")
    assert rate == pytest.approx(1.0)
    assert len(parsed.segments) == 2
    assert parsed.malformed_lines == ()


def test_grammar_compliance_partial_reply():
    rate, parsed = grammar_compliance("A|hello\nnot a valid line at all")
    assert 0.0 < rate < 1.0
    assert len(parsed.segments) == 1
    assert len(parsed.malformed_lines) == 1


def test_grammar_compliance_empty_reply_is_zero_never_vacuously_compliant():
    rate, parsed = grammar_compliance("")
    assert rate == 0.0
    assert parsed.segments == ()


def test_grammar_compliance_fully_malformed_reply_is_zero():
    rate, _ = grammar_compliance("no pipes here\nnor here")
    assert rate == 0.0


# ---------------------------------------------------------------------------
# score_slice (meeteval-dependent, gated per tests/unit/metrics/test_wer.py
# and tests/unit/probes/test_pattr_scoring.py's own convention)
# ---------------------------------------------------------------------------

pytest.importorskip("meeteval")

from meeting_minutes_agent.metrics.pins import MetricPins  # noqa: E402

_PINS = MetricPins(meeteval_version="0.4.3")


def test_score_slice_normal_case_is_scored_via_meeteval():
    reference = (PerSpeakerSegment(speaker="A", start=0.0, end=1.0, words="hello world"),)
    score = score_slice("T1-A1", "MTG1", 0, reference, "A|hello world", slice_start=0.0, slice_end=1.0, pins=_PINS)
    assert score.arm == "T1-A1"
    assert score.cp_wer == pytest.approx(0.0)
    assert score.hypothesis_empty is False
    assert score.compliance == pytest.approx(1.0)
    assert score.n_hypothesis_segments == 1


def test_score_slice_empty_reply_is_recorded_as_worst_case_not_sent_to_meeteval():
    # A zero-segment hypothesis can trip meeteval's own ORC-WER assertion on
    # an empty hypothesis (pattr_scoring.score_arm's own documented
    # limitation) -- this must never reach that code path.
    reference = (PerSpeakerSegment(speaker="A", start=0.0, end=1.0, words="hello world"),)
    score = score_slice("T1-A1", "MTG1", 0, reference, "", slice_start=0.0, slice_end=1.0, pins=_PINS)
    assert score.hypothesis_empty is True
    assert score.cp_wer == pytest.approx(1.0)
    assert score.confusion_cost == pytest.approx(0.0)
    assert score.compliance == pytest.approx(0.0)
    assert score.n_hypothesis_segments == 0


def test_score_slice_malformed_only_reply_is_also_the_empty_hypothesis_case():
    reference = (PerSpeakerSegment(speaker="A", start=0.0, end=1.0, words="hello world"),)
    score = score_slice("T1-A1", "MTG1", 0, reference, "not parseable at all", slice_start=0.0, slice_end=1.0, pins=_PINS)
    assert score.hypothesis_empty is True
    assert score.n_malformed_lines == 1


# ---------------------------------------------------------------------------
# per-cell aggregation
# ---------------------------------------------------------------------------


def _slice(arm, cp_wer, confusion, compliance, *, meeting_id="M", slice_index=0):
    return SliceScore(
        arm=arm,
        meeting_id=meeting_id,
        slice_index=slice_index,
        cp_wer=cp_wer,
        confusion_cost=confusion,
        compliance=compliance,
        n_reference_segments=1,
        n_hypothesis_segments=1,
        n_malformed_lines=0,
        hypothesis_empty=False,
    )


def _cell(arm, cp_wer, confusion, compliance) -> CellScore:
    return aggregate_cell(arm, [_slice(arm, cp_wer, confusion, compliance)])


def test_aggregate_cell_computes_means():
    slices = [
        _slice("T1-A1", cp_wer=0.2, confusion=0.1, compliance=1.0, slice_index=0),
        _slice("T1-A1", cp_wer=0.4, confusion=0.3, compliance=0.8, slice_index=1),
    ]
    cell = aggregate_cell("T1-A1", slices)
    assert cell.n_slices == 2
    assert cell.mean_cp_wer == pytest.approx(0.3)
    assert cell.mean_confusion_cost == pytest.approx(0.2)
    assert cell.mean_compliance == pytest.approx(0.9)


def test_aggregate_cell_rejects_empty_slice_list():
    with pytest.raises(ValueError):
        aggregate_cell("T1-A1", [])


def test_aggregate_cell_rejects_a_slice_tagged_with_a_different_arm():
    with pytest.raises(ValueError):
        aggregate_cell("T1-A1", [_slice("T2-A1", 0.1, 0.0, 1.0)])


def test_aggregate_by_arm_groups_by_the_slice_scores_own_arm_field():
    slices = [
        _slice("T1-A1", 0.1, 0.0, 1.0, slice_index=0),
        _slice("T1-A1", 0.2, 0.0, 1.0, slice_index=1),
        _slice("T2-A1", 0.3, 0.0, 1.0, slice_index=0),
    ]
    by_arm = aggregate_by_arm(slices)
    assert set(by_arm) == {"T1-A1", "T2-A1"}
    assert by_arm["T1-A1"].n_slices == 2
    assert by_arm["T2-A1"].n_slices == 1


# ---------------------------------------------------------------------------
# the mechanical winner rule -- every branch
# ---------------------------------------------------------------------------


def _all_grid_cells(*, cp_wer=0.5, confusion=0.3, compliance=0.95) -> dict[str, CellScore]:
    return {arm: _cell(arm, cp_wer, confusion, compliance) for arm in GRID_CELLS}


def test_winner_rule_clear_winner():
    cells = _all_grid_cells()
    cells["T2-A1"] = _cell("T2-A1", cp_wer=0.20, confusion=0.05, compliance=0.95)
    result = apply_winner_rule(cells)
    assert result.status == "WINNER"
    assert result.winner_arm == "T2-A1"
    assert result.tie_set == ("T2-A1",)


def test_winner_rule_compliance_gate_boundary_is_inclusive():
    cells = _all_grid_cells()
    cells["T2-A1"] = _cell("T2-A1", cp_wer=0.20, confusion=0.05, compliance=0.90)  # exactly the gate
    result = apply_winner_rule(cells)
    assert "T2-A1" in result.eligible_arms


def test_winner_rule_tie_set_broken_by_lower_confusion():
    cells = _all_grid_cells()
    cells["T2-A1"] = _cell("T2-A1", cp_wer=0.200, confusion=0.10, compliance=0.95)
    cells["T3-A2"] = _cell("T3-A2", cp_wer=0.205, confusion=0.02, compliance=0.95)  # within 0.01, lower confusion
    result = apply_winner_rule(cells)
    assert set(result.tie_set) == {"T2-A1", "T3-A2"}
    assert result.winner_arm == "T3-A2"


def test_winner_rule_tie_broken_by_higher_compliance_when_confusion_ties():
    cells = _all_grid_cells()
    cells["T2-A1"] = _cell("T2-A1", cp_wer=0.200, confusion=0.10, compliance=0.91)
    cells["T3-A2"] = _cell("T3-A2", cp_wer=0.205, confusion=0.10, compliance=0.99)
    result = apply_winner_rule(cells)
    assert result.winner_arm == "T3-A2"


def test_winner_rule_tie_broken_by_lower_template_index_when_confusion_and_compliance_tie():
    cells = _all_grid_cells()
    cells["T3-A1"] = _cell("T3-A1", cp_wer=0.200, confusion=0.10, compliance=0.95)
    cells["T2-A2"] = _cell("T2-A2", cp_wer=0.205, confusion=0.10, compliance=0.95)  # T2 < T3
    result = apply_winner_rule(cells)
    assert result.winner_arm == "T2-A2"


def test_winner_rule_tie_broken_by_lower_arrangement_index_as_last_resort():
    cells = _all_grid_cells()
    cells["T2-A3"] = _cell("T2-A3", cp_wer=0.200, confusion=0.10, compliance=0.95)
    cells["T2-A1"] = _cell("T2-A1", cp_wer=0.205, confusion=0.10, compliance=0.95)  # same template, lower A index
    result = apply_winner_rule(cells)
    assert result.winner_arm == "T2-A1"


def test_winner_rule_grammar_blocked_when_no_cell_reaches_the_gate():
    cells = _all_grid_cells(compliance=0.50)
    result = apply_winner_rule(cells)
    assert result.status == GRAMMAR_BLOCKED
    assert result.winner_arm is None
    assert result.tie_set == ()
    assert result.eligible_arms == ()
    assert len(result.ranked_by_cp_wer) == len(GRID_CELLS)  # still reported, for audit


def test_winner_rule_ignores_non_grid_arms_even_if_they_would_otherwise_win():
    cells = _all_grid_cells()
    cells["T2-A1"] = _cell("T2-A1", cp_wer=0.10, confusion=0.05, compliance=0.95)
    cells[ARM_X1] = _cell(ARM_X1, cp_wer=0.0, confusion=0.0, compliance=1.0)
    cells[ARM_X2] = _cell(ARM_X2, cp_wer=0.0, confusion=0.0, compliance=1.0)
    result = apply_winner_rule(cells)
    assert result.winner_arm == "T2-A1"
    assert ARM_X1 not in result.eligible_arms
    assert ARM_X2 not in result.eligible_arms


# ---------------------------------------------------------------------------
# corrupt-context verdicts -- all three outcomes
# ---------------------------------------------------------------------------


def test_corrupt_verdict_context_sensitive_at_the_registered_threshold():
    reference = _cell(REFERENCE_CELL, cp_wer=0.20, confusion=0.05, compliance=0.95)
    x1 = _cell(ARM_X1, cp_wer=0.25, confusion=0.05, compliance=0.95)  # exactly +0.05
    verdict = evaluate_corrupt_arm(x1, reference)
    assert verdict.verdict == "CONTEXT-SENSITIVE"
    assert verdict.degradation == pytest.approx(0.05)


def test_corrupt_verdict_context_sensitive_above_threshold():
    reference = _cell(REFERENCE_CELL, cp_wer=0.20, confusion=0.05, compliance=0.95)
    x1 = _cell(ARM_X1, cp_wer=0.35, confusion=0.05, compliance=0.95)  # +0.15
    verdict = evaluate_corrupt_arm(x1, reference)
    assert verdict.verdict == "CONTEXT-SENSITIVE"


def test_corrupt_verdict_context_inert_at_the_registered_threshold():
    reference = _cell(REFERENCE_CELL, cp_wer=0.20, confusion=0.05, compliance=0.95)
    x2 = _cell(ARM_X2, cp_wer=0.21, confusion=0.05, compliance=0.95)  # exactly +0.01
    verdict = evaluate_corrupt_arm(x2, reference)
    assert verdict.verdict == "CONTEXT-INERT"


def test_corrupt_verdict_context_inert_when_corrupt_arm_improves():
    reference = _cell(REFERENCE_CELL, cp_wer=0.20, confusion=0.05, compliance=0.95)
    x2 = _cell(ARM_X2, cp_wer=0.05, confusion=0.05, compliance=0.95)  # improved (negative degradation)
    verdict = evaluate_corrupt_arm(x2, reference)
    assert verdict.verdict == "CONTEXT-INERT"
    assert verdict.degradation < 0.0


def test_corrupt_verdict_context_indeterminate_strictly_between_thresholds():
    reference = _cell(REFERENCE_CELL, cp_wer=0.20, confusion=0.05, compliance=0.95)
    x1 = _cell(ARM_X1, cp_wer=0.23, confusion=0.05, compliance=0.95)  # +0.03
    verdict = evaluate_corrupt_arm(x1, reference)
    assert verdict.verdict == "CONTEXT-INDETERMINATE"


def test_evaluate_all_corrupt_arms_reads_both_from_the_reference_cell():
    cells = {
        REFERENCE_CELL: _cell(REFERENCE_CELL, cp_wer=0.20, confusion=0.05, compliance=0.95),
        ARM_X1: _cell(ARM_X1, cp_wer=0.30, confusion=0.05, compliance=0.95),
        ARM_X2: _cell(ARM_X2, cp_wer=0.205, confusion=0.05, compliance=0.95),
    }
    verdicts = evaluate_all_corrupt_arms(cells)
    assert set(verdicts) == {ARM_X1, ARM_X2}
    assert verdicts[ARM_X1].verdict == "CONTEXT-SENSITIVE"
    assert verdicts[ARM_X2].verdict == "CONTEXT-INERT"
    assert verdicts[ARM_X1].reference_arm == REFERENCE_CELL


def test_evaluate_all_corrupt_arms_requires_the_reference_cell_present():
    cells = {ARM_X1: _cell(ARM_X1, 0.3, 0.05, 0.95), ARM_X2: _cell(ARM_X2, 0.2, 0.05, 0.95)}
    with pytest.raises(KeyError):
        evaluate_all_corrupt_arms(cells)


# ---------------------------------------------------------------------------
# one-shot idempotence guard
# ---------------------------------------------------------------------------


def test_one_shot_guard_passes_on_a_fresh_directory(tmp_path):
    assert_one_shot_output_dir(tmp_path)  # must not raise


def test_one_shot_guard_passes_when_out_dir_does_not_exist_yet(tmp_path):
    assert_one_shot_output_dir(tmp_path / "not-created-yet")  # must not raise


def test_one_shot_guard_refuses_when_a_prior_verdict_exists(tmp_path):
    (tmp_path / "verdict.json").write_text("{}", encoding="utf-8")
    with pytest.raises(PromptSweepOutputExistsError):
        assert_one_shot_output_dir(tmp_path)


def test_one_shot_guard_force_bypasses_the_refusal(tmp_path):
    (tmp_path / "verdict.json").write_text("{}", encoding="utf-8")
    assert_one_shot_output_dir(tmp_path, force=True)  # must not raise
