"""Stage 3: dedupe -- cluster raw candidate surfaces into canonical terms
by their normalised form.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .extract import Candidate
from .normalise import normalise_surface


@dataclass(frozen=True)
class Cluster:
    canonical_surface: str
    variants: tuple[str, ...]
    evidence_count: int


def dedupe_candidates(candidates: Sequence[Candidate]) -> list[Cluster]:
    """Group candidates whose normalised surface matches. The canonical
    display surface is the cluster's most frequent raw variant (ties
    broken alphabetically for determinism); ``evidence_count`` is the
    total number of raw candidate occurrences across every variant in the
    cluster. Candidates that normalise to the empty string are dropped."""

    groups: dict[str, dict[str, int]] = {}
    order: list[str] = []
    for c in candidates:
        key = normalise_surface(c.surface)
        if not key:
            continue
        if key not in groups:
            groups[key] = {}
            order.append(key)
        groups[key][c.surface] = groups[key].get(c.surface, 0) + 1

    clusters: list[Cluster] = []
    for key in order:
        variant_counts = groups[key]
        total = sum(variant_counts.values())
        canonical = sorted(variant_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        variants = tuple(sorted(variant_counts.keys()))
        clusters.append(Cluster(canonical_surface=canonical, variants=variants, evidence_count=total))
    return clusters
