"""Data shapes for the chunking engine.

A :class:`ChunkPlan` divides a meeting's segment sequence into an ordered
list of :class:`Chunk`\\ s under a configurable duration cap, with
boundaries snapped to topic-segmentation marks when available and a
plain-duration fallback otherwise (see :mod:`.planner`). ``single_pass`` is
a first-class plan kind, not merely a one-chunk special case of
multi-chunk mode: the registered single-pass control arm (deep-check
synthesis SS3.2) needs to select "no chunking" explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable


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
    window_cap_s: float
    chunks: tuple[Chunk, ...]
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "kind": self.kind.value,
            "window_cap_s": self.window_cap_s,
            "chunks": [c.to_dict() for c in self.chunks],
            "content_hash": self.content_hash,
        }
