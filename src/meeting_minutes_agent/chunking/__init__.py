"""E3 -- chunking engine.

Deterministic chunk planning under a configurable window cap, with
boundaries snapped to topic-segmentation marks when available and a
plain-duration fallback otherwise (:mod:`.planner`); an episode-local,
append-only inter-chunk glossary-state interface (:mod:`.state`); and
adapters from E2's ``ResolvedMeeting`` (:mod:`.adapters`).
"""

from __future__ import annotations

from .adapters import build_chunk_plan_for_resolved_meeting, topic_marks_from_resolved_meeting
from .models import BoundarySource, Chunk, ChunkPlan, ChunkPlanKind, Segment, SegmentLike
from .planner import DEFAULT_WINDOW_CAP_S, build_chunk_plan
from .state import GlossaryStateLog, StateEntry

__all__ = [
    "BoundarySource",
    "Chunk",
    "ChunkPlan",
    "ChunkPlanKind",
    "Segment",
    "SegmentLike",
    "DEFAULT_WINDOW_CAP_S",
    "build_chunk_plan",
    "build_chunk_plan_for_resolved_meeting",
    "topic_marks_from_resolved_meeting",
    "GlossaryStateLog",
    "StateEntry",
]
