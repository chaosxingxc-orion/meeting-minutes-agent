from meeting_minutes_agent.probes.e4_mechanism import (
    CANDIDATE_ORDER,
    choose_decision,
    classify_false_association,
    classify_transition,
)


def _overall(**overrides):
    contrasts = {
        "speaker_bare_wer": -0.01,
        "speaker_global_false_hint_target_rate": 0.0,
        "speaker_global_carry_hit_rate": 0.01,
    }
    contrasts.update(overrides)
    return {"contrasts": contrasts}


def test_transition_and_false_association_classes_are_mutually_exclusive():
    assert classify_transition(False, True) == "repair"
    assert classify_transition(True, False) == "break"
    assert classify_transition(True, True) == "retained"
    assert classify_transition(False, False) == "missed"
    assert classify_false_association(1, 0) == "net-carry-gain/no-wer-harm"
    assert classify_false_association(0, 1) == "no-net-carry-gain/wer-harm"


def test_decision_selects_only_first_qualified_fixed_predicate():
    candidates = {name: {"qualifies": name in {CANDIDATE_ORDER[1], CANDIDATE_ORDER[2]}} for name in CANDIDATE_ORDER}
    decision, selected = choose_decision(_overall(), candidates)
    assert decision == "PREREGISTER-ONE-FIXED-POLICY"
    assert selected == CANDIDATE_ORDER[1]


def test_safety_rule_precedes_actionable_candidate():
    candidates = {name: {"qualifies": True} for name in CANDIDATE_ORDER}
    decision, selected = choose_decision(_overall(speaker_bare_wer=0.011), candidates)
    assert decision == "SAFETY-RISK-DOMINATES"
    assert selected is None


def test_no_qualified_predicate_yields_no_actionable_mechanism():
    candidates = {name: {"qualifies": False} for name in CANDIDATE_ORDER}
    decision, selected = choose_decision(_overall(), candidates)
    assert decision == "NO-ACTIONABLE-MECHANISM"
    assert selected is None
