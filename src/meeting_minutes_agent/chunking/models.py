"""Data shapes for the chunking engine.

A :class:`ChunkPlan` divides a meeting's segment sequence into an ordered
list of :class:`Chunk`\\ s -- the STATE/DISPATCH unit, bounded to
``[min_chunk_s, max_chunk_s]`` around a ``target_chunk_s`` target and NEVER
a transport unit (``docs/readiness/2026-08-18-chunk-slice-granularity-
analysis.md`` SS8.2; the transport unit is a slice, :mod:`.slicer`) -- with
boundaries snapped to topic-segmentation marks when admissible (see
:mod:`.leakage`) and a plain-duration fallback otherwise (see
:mod:`.planner`). ``single_pass`` is a first-class plan kind, not merely a
one-chunk special case of multi-chunk mode, but it is gated behind an
explicit opt-in and a plan-time serving-context assertion (:mod:`.planner`)
-- the analysis found it infeasible for every one of the 18 AMI dev
meetings at the locked serving config (SS7), so it must never be the
``mode="auto"`` default.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from .leakage import BoundaryProvenance


@runtime_checkable
class SegmentLike(Protocol):
    """Structural shape a chunk-plan input must satisfy. This module's own
    :class:`Segment` and E2's ``ResolvedMeeting`` ``Utterance``
    (``corpora.nxt.models.Utterance``) both already match this shape --
    either can be passed to :func:`~.planner.build_chunk_plan` directly, no
    adapter required for the plain-segment-list case."""

    id: str
    speaker: str
    start: float | None
    end: float | None
    text: str


@dataclass(frozen=True)
class Segment:
    """A plain speaker-attributed span: the minimal chunking input when no
    E2 ``ResolvedMeeting`` is available."""

    id: str
    speaker: str
    start: float
    end: float
    text: str


class ChunkPlanKind(str, Enum):
    SINGLE_PASS = "single_pass"
    MULTI_CHUNK = "multi_chunk"


class BoundarySource(str, Enum):
    TOPIC_MARK = "topic_mark"
    PLAIN_DURATION = "plain_duration"
    SINGLE_PASS = "single_pass"
    FINAL = "final"


@dataclass(frozen=True)
class Chunk:
    index: int
    start: float
    end: float
    segment_ids: tuple[str, ...]
    boundary_source: BoundarySource

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "start": self.start,
            "end": self.end,
            "segment_ids": list(self.segment_ids),
            "boundary_source": self.boundary_source.value,
        }


@dataclass(frozen=True)
class ChunkPlan:
    meeting_id: str
    kind: ChunkPlanKind
    target_chunk_s: float
    min_chunk_s: float
    max_chunk_s: float
    boundary_provenance: BoundaryProvenance
    chunks: tuple[Chunk, ...]
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "kind": self.kind.value,
            "target_chunk_s": self.target_chunk_s,
            "min_chunk_s": self.min_chunk_s,
            "max_chunk_s": self.max_chunk_s,
            "boundary_provenance": self.boundary_provenance.value,
            "chunks": [c.to_dict() for c in self.chunks],
            "content_hash": self.content_hash,
        }
