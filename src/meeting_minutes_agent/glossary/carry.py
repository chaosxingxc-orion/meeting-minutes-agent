"""Carry accounting: per-chunk glossary-size bookkeeping and the census's
first-half -> second-half coverage metric.

:func:`accumulate_glossary` and :func:`carry_accounting` both fold
:func:`~.accumulate.merge_entries` across an ordered sequence of per-chunk
entries; :func:`carry_accounting` additionally records, at each chunk
boundary, how many of the accumulated glossary's terms are newly
introduced this chunk versus how many carried over unchanged from a prior
chunk. :func:`second_half_coverage` reproduces the metric defined in
``docs/readiness/2026-08-17-meetingbank-entity-census.md`` SS7: build a
glossary from one half of an episode, then measure what fraction of the
OTHER half's raw mentions the glossary's terms would have covered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .accumulate import _entry_key, merge_entries
from .models import GlossaryEntry
from .normalise import normalise_surface


@dataclass(frozen=True)
class ChunkGlossarySnapshot:
    """The accumulated-glossary state immediately after folding in one
    chunk. ``total_terms`` is the accumulated glossary's size at this
    point; ``new_terms`` is how many of those terms were introduced BY
    this chunk (first appearance); ``carried_terms`` is how many were
    already present before this chunk and simply persisted
    (``total_terms == new_terms + carried_terms`` always holds)."""

    chunk_index: int
    total_terms: int
    new_terms: int
    carried_terms: int

    def __post_init__(self) -> None:
        if self.new_terms + self.carried_terms != self.total_terms:
            raise ValueError(
                f"chunk {self.chunk_index}: new_terms ({self.new_terms}) + carried_terms "
                f"({self.carried_terms}) != total_terms ({self.total_terms})"
            )


@dataclass(frozen=True)
class CarryReport:
    snapshots: tuple[ChunkGlossarySnapshot, ...]
    final_glossary: tuple[GlossaryEntry, ...]
    total_new_terms: int
    total_carried_events: int


def accumulate_glossary(chunk_entries_sequence: Sequence[Sequence[GlossaryEntry]]) -> tuple[GlossaryEntry, ...]:
    """Fold :func:`~.accumulate.merge_entries` over an ordered sequence of
    per-chunk entry lists, returning only the final accumulated glossary
    state (no per-chunk bookkeeping -- see :func:`carry_accounting` for
    that)."""

    accumulated: tuple[GlossaryEntry, ...] = ()
    for chunk_entries in chunk_entries_sequence:
        accumulated = merge_entries(accumulated, chunk_entries)
    return accumulated


def carry_accounting(chunk_entries_sequence: Sequence[Sequence[GlossaryEntry]]) -> CarryReport:
    """Walk the same fold as :func:`accumulate_glossary`, recording a
    :class:`ChunkGlossarySnapshot` at each step. ``total_new_terms`` sums
    ``new_terms`` across all snapshots (equals the final glossary's size,
    since every term is new exactly once); ``total_carried_events`` sums
    ``carried_terms`` -- the total count of chunk-boundary crossings a
    term survived, the raw measure of how much carry actually happened."""

    accumulated: tuple[GlossaryEntry, ...] = ()
    snapshots: list[ChunkGlossarySnapshot] = []
    for idx, chunk_entries in enumerate(chunk_entries_sequence):
        existing_keys = {_entry_key(e) for e in accumulated}
        accumulated = merge_entries(accumulated, chunk_entries)
        current_keys = {_entry_key(e) for e in accumulated}
        new_terms = len(current_keys - existing_keys)
        carried_terms = len(current_keys & existing_keys)
        snapshots.append(
            ChunkGlossarySnapshot(
                chunk_index=idx,
                total_terms=len(current_keys),
                new_terms=new_terms,
                carried_terms=carried_terms,
            )
        )
    total_new = sum(s.new_terms for s in snapshots)
    total_carried = sum(s.carried_terms for s in snapshots)
    return CarryReport(
        snapshots=tuple(snapshots),
        final_glossary=accumulated,
        total_new_terms=total_new,
        total_carried_events=total_carried,
    )


def rank_terms_by_frequency(entries: Sequence[GlossaryEntry]) -> tuple[GlossaryEntry, ...]:
    """Sort entries by evidence count descending; ties broken by
    ``first_seen_chunk`` ascending then ``canonical_surface`` ascending,
    for determinism -- the same tie-break :func:`glossary.gate.apply_inventory_cap`
    uses, so ``rank_terms_by_frequency(...)[:cap]`` matches a gate's
    inventory-cap selection exactly."""

    return tuple(sorted(entries, key=lambda e: (-e.evidence_count, e.first_seen_chunk, e.canonical_surface)))


def second_half_coverage(
    first_half_entries: Sequence[GlossaryEntry],
    second_half_mentions: Sequence[str],
    *,
    top_n: int | None = None,
) -> float:
    """The census's carry-delta metric (SS7 of the MeetingBank entity
    re-census): build a term list from ``first_half_entries`` (optionally
    truncated to its top ``top_n`` terms by evidence count, matching the
    census's "top 10/25/50/unbounded" columns), then measure the fraction
    of ``second_half_mentions`` (raw surface-form mention strings, ONE per
    occurrence -- this is mention-weighted/pooled coverage, not
    type-weighted) whose normalised surface matches either a first-half
    entry's canonical surface OR one of its recorded variants. Matching
    variants too (not just the canonical form) is a deliberate widening
    beyond the census's raw-string method: a term list is membership-
    tested by normalised form in this codebase, and a variant is still the
    same term.

    Returns 0.0 for an empty ``second_half_mentions`` (no mentions to
    cover is vacuously zero coverage, not undefined -- callers scoring a
    real corpus should skip empty second halves rather than average in a
    NaN)."""

    terms = rank_terms_by_frequency(first_half_entries) if top_n is not None else tuple(first_half_entries)
    if top_n is not None:
        terms = terms[:top_n]

    known: set[str] = set()
    for e in terms:
        known.add(normalise_surface(e.canonical_surface))
        for v in e.variants:
            known.add(normalise_surface(v))

    if not second_half_mentions:
        return 0.0

    covered = sum(1 for m in second_half_mentions if normalise_surface(m) in known)
    return covered / len(second_half_mentions)


__all__ = [
    "ChunkGlossarySnapshot",
    "CarryReport",
    "accumulate_glossary",
    "carry_accounting",
    "rank_terms_by_frequency",
    "second_half_coverage",
]
