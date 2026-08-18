"""E4 -- glossary module.

Pipeline: extract (:mod:`.extract`) -> normalise (:mod:`.normalise`) ->
dedupe (:mod:`.dedupe`) -> gate (:mod:`.gate`), tied together for one
chunk by :mod:`.pipeline`. Cross-chunk carry is :mod:`.accumulate`. Every
entry carries a provenance tag and a machine-enforced leakage tier
(:mod:`.models`, :mod:`.provenance`). Arm switches are explicit
constructors in :mod:`.arms`. Carry accounting (per-chunk glossary size,
new-vs-carried counts, second-half coverage) is :mod:`.carry`.
"""

from __future__ import annotations

from .accumulate import merge_entries
from .arms import ArmKind, ArmPlan, deranged_arm, gated_arm, naive_raw_arm, no_carry_arm, scrambled_raw_arm, uniform_ungated_arm
from .carry import CarryReport, ChunkGlossarySnapshot, accumulate_glossary, carry_accounting, rank_terms_by_frequency, second_half_coverage
from .dedupe import Cluster, dedupe_candidates
from .extract import Candidate, CandidateExtractor, RuleBasedExtractor, extract_candidates
from .gate import GateConfig, gate_entries
from .models import GlossaryEntry, LeakageTier, ProvenanceTag
from .normalise import normalise_surface
from .pipeline import build_chunk_entries
from .provenance import (
    LeakageTierViolation,
    build_diagnostic_view,
    build_runtime_supply_view,
    combined,
    filter_by_provenance,
    metadata_only,
    speaker_view,
    speech_only,
)

__all__ = [
    "merge_entries",
    "ArmKind",
    "ArmPlan",
    "deranged_arm",
    "gated_arm",
    "naive_raw_arm",
    "no_carry_arm",
    "scrambled_raw_arm",
    "uniform_ungated_arm",
    "CarryReport",
    "ChunkGlossarySnapshot",
    "accumulate_glossary",
    "carry_accounting",
    "rank_terms_by_frequency",
    "second_half_coverage",
    "Cluster",
    "dedupe_candidates",
    "Candidate",
    "CandidateExtractor",
    "RuleBasedExtractor",
    "extract_candidates",
    "GateConfig",
    "gate_entries",
    "GlossaryEntry",
    "LeakageTier",
    "ProvenanceTag",
    "normalise_surface",
    "build_chunk_entries",
    "LeakageTierViolation",
    "build_diagnostic_view",
    "build_runtime_supply_view",
    "combined",
    "filter_by_provenance",
    "metadata_only",
    "speaker_view",
    "speech_only",
]
