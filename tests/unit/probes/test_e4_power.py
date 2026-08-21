from __future__ import annotations

import pytest

from meeting_minutes_agent.probes.e4_power import DialoguePowerStats, budget_summary, required_paired_mentions, select_roster


def test_required_mentions_increases_for_smaller_effect():
    assert required_paired_mentions(mde=0.05, discordance_rate=0.15, design_effect=1.5) > required_paired_mentions(mde=0.10, discordance_rate=0.15, design_effect=1.5)


def test_required_mentions_rejects_invalid_assumptions():
    with pytest.raises(ValueError):
        required_paired_mentions(mde=0, discordance_rate=0.15, design_effect=1.5)


def test_roster_is_deterministic_and_meets_attrition_adjusted_target():
    stats = [DialoguePowerStats(f"D{i}", 10, 100, 4, 3, 30) for i in range(10)]
    left = select_roster(stats, required_mentions=12, usable_fraction=0.75, seed="s")
    right = select_roster(tuple(reversed(stats)), required_mentions=12, usable_fraction=0.75, seed="s")
    assert left == right
    assert sum(x.carry_mentions for x in left) >= 16


def test_budget_counts_pass0_and_second_pass_separately():
    roster = [DialoguePowerStats("D", 10, 100, 4, 3, 30)]
    assert budget_summary(roster, second_pass_arms=4) == {
        "dialogues": 1, "carry_mentions": 4, "target_turns": 3,
        "pass0_calls": 10, "second_pass_calls": 12, "total_calls": 22,
        "pass0_audio_seconds": 100, "second_pass_audio_seconds": 120, "total_audio_seconds": 220,
    }
