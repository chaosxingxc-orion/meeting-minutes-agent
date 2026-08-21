from __future__ import annotations

import pytest

from meeting_minutes_agent.probes.e4_disjoint_power import (
    build_scenario,
    cluster_summary,
    policy_budget,
    required_raw_carry,
)
from meeting_minutes_agent.probes.e4_power import DialoguePowerStats


def _stat(name: str, carry: int = 4) -> DialoguePowerStats:
    return DialoguePowerStats(name, 10, 100.0, carry, 3, 30.0)


def test_required_raw_carry_applies_prevalence_and_attrition():
    assert required_raw_carry(required_analyzable=34, predicate_prevalence=0.5, usable_fraction=0.85) == 80
    with pytest.raises(ValueError):
        required_raw_carry(required_analyzable=34, predicate_prevalence=0, usable_fraction=0.85)


def test_policy_budget_aliases_policy_arm_instead_of_recalling_model():
    budget = policy_budget([_stat("D")], predicate_prevalence=0.5)
    assert budget["pass0_calls"] == 10
    assert budget["expected_disjoint_target_calls"] == 2
    assert budget["deduplicated_second_pass_calls"] == 8
    assert budget["naive_four_arm_second_pass_calls"] == 12


def test_cluster_summary_reports_roster_concentration():
    summary = cluster_summary([_stat("A", 1), _stat("B", 2), _stat("C", 8)])
    assert summary == {
        "eligible_dialogues": 2,
        "mean_carry": 5,
        "median_carry": 5.0,
        "p90_carry": 8,
        "max_carry": 8,
    }


def test_scenario_is_deterministic_and_reaches_required_mass():
    stats = [_stat(f"D{i}", 50) for i in range(100)]
    left = build_scenario(
        stats, mde=0.1, prevalence=0.5, usable_fraction=0.85,
        discordance_rate=0.15, design_effect=1.5, seed="fixed",
    )
    right = build_scenario(
        tuple(reversed(stats)), mde=0.1, prevalence=0.5, usable_fraction=0.85,
        discordance_rate=0.15, design_effect=1.5, seed="fixed",
    )
    assert left == right
    assert left["budget"]["carry_mentions"] >= left["required_raw_carry"]
