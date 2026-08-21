"""Zero-model scenario planning for the E4 disjoint fixed policy."""

from __future__ import annotations

import math
from dataclasses import asdict
from statistics import mean, median
from typing import Sequence

from .e4_power import DialoguePowerStats, budget_summary, required_paired_mentions, select_roster


def required_raw_carry(
    *, required_analyzable: int, predicate_prevalence: float, usable_fraction: float
) -> int:
    if required_analyzable <= 0:
        raise ValueError("required_analyzable must be positive")
    if not 0 < predicate_prevalence <= 1:
        raise ValueError("predicate_prevalence must lie in (0, 1]")
    if not 0 < usable_fraction <= 1:
        raise ValueError("usable_fraction must lie in (0, 1]")
    return math.ceil(required_analyzable / (predicate_prevalence * usable_fraction))


def cluster_summary(stats: Sequence[DialoguePowerStats]) -> dict[str, float | int]:
    eligible = [item for item in stats if item.carry_mentions >= 2]
    masses = sorted(item.carry_mentions for item in eligible)
    if not masses:
        return {"eligible_dialogues": 0, "mean_carry": 0.0, "median_carry": 0.0, "p90_carry": 0, "max_carry": 0}
    p90_index = math.ceil(0.9 * len(masses)) - 1
    return {
        "eligible_dialogues": len(eligible),
        "mean_carry": mean(masses),
        "median_carry": median(masses),
        "p90_carry": masses[p90_index],
        "max_carry": masses[-1],
    }


def policy_budget(
    roster: Sequence[DialoguePowerStats], *, predicate_prevalence: float
) -> dict[str, float | int]:
    base = budget_summary(roster, second_pass_arms=0)
    target_turns = int(base["target_turns"])
    target_seconds = sum(item.target_seconds for item in roster)
    conditional_calls = math.ceil(target_turns * predicate_prevalence)
    conditional_seconds = target_seconds * predicate_prevalence
    deduplicated_second_calls = 2 * target_turns + conditional_calls
    deduplicated_second_seconds = 2 * target_seconds + conditional_seconds
    naive_second_calls = 4 * target_turns
    naive_second_seconds = 4 * target_seconds
    return {
        **base,
        "expected_disjoint_target_calls": conditional_calls,
        "deduplicated_second_pass_calls": deduplicated_second_calls,
        "deduplicated_total_calls": int(base["pass0_calls"]) + deduplicated_second_calls,
        "deduplicated_second_pass_audio_seconds": deduplicated_second_seconds,
        "deduplicated_total_audio_seconds": float(base["pass0_audio_seconds"]) + deduplicated_second_seconds,
        "naive_four_arm_second_pass_calls": naive_second_calls,
        "naive_four_arm_total_calls": int(base["pass0_calls"]) + naive_second_calls,
        "naive_four_arm_second_pass_audio_seconds": naive_second_seconds,
        "naive_four_arm_total_audio_seconds": float(base["pass0_audio_seconds"]) + naive_second_seconds,
    }


def build_scenario(
    stats: Sequence[DialoguePowerStats], *, mde: float, prevalence: float, usable_fraction: float,
    discordance_rate: float, design_effect: float, seed: str,
) -> dict[str, object]:
    analyzable = required_paired_mentions(
        mde=mde, discordance_rate=discordance_rate, design_effect=design_effect
    )
    raw_carry = required_raw_carry(
        required_analyzable=analyzable,
        predicate_prevalence=prevalence,
        usable_fraction=usable_fraction,
    )
    roster = select_roster(stats, required_mentions=raw_carry, usable_fraction=1.0, seed=seed)
    return {
        "mde": mde,
        "assumed_predicate_prevalence": prevalence,
        "required_analyzable_predicate_carry": analyzable,
        "required_raw_carry": raw_carry,
        "roster": [asdict(item) for item in roster],
        "budget": policy_budget(roster, predicate_prevalence=prevalence),
    }


__all__ = ["build_scenario", "cluster_summary", "policy_budget", "required_raw_carry"]
