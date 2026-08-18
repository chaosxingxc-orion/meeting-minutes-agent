"""Shared fixtures for the ``state`` module's tests."""

from __future__ import annotations

from meeting_minutes_agent.glossary.models import GlossaryEntry, LeakageTier, ProvenanceTag


def glossary_entry(
    surface: str,
    *,
    chunk: int = 0,
    evidence: int = 2,
    provenance: ProvenanceTag = ProvenanceTag.SPEECH_PASS,
    tier: LeakageTier = LeakageTier.M0,
    introduced_by: str | None = None,
) -> GlossaryEntry:
    return GlossaryEntry(
        canonical_surface=surface,
        variants=(surface,),
        first_seen_chunk=chunk,
        evidence_count=evidence,
        provenance=provenance,
        leakage_tier=tier,
        introduced_by=introduced_by,
    )
