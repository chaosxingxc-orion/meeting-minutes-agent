"""The six registered REVISE-stage arms (deep-check synthesis SS3.2; backbone
design SS1: "Registered experiment arms are switches on exactly two joints:
the REVISE stage ... and the INGEST provenance filter").

Each arm constructor is the per-chunk REVISE body for one registered
control condition, built by skipping or perturbing stages of the same
extract -> normalise -> dedupe -> gate pipeline :func:`~.pipeline.build_chunk_entries`
runs in full:

- **gated** -- the full pipeline: extract, normalise+dedupe, gate. The
  target condition.
- **naive-raw** -- extract only; every raw candidate occurrence becomes its
  own unnormalised, unmerged, ungated entry (evidence_count=1). The
  arXiv 2511.18774 "naive" analogue: an unfiltered first pass re-injected
  as-is.
- **scrambled-raw** -- naive-raw's exact entry set, with presentation order
  deterministically shuffled by ``seed``. The de-sequentialization control:
  isolates whether raw-arm effects come from the (unordered) content or
  from incidental temporal/order cues.
- **uniform-ungated** -- extract, normalise+dedupe (a CLEAN candidate list,
  duplicates merged) but no gate stage, and every entry's evidence count is
  reset to 1 ("uniform" -- the frequency signal the gate would otherwise
  rank on is erased). Isolates the gate stage's own contribution, holding
  list cleanliness constant (EGTA A.6: un-gated hurts even with clean
  lists).
- **deranged** -- runs the full gated pipeline, then permutes which
  entry's variants/evidence/introduced_by go with which entry's canonical
  surface (a fixed-point-free permutation -- see :func:`_derange`), so the
  result is structurally a well-formed gated glossary but semantically
  wrong. The EGTA shuffled-memory-template analogue.
- **no-carry** -- per-chunk construction identical to ``gated``; the arm
  distinction is not in this constructor but in how a caller folds chunks
  together -- a no-carry episode never calls
  :func:`~.accumulate.merge_entries` across chunk boundaries, so each
  chunk's glossary is discarded at the next chunk (state reset per
  boundary). ``ArmKind.NO_CARRY`` on the returned plan is the signal a
  multi-chunk driver reads to skip carry.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from .dedupe import dedupe_candidates
from .extract import CandidateExtractor, RuleBasedExtractor
from .gate import GateConfig
from .models import GlossaryEntry, LeakageTier, ProvenanceTag
from .pipeline import build_chunk_entries


class ArmKind(str, Enum):
    GATED = "gated"
    NAIVE_RAW = "naive-raw"
    SCRAMBLED_RAW = "scrambled-raw"
    UNIFORM_UNGATED = "uniform-ungated"
    DERANGED = "deranged"
    NO_CARRY = "no-carry"


@dataclass(frozen=True)
class ArmPlan:
    kind: ArmKind
    chunk_index: int
    entries: tuple[GlossaryEntry, ...]
    seed: int | None = None


def gated_arm(
    text: str,
    *,
    chunk_index: int,
    provenance: ProvenanceTag = ProvenanceTag.SPEECH_PASS,
    leakage_tier: LeakageTier = LeakageTier.M0,
    introduced_by: str | None = None,
    extractor: CandidateExtractor | None = None,
    gate_config: GateConfig | None = None,
) -> ArmPlan:
    entries = build_chunk_entries(
        text,
        chunk_index=chunk_index,
        provenance=provenance,
        leakage_tier=leakage_tier,
        introduced_by=introduced_by,
        extractor=extractor,
        gate_config=gate_config,
    )
    return ArmPlan(ArmKind.GATED, chunk_index, entries)


def naive_raw_arm(
    text: str,
    *,
    chunk_index: int,
    provenance: ProvenanceTag = ProvenanceTag.SPEECH_PASS,
    leakage_tier: LeakageTier = LeakageTier.M0,
    introduced_by: str | None = None,
    extractor: CandidateExtractor | None = None,
) -> ArmPlan:
    extractor = extractor or RuleBasedExtractor()
    candidates = extractor.extract(text)
    entries = tuple(
        GlossaryEntry(
            canonical_surface=c.surface,
            variants=(c.surface,),
            first_seen_chunk=chunk_index,
            evidence_count=1,
            provenance=provenance,
            leakage_tier=leakage_tier,
            introduced_by=introduced_by,
        )
        for c in candidates
    )
    return ArmPlan(ArmKind.NAIVE_RAW, chunk_index, entries)


def scrambled_raw_arm(
    text: str,
    *,
    chunk_index: int,
    provenance: ProvenanceTag = ProvenanceTag.SPEECH_PASS,
    leakage_tier: LeakageTier = LeakageTier.M0,
    introduced_by: str | None = None,
    extractor: CandidateExtractor | None = None,
    seed: int = 0,
) -> ArmPlan:
    base = naive_raw_arm(
        text,
        chunk_index=chunk_index,
        provenance=provenance,
        leakage_tier=leakage_tier,
        introduced_by=introduced_by,
        extractor=extractor,
    ).entries
    scrambled = list(base)
    random.Random(seed).shuffle(scrambled)
    return ArmPlan(ArmKind.SCRAMBLED_RAW, chunk_index, tuple(scrambled), seed=seed)


def uniform_ungated_arm(
    text: str,
    *,
    chunk_index: int,
    provenance: ProvenanceTag = ProvenanceTag.SPEECH_PASS,
    leakage_tier: LeakageTier = LeakageTier.M0,
    introduced_by: str | None = None,
    extractor: CandidateExtractor | None = None,
) -> ArmPlan:
    extractor = extractor or RuleBasedExtractor()
    clusters = dedupe_candidates(extractor.extract(text))
    entries = tuple(
        GlossaryEntry(
            canonical_surface=c.canonical_surface,
            variants=c.variants,
            first_seen_chunk=chunk_index,
            evidence_count=1,
            provenance=provenance,
            leakage_tier=leakage_tier,
            introduced_by=introduced_by,
        )
        for c in clusters
    )
    return ArmPlan(ArmKind.UNIFORM_UNGATED, chunk_index, entries)


def _sattolo_cycle(n: int, rng: random.Random) -> list[int]:
    """A uniformly-random single n-cycle over ``range(n)`` -- a
    fixed-point-free permutation for n>=2 (Sattolo's algorithm)."""

    perm = list(range(n))
    for i in range(n - 1, 0, -1):
        j = rng.randrange(i)
        perm[i], perm[j] = perm[j], perm[i]
    return perm


def _derange(entries: Sequence[GlossaryEntry], seed: int) -> tuple[GlossaryEntry, ...]:
    """Keep each entry's own ``canonical_surface``/``first_seen_chunk``/
    ``provenance``/``leakage_tier`` (the term's identity and where it's
    allowed to be used), but swap in a DIFFERENT entry's
    ``variants``/``evidence_count``/``introduced_by`` (the term's
    evidence). Fewer than 2 entries cannot be deranged (no other entry to
    swap with) and are returned unchanged."""

    n = len(entries)
    if n < 2:
        return tuple(entries)
    perm = _sattolo_cycle(n, random.Random(seed))
    out = []
    for i, e in enumerate(entries):
        donor = entries[perm[i]]
        out.append(
            GlossaryEntry(
                canonical_surface=e.canonical_surface,
                variants=donor.variants,
                first_seen_chunk=e.first_seen_chunk,
                evidence_count=donor.evidence_count,
                provenance=e.provenance,
                leakage_tier=e.leakage_tier,
                introduced_by=donor.introduced_by,
            )
        )
    return tuple(out)


def deranged_arm(
    text: str,
    *,
    chunk_index: int,
    provenance: ProvenanceTag = ProvenanceTag.SPEECH_PASS,
    leakage_tier: LeakageTier = LeakageTier.M0,
    introduced_by: str | None = None,
    extractor: CandidateExtractor | None = None,
    gate_config: GateConfig | None = None,
    seed: int = 0,
) -> ArmPlan:
    clean = build_chunk_entries(
        text,
        chunk_index=chunk_index,
        provenance=provenance,
        leakage_tier=leakage_tier,
        introduced_by=introduced_by,
        extractor=extractor,
        gate_config=gate_config,
    )
    return ArmPlan(ArmKind.DERANGED, chunk_index, _derange(clean, seed), seed=seed)


def no_carry_arm(
    text: str,
    *,
    chunk_index: int,
    provenance: ProvenanceTag = ProvenanceTag.SPEECH_PASS,
    leakage_tier: LeakageTier = LeakageTier.M0,
    introduced_by: str | None = None,
    extractor: CandidateExtractor | None = None,
    gate_config: GateConfig | None = None,
) -> ArmPlan:
    entries = build_chunk_entries(
        text,
        chunk_index=chunk_index,
        provenance=provenance,
        leakage_tier=leakage_tier,
        introduced_by=introduced_by,
        extractor=extractor,
        gate_config=gate_config,
    )
    return ArmPlan(ArmKind.NO_CARRY, chunk_index, entries)


__all__ = [
    "ArmKind",
    "ArmPlan",
    "gated_arm",
    "naive_raw_arm",
    "scrambled_raw_arm",
    "uniform_ungated_arm",
    "deranged_arm",
    "no_carry_arm",
]
