"""Adapters from E2's ``ResolvedMeeting`` into chunking/slicing inputs.

``ResolvedMeeting.transcript`` (a tuple of ``Utterance``) already satisfies
:class:`~.models.SegmentLike` structurally (``id``/``speaker``/``start``/
``end``/``text``), so it needs no conversion to pass to
:func:`~.planner.build_chunk_plan` directly -- only the topic-mark and
turn-table extraction below is genuinely adapter work.

Both AMI/ICSI's topic-segmentation layer AND its diarization/turn (speaker-
segment) layer are MANUAL ANNOTATION of the evaluation material -- Tier-M1,
oracle/ceiling-only (:mod:`.leakage`). This module is where that fact is
enforced: :func:`build_chunk_plan_for_resolved_meeting` and
:func:`turn_table_from_resolved_meeting`'s callers default to NOT admitting
the gold layer, falling back to pure signal packing, per the owner ruling
"runtime chunk planning must fall back to signal-derived boundaries unless
a ceiling arm explicitly admits the gold topic layer" (extended, by the
2026-08-18 diarization-aware slicer amendment, to the turn layer).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from .leakage import BoundaryProvenance
from .models import ChunkPlan

if TYPE_CHECKING:
    from ..corpora.nxt.models import ResolvedMeeting, Topic
    from .slicer import TurnSpan


def topic_marks_from_resolved_meeting(resolved: "ResolvedMeeting") -> tuple[float, ...]:
    """Flatten every topic node's (including nested children's) ``start``
    time into a sorted, deduplicated tuple of candidate chunk-boundary
    marks. Pure extraction -- carries no admissibility decision of its own;
    see :func:`build_chunk_plan_for_resolved_meeting` for the gate."""

    marks: list[float] = []

    def walk(topics: Sequence["Topic"]) -> None:
        for t in topics:
            if t.start is not None:
                marks.append(t.start)
            walk(t.children)

    walk(resolved.topics)
    return tuple(sorted(set(marks)))


def turn_table_from_resolved_meeting(resolved: "ResolvedMeeting") -> tuple["TurnSpan", ...]:
    """The gold AMI/ICSI diarization/turn (speaker-segment) layer as a
    plain, source-agnostic turn table -- ``resolved.transcript`` IS that
    layer (each ``Utterance`` is already one speaker-attributed span with
    times). Pure extraction, sorted by start, dropping any utterance
    missing a start or end (a turn-aware slice plan needs concrete times).
    Pure extraction -- carries no admissibility decision of its own; see
    :func:`turn_table_provenance` and :mod:`.slicer`'s turn-aware mode for
    the gate."""

    from .slicer import TurnSpan

    turns = [
        TurnSpan(start=u.start, end=u.end, speaker=u.speaker)
        for u in resolved.transcript
        if u.start is not None and u.end is not None and u.end > u.start
    ]
    return tuple(sorted(turns, key=lambda t: (t.start, t.end)))


def turn_table_provenance() -> BoundaryProvenance:
    """The provenance tag :func:`turn_table_from_resolved_meeting`'s output
    always carries: AMI/ICSI's segment/dialogue-act layer is manual
    annotation of the evaluation material, Tier-M1 oracle-turn -- never
    signal-derived, regardless of caller intent."""

    return BoundaryProvenance.ORACLE_TURN


def build_chunk_plan_for_resolved_meeting(
    resolved: "ResolvedMeeting",
    *,
    target_chunk_s: float | None = None,
    min_chunk_s: float | None = None,
    max_chunk_s: float | None = None,
    mode: str = "auto",
    allow_oracle_topic: bool = False,
    **kwargs: object,
) -> ChunkPlan:
    """Convenience wrapper: chunk-plan a whole ``ResolvedMeeting``.

    ``allow_oracle_topic`` (default ``False``) is the ceiling-arm admission
    switch for AMI/ICSI's gold topic-segmentation layer: when ``False``
    (the default, correct for any headline arm), the gold marks are NOT
    forwarded at all -- the plan falls back to pure signal/plain-duration
    packing, exactly as if the meeting had no topic layer. Only when
    ``allow_oracle_topic=True`` (a declared oracle-ceiling arm) are the
    marks forwarded, tagged ``BoundaryProvenance.ORACLE_TOPIC``.
    """

    from .constants import TASK_CHUNK_MAX_S, TASK_CHUNK_MIN_S, TASK_CHUNK_TARGET_S
    from .planner import build_chunk_plan

    if allow_oracle_topic:
        marks = topic_marks_from_resolved_meeting(resolved)
        boundary_provenance = BoundaryProvenance.ORACLE_TOPIC
    else:
        marks = ()
        boundary_provenance = BoundaryProvenance.SIGNAL

    return build_chunk_plan(
        resolved.transcript,
        meeting_id=resolved.meeting_id,
        target_chunk_s=TASK_CHUNK_TARGET_S if target_chunk_s is None else target_chunk_s,
        min_chunk_s=TASK_CHUNK_MIN_S if min_chunk_s is None else min_chunk_s,
        max_chunk_s=TASK_CHUNK_MAX_S if max_chunk_s is None else max_chunk_s,
        topic_marks=marks,
        boundary_provenance=boundary_provenance,
        allow_oracle_boundaries=allow_oracle_topic,
        mode=mode,
        **kwargs,
    )


__all__ = [
    "topic_marks_from_resolved_meeting",
    "turn_table_from_resolved_meeting",
    "turn_table_provenance",
    "build_chunk_plan_for_resolved_meeting",
]
