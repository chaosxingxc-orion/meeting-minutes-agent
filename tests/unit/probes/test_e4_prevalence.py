from meeting_minutes_agent.probes.e4_prevalence import (
    BREAK_EVEN,
    cluster_bootstrap_interval,
    screening_decision,
)


def test_cluster_bootstrap_is_deterministic_and_bounded():
    counts = [(3, 5), (1, 2), (2, 4)]
    left = cluster_bootstrap_interval(counts, level=0.8, seed=7, replicates=500)
    right = cluster_bootstrap_interval(counts, level=0.8, seed=7, replicates=500)
    assert left == right
    assert 0 <= left[0] <= left[1] <= 1


def test_stage_stops_and_final_decisions_are_frozen():
    assert screening_decision(stage_dialogues=20, prevalence=0.34, ci80_lower=0.2, ci90_upper=0.5, usable_fraction=0.9) == "EARLY-LOW-PREVALENCE"
    assert screening_decision(stage_dialogues=40, prevalence=0.45, ci80_lower=0.3, ci90_upper=0.6, usable_fraction=0.9) == "CONTINUE"
    assert screening_decision(stage_dialogues=60, prevalence=BREAK_EVEN, ci80_lower=0.40, ci90_upper=0.6, usable_fraction=0.85) == "PREVALENCE-SCREEN-PASS"
    assert screening_decision(stage_dialogues=60, prevalence=0.3, ci80_lower=0.2, ci90_upper=0.4, usable_fraction=0.9) == "LOW-PREVALENCE"
