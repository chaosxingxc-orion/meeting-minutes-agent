"""Cross-chunk carry: fold a new chunk's gated entries into the
episode-so-far accumulated glossary.

The merge key is ``(normalised canonical surface, provenance, leakage
tier)`` -- deliberately NOT surface alone. Two entries with the same
surface but different provenance (a speech-pass mention and a metadata
mention of the same name) or different leakage tier stay as separate
records, because collapsing them would destroy exactly the distinction
:mod:`.provenance`'s views need to filter or refuse on.
"""

from __future__ import annotations

from typing import Sequence

from .models import GlossaryEntry
from .normalise import normalise_surface


def _entry_key(entry: GlossaryEntry) -> tuple[str, str, str]:
    return (normalise_surface(entry.canonical_surface), entry.provenance.value, entry.leakage_tier.value)


def _merge_pair(existing: GlossaryEntry, incoming: GlossaryEntry) -> GlossaryEntry:
    """Merge two entries already known to share a key. Variants union;
    evidence counts sum; ``first_seen_chunk`` and ``introduced_by`` both
    stick to whichever entry actually appeared earlier (a term's
    introducer is fixed at first sighting -- a later chunk's mention by a
    different speaker does not retroactively change who introduced it);
    the displayed canonical surface follows the higher-evidence side (tie
    goes to the earlier-seen entry, for determinism)."""

    earlier, later = (
        (existing, incoming) if existing.first_seen_chunk <= incoming.first_seen_chunk else (incoming, existing)
    )
    canonical = existing.canonical_surface if existing.evidence_count >= incoming.evidence_count else incoming.canonical_surface
    merged_variants = tuple(sorted(set(existing.variants) | set(incoming.variants)))
    return GlossaryEntry(
        canonical_surface=canonical,
        variants=merged_variants,
        first_seen_chunk=earlier.first_seen_chunk,
        evidence_count=existing.evidence_count + incoming.evidence_count,
        provenance=existing.provenance,
        leakage_tier=existing.leakage_tier,
        introduced_by=earlier.introduced_by,
    )


def merge_entries(
    existing: Sequence[GlossaryEntry],
    new: Sequence[GlossaryEntry],
) -> tuple[GlossaryEntry, ...]:
    """Fold ``new`` (one chunk's freshly-gated entries) into ``existing``
    (the accumulated episode state so far). Entries sharing a key merge
    via :func:`_merge_pair`; entries with a new key are appended in the
    order first encountered (``existing`` order first, then any genuinely
    new keys from ``new``, in ``new``'s own order). Pure function: neither
    input sequence is mutated, and this is the ``gated``/default carry
    rule every arm except ``no-carry`` uses across chunk boundaries."""

    by_key: dict[tuple[str, str, str], GlossaryEntry] = {}
    order: list[tuple[str, str, str]] = []
    for e in existing:
        k = _entry_key(e)
        by_key[k] = e
        order.append(k)
    for e in new:
        k = _entry_key(e)
        if k in by_key:
            by_key[k] = _merge_pair(by_key[k], e)
        else:
            by_key[k] = e
            order.append(k)
    return tuple(by_key[k] for k in order)


__all__ = ["merge_entries"]
