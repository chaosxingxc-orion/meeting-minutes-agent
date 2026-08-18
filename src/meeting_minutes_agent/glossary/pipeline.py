"""Ties one chunk's REVISE stage together: extract -> normalise (inside
dedupe) -> dedupe -> gate.

:func:`build_chunk_entries` is the canonical ("gated") REVISE path for one
chunk. It is deliberately the composition of the four already-separately-
testable stage functions -- no logic lives here beyond wiring -- so the six
registered arms (:mod:`.arms`) can each swap out or skip a stage while
still sharing the same :class:`~.models.GlossaryEntry` construction step.
"""

from __future__ import annotations

from typing import Sequence

from .dedupe import Cluster, dedupe_candidates
from .extract import Candidate, CandidateExtractor, RuleBasedExtractor
from .gate import GateConfig, gate_entries
from .models import GlossaryEntry, LeakageTier, ProvenanceTag


def cluster_to_entry(
    cluster: Cluster,
    *,
    chunk_index: int,
    provenance: ProvenanceTag,
    leakage_tier: LeakageTier,
    introduced_by: str | None = None,
) -> GlossaryEntry:
    """Attach one chunk's provenance/tier/speaker context to a dedupe
    :class:`~.dedupe.Cluster`, producing a fully-formed
    :class:`~.models.GlossaryEntry`."""

    return GlossaryEntry(
        canonical_surface=cluster.canonical_surface,
        variants=cluster.variants,
        first_seen_chunk=chunk_index,
        evidence_count=cluster.evidence_count,
        provenance=provenance,
        leakage_tier=leakage_tier,
        introduced_by=introduced_by,
    )


def build_chunk_entries(
    text: str,
    *,
    chunk_index: int,
    provenance: ProvenanceTag = ProvenanceTag.SPEECH_PASS,
    leakage_tier: LeakageTier = LeakageTier.M0,
    introduced_by: str | None = None,
    extractor: CandidateExtractor | None = None,
    gate_config: GateConfig | None = None,
) -> tuple[GlossaryEntry, ...]:
    """The canonical gated REVISE path for one chunk's transcript text:
    extract candidates -> dedupe (which normalises internally) -> attach
    chunk context -> gate. This is the ``gated`` arm's per-chunk body; see
    :mod:`.arms` for the other five registered REVISE-stage variants.

    ``extractor`` defaults to :class:`~.extract.RuleBasedExtractor`
    (min_repeats=2). ``gate_config`` defaults to
    ``GateConfig(min_evidence=2)`` -- no repetition or inventory cap.
    """

    if extractor is None:
        extractor = RuleBasedExtractor()
    if gate_config is None:
        gate_config = GateConfig(min_evidence=2)

    candidates: Sequence[Candidate] = extractor.extract(text)
    clusters = dedupe_candidates(candidates)
    entries = tuple(
        cluster_to_entry(
            c,
            chunk_index=chunk_index,
            provenance=provenance,
            leakage_tier=leakage_tier,
            introduced_by=introduced_by,
        )
        for c in clusters
    )
    return gate_entries(entries, gate_config)


__all__ = ["build_chunk_entries", "cluster_to_entry"]
