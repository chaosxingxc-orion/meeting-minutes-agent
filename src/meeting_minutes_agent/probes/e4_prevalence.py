"""Frozen aggregation rules for the E4 disjoint prevalence pilot."""

from __future__ import annotations

import random
from typing import Sequence

BREAK_EVEN = 1963 / (4782 * 0.85)


def percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def cluster_bootstrap_interval(
    dialogue_counts: Sequence[tuple[int, int]], *, level: float, seed: int, replicates: int = 20_000
) -> tuple[float, float]:
    if not dialogue_counts or not 0 < level < 1 or replicates < 1:
        raise ValueError("invalid bootstrap input")
    if any(usable < 1 or positive < 0 or positive > usable for positive, usable in dialogue_counts):
        raise ValueError("invalid dialogue counts")
    generator = random.Random(seed)
    estimates = []
    for _ in range(replicates):
        sampled = [dialogue_counts[generator.randrange(len(dialogue_counts))] for _ in dialogue_counts]
        estimates.append(sum(x[0] for x in sampled) / sum(x[1] for x in sampled))
    tail = (1 - level) / 2
    return percentile(estimates, tail), percentile(estimates, 1 - tail)


def screening_decision(
    *, stage_dialogues: int, prevalence: float, ci80_lower: float, ci90_upper: float, usable_fraction: float
) -> str:
    if stage_dialogues == 20:
        return "EARLY-LOW-PREVALENCE" if prevalence < 0.35 else "CONTINUE"
    if stage_dialogues == 40:
        return "EARLY-LOW-PREVALENCE" if prevalence < 0.40 else "CONTINUE"
    if stage_dialogues != 60:
        raise ValueError("stage_dialogues must be 20, 40, or 60")
    if prevalence >= BREAK_EVEN and ci80_lower >= 0.40 and usable_fraction >= 0.85:
        return "PREVALENCE-SCREEN-PASS"
    if ci90_upper < BREAK_EVEN:
        return "LOW-PREVALENCE"
    return "INCONCLUSIVE"


__all__ = ["BREAK_EVEN", "cluster_bootstrap_interval", "percentile", "screening_decision"]
