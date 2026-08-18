"""Provenance factorization views and the machine-enforced leakage-tier gate.

Two independent axes over a flat sequence of :class:`~.models.GlossaryEntry`:

- **provenance** (speech-pass / metadata): :func:`speech_only`,
  :func:`metadata_only`, :func:`combined` -- the registered INGEST
  provenance filter (deep-check synthesis SS3.2's speech-only / metadata-only
  / combined factorization).
- **leakage tier** (M0 / M1): :func:`build_runtime_supply_view` /
  :func:`build_diagnostic_view` -- the machine-enforced refusal. Building a
  runtime supply view over ANY M1 (reference/annotation-derived,
  ceiling-only) entry raises :class:`LeakageTierViolation` rather than
  silently dropping it, so a caller cannot "fix" the refusal by catching and
  ignoring it without noticing that the view it wanted is empty and wrong.

A third, orthogonal axis (v2 delta, owner architecture ruling 2026-08-18
SS5.2): **speaker**. :func:`speaker_view` filters to one speaker's
introduced vocabulary; the glossary is speaker-conditioned via
``GlossaryEntry.introduced_by``.
"""

from __future__ import annotations

from typing import Sequence

from .models import GlossaryEntry, LeakageTier, ProvenanceTag


class LeakageTierViolation(RuntimeError):
    """Raised when a runtime supply view is requested over one or more
    Tier-M1 (ceiling/diagnostic-only) glossary entries. M1 entries are
    annotation/reference-derived (oracle/bias lists, corrected references,
    speaker-metadata name maps, GPT-over-gold lists, role/seen_type
    annotations) and must never reach a supply view a running episode
    could act on."""


def filter_by_provenance(entries: Sequence[GlossaryEntry], tag: ProvenanceTag) -> tuple[GlossaryEntry, ...]:
    """Keep only entries whose ``provenance`` equals ``tag``, preserving
    input order."""

    return tuple(e for e in entries if e.provenance == tag)


def speech_only(entries: Sequence[GlossaryEntry]) -> tuple[GlossaryEntry, ...]:
    """The speech-derived-only provenance factorization arm."""

    return filter_by_provenance(entries, ProvenanceTag.SPEECH_PASS)


def metadata_only(entries: Sequence[GlossaryEntry]) -> tuple[GlossaryEntry, ...]:
    """The metadata-only provenance factorization arm (the EGTA-analogue
    baseline -- a glossary built entirely from shipped meeting materials,
    never from the episode's own speech)."""

    return filter_by_provenance(entries, ProvenanceTag.METADATA)


def combined(entries: Sequence[GlossaryEntry]) -> tuple[GlossaryEntry, ...]:
    """The combined provenance arm: no provenance filter at all. The
    provenance claim (speech-only adds measurably over metadata-only) is
    licensed only by comparing this against :func:`speech_only` and
    :func:`metadata_only` on the SAME episode."""

    return tuple(entries)


def _reject_m1(entries: Sequence[GlossaryEntry]) -> None:
    offenders = [e.canonical_surface for e in entries if e.leakage_tier == LeakageTier.M1]
    if offenders:
        raise LeakageTierViolation(
            f"{len(offenders)} Tier-M1 (ceiling/diagnostic-only) entr"
            f"{'y' if len(offenders) == 1 else 'ies'} cannot enter a runtime "
            f"supply view: {offenders!r}"
        )


def build_runtime_supply_view(entries: Sequence[GlossaryEntry]) -> tuple[GlossaryEntry, ...]:
    """The ONLY sanctioned path from a glossary-entry sequence to something
    a running episode may actually supply to the core. Fail-closed: raises
    :class:`LeakageTierViolation` if any entry is Tier-M1, rather than
    silently filtering M1 out (a silent filter would let a caller who
    forgot to gate on tier ship an unintentionally-smaller-but-still-wrong
    view without ever finding out)."""

    _reject_m1(entries)
    return tuple(entries)


def build_diagnostic_view(entries: Sequence[GlossaryEntry]) -> tuple[GlossaryEntry, ...]:
    """The ceiling/diagnostic-only path: M1 entries ARE allowed here (an
    oracle-ceiling arm, or an offline diagnostic report, legitimately wants
    them) but this view must never be wired to anything the episode acts
    on -- callers that need the runtime guarantee must use
    :func:`build_runtime_supply_view` instead, never this function."""

    return tuple(entries)


def speaker_view(entries: Sequence[GlossaryEntry], speaker_id: str | None) -> tuple[GlossaryEntry, ...]:
    """Per-speaker vocabulary view (v2 delta): keep only entries whose
    ``introduced_by`` equals ``speaker_id``. Pass ``None`` to view the
    entries with no attributed introducing speaker (e.g. ``metadata``
    provenance, or speech-pass entries where speaker attribution was not
    available)."""

    return tuple(e for e in entries if e.introduced_by == speaker_id)


__all__ = [
    "LeakageTierViolation",
    "filter_by_provenance",
    "speech_only",
    "metadata_only",
    "combined",
    "build_runtime_supply_view",
    "build_diagnostic_view",
    "speaker_view",
]
