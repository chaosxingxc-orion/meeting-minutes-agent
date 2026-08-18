"""Data shapes for the glossary module.

Every entry carries a canonical surface, its raw variants, the chunk it
was first seen in, an evidence count, a **provenance tag** (where the
mention came from), a **leakage tier** (whether it may enter a runtime
supply view, or is ceiling/diagnostic only), and (v2 delta, owner
architecture ruling 2026-08-18 SS5.2) **introduced_by** -- the speaker
cluster/roster id whose speech first produced the entry's evidence, or
``None`` when the entry came from a provenance with no speaker axis
(e.g. ``metadata``) or the introducing speaker could not be attributed.
The glossary is speaker-conditioned: :func:`glossary.provenance.speaker_view`
filters an entry sequence down to one speaker's vocabulary. See
:mod:`.provenance` for the machine-enforced refusal that makes the
leakage tier binding rather than advisory.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ProvenanceTag(str, Enum):
    """Where a glossary entry's evidence came from."""

    SPEECH_PASS = "speech-pass"
    METADATA = "metadata"


class LeakageTier(str, Enum):
    """M0 = artifacts co-shipped with the audio as meeting materials
    (agendas, slides, press releases) -- runtime-admissible. M1 =
    annotation/reference-derived artifacts (oracle/bias lists, corrected
    references, speaker-metadata name maps, GPT-over-gold lists,
    role/seen_type annotations) -- ceiling/diagnostic only, never runtime
    supply."""

    M0 = "M0"
    M1 = "M1"


@dataclass(frozen=True)
class GlossaryEntry:
    canonical_surface: str
    variants: tuple[str, ...]
    first_seen_chunk: int
    evidence_count: int
    provenance: ProvenanceTag
    leakage_tier: LeakageTier
    introduced_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_surface": self.canonical_surface,
            "variants": list(self.variants),
            "first_seen_chunk": self.first_seen_chunk,
            "evidence_count": self.evidence_count,
            "provenance": self.provenance.value,
            "leakage_tier": self.leakage_tier.value,
            "introduced_by": self.introduced_by,
        }
