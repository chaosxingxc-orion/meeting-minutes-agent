"""Adapters from E2's ``ResolvedMeeting`` into chunking inputs.

``ResolvedMeeting.transcript`` (a tuple of ``Utterance``) already satisfies
:class:`~.models.SegmentLike` structurally (``id``/``speaker``/``start``/
``end``/``text``), so it needs no conversion to pass to
:func:`~.planner.build_chunk_plan` directly -- only the topic-mark
extraction below is genuinely adapter work.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from .models import ChunkPlan

if TYPE_CHECKING:
    from ..corpora.nxt.models import ResolvedMeeting, Topic


def topic_marks_from_resolved_meeting(resolved: "ResolvedMeeting") -> tuple[float, ...]:
    """Flatten every topic node's (including nested children's) ``start``
    time into a sorted, deduplicated tuple of candidate chunk-boundary
    marks."""

    marks: list[float] = []

    def walk(topics: Sequence["Topic"]) -> None:
        for t in topics:
            if t.start is not None:
                marks.append(t.start)
            walk(t.children)

    walk(resolved.topics)
    return tuple(sorted(set(marks)))


def build_chunk_plan_for_resolved_meeting(
    resolved: "ResolvedMeeting",
    *,
    window_cap_s: float = 2400.0,
    mode: str = "auto",
) -> ChunkPlan:
    """Convenience wrapper: chunk-plan a whole ``ResolvedMeeting``, using
    its topic tree (AMI/ICSI topic segmentation, or MeetingBank Legistar
    bill boundaries once modelled the same way) for boundary snapping."""

    from .planner import build_chunk_plan

    marks = topic_marks_from_resolved_meeting(resolved)
    return build_chunk_plan(
        resolved.transcript,
        meeting_id=resolved.meeting_id,
        window_cap_s=window_cap_s,
        topic_marks=marks,
        mode=mode,
    )
