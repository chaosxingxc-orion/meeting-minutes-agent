from meeting_minutes_agent.probes.e4_disjoint_direction_scoring import DirectionScore
from meeting_minutes_agent.probes.e4_safety_gate_audit import (
    CANDIDATE_ORDER,
    choose_audit_decision,
    dialogue_fold,
    evaluate_policy_slice,
    width_bucket,
)


def _score(target, arm, *, hit=0, carry_error=1, wer_error=1, false=0):
    return DirectionScore(target, target.split("-")[0], arm, wer_error, 10, carry_error, 1, hit, 1, false, 10)


def test_dialogue_fold_is_deterministic_and_bounded():
    assert dialogue_fold("dialogue-1") == dialogue_fold("dialogue-1")
    assert {dialogue_fold(f"dialogue-{index}") for index in range(50)} <= {0, 1, 2, 3}


def test_width_buckets_are_frozen():
    assert [width_bucket(value) for value in (1, 2, 4, 5, 8)] == ["1", "2-4", "2-4", "5-8", "5-8"]


def test_policy_keeps_every_target_and_falls_back_to_global():
    scores = {
        ("d1-t1", "D0-global"): _score("d1-t1", "D0-global"),
        ("d1-t1", "D1-speaker"): _score("d1-t1", "D1-speaker", hit=1, carry_error=0),
        ("d2-t1", "D0-global"): _score("d2-t1", "D0-global", hit=1, carry_error=0),
        ("d2-t1", "D1-speaker"): _score("d2-t1", "D1-speaker", false=1),
    }
    result = evaluate_policy_slice(("d1-t1", "d2-t1"), {"d1-t1"}, scores)
    assert result["targets"] == 2
    assert result["selected_targets"] == 1
    assert result["policy"]["carry_hits"] == 2
    assert result["policy"]["false_hint_targets"] == 0


def test_decision_distinguishes_no_gate_scene_dependence_and_internal_stability():
    empty = {name: {"coverage_pass": False, "overall_pass": False, "qualifies": False} for name in CANDIDATE_ORDER}
    assert choose_audit_decision(empty) == ("NO-USABLE-COVERAGE", None)
    unsafe = {name: {"coverage_pass": True, "overall_pass": False, "qualifies": False} for name in CANDIDATE_ORDER}
    assert choose_audit_decision(unsafe) == ("NO-SAFE-GATE", None)
    unstable = {name: {"coverage_pass": True, "overall_pass": True, "qualifies": False} for name in CANDIDATE_ORDER}
    assert choose_audit_decision(unstable) == ("SCENARIO-DEPENDENT", None)
    stable = dict(unstable)
    stable[CANDIDATE_ORDER[2]] = {"coverage_pass": True, "overall_pass": True, "qualifies": True}
    assert choose_audit_decision(stable) == ("WITHIN-SURFACE-STABLE-CANDIDATE", CANDIDATE_ORDER[2])
