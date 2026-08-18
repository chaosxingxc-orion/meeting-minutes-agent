"""Shared fixtures for the ``supply`` module's tests."""

from __future__ import annotations

from meeting_minutes_agent.glossary.models import GlossaryEntry, LeakageTier, ProvenanceTag
from meeting_minutes_agent.state.episode import EpisodeState
from meeting_minutes_agent.state.models import SpeakerEvidenceSource


def glossary_entry(
    surface: str,
    *,
    variants: tuple[str, ...] | None = None,
    chunk: int = 0,
    evidence: int = 2,
    provenance: ProvenanceTag = ProvenanceTag.SPEECH_PASS,
    tier: LeakageTier = LeakageTier.M0,
    introduced_by: str | None = None,
) -> GlossaryEntry:
    return GlossaryEntry(
        canonical_surface=surface,
        variants=variants if variants is not None else (surface,),
        first_seen_chunk=chunk,
        evidence_count=evidence,
        provenance=provenance,
        leakage_tier=tier,
        introduced_by=introduced_by,
    )


# Rank order under glossary.carry.rank_terms_by_frequency (evidence desc,
# first_seen_chunk asc, canonical_surface asc) is, by construction:
# Alpha (5) > Beta (3, chunk 0) > Gamma (3, chunk 1).
ALPHA = glossary_entry("Alpha", chunk=0, evidence=5)
BETA = glossary_entry("Beta", variants=("Beta", "B."), chunk=0, evidence=3)
GAMMA = glossary_entry("Gamma", chunk=1, evidence=3)


def state_with_three_terms_and_three_speakers() -> EpisodeState:
    state = EpisodeState().with_glossary_chunk([ALPHA, BETA, GAMMA])
    state = state.bind_speaker(cluster_id="S3", roster_name="Carol", source=SpeakerEvidenceSource.ROSTER_MATCH, chunk=0, quote="q3")
    state = state.bind_speaker(cluster_id="S1", roster_name="Alice", source=SpeakerEvidenceSource.SELF_INTRODUCTION, chunk=0, quote="q1")
    state = state.bind_speaker(cluster_id="S2", roster_name="Bob", source=SpeakerEvidenceSource.ROSTER_MATCH, chunk=1, quote="q2")
    return state
