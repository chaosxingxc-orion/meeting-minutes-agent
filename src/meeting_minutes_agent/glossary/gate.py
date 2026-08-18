"""Stage 4: gate -- evidence-threshold, per-term budget, and inventory cap.

The In-Context-Fixation-motivated rules (arXiv 2511.18774's naive-arm
caution): a per-term repetition cap (a single hyper-frequent term cannot
dominate the evidence budget) and an inventory cap (the whole glossary is
bounded, however much candidate evidence exists).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .models import GlossaryEntry


@dataclass(frozen=True)
class GateConfig:
    min_evidence: int = 2
    per_term_repetition_cap: int | None = None
    inventory_cap: int | None = None


def apply_evidence_threshold(entries: Sequence[GlossaryEntry], min_evidence: int) -> tuple[GlossaryEntry, ...]:
    """Drop entries whose evidence count is below ``min_evidence``."""

    return tuple(e for e in entries if e.evidence_count >= min_evidence)


def apply_repetition_cap(entries: Sequence[GlossaryEntry], cap: int | None) -> tuple[GlossaryEntry, ...]:
    """Clip each entry's evidence count to at most ``cap`` -- a single
    hyper-frequent term cannot out-rank everything else on repetition
    alone. ``cap=None`` is a no-op."""

    if cap is None:
        return tuple(entries)
    out = []
    for e in entries:
        if e.evidence_count <= cap:
            out.append(e)
        else:
            out.append(
                GlossaryEntry(
                    canonical_surface=e.canonical_surface,
                    variants=e.variants,
                    first_seen_chunk=e.first_seen_chunk,
                    evidence_count=cap,
                    provenance=e.provenance,
                    leakage_tier=e.leakage_tier,
                )
            )
    return tuple(out)


def apply_inventory_cap(entries: Sequence[GlossaryEntry], cap: int | None) -> tuple[GlossaryEntry, ...]:
    """Keep at most ``cap`` entries, ranked by (evidence count desc,
    first-seen chunk asc, canonical surface asc) for determinism.
    ``cap=None`` is a no-op."""

    if cap is None or len(entries) <= cap:
        return tuple(entries)
    ranked = sorted(entries, key=lambda e: (-e.evidence_count, e.first_seen_chunk, e.canonical_surface))
    return tuple(ranked[:cap])


def gate_entries(entries: Sequence[GlossaryEntry], config: GateConfig) -> tuple[GlossaryEntry, ...]:
    """Apply the three gate rules in order: evidence threshold, per-term
    repetition cap, inventory cap."""

    out = apply_evidence_threshold(entries, config.min_evidence)
    out = apply_repetition_cap(out, config.per_term_repetition_cap)
    out = apply_inventory_cap(out, config.inventory_cap)
    return out
