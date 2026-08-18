"""Deterministic chunk planning.

:func:`build_chunk_plan` divides a sorted segment sequence into an ordered
sequence of chunks under ``window_cap_s`` (default ~40 minutes = 2400 s).
A chunk boundary is never placed inside a segment (a segment is never
split). When the running chunk crosses the window cap, the boundary snaps
to the topic-segmentation mark closest to the cap point among the marks
that fall inside the segment that caused the crossing; when no such mark
is available the boundary falls back to that segment's own end time (the
plain-duration fallback). If the whole episode already fits under the cap,
the plan is ``single_pass`` -- one chunk, no boundary decision needed at
all.
"""

from __future__ import annotations

from typing import Sequence

from ..runreceipt import config_hash
from .models import BoundarySource, Chunk, ChunkPlan, ChunkPlanKind, SegmentLike

DEFAULT_WINDOW_CAP_S = 2400.0  # 40 minutes
_VALID_MODES = ("auto", "single_pass", "multi_chunk")


def _sorted_segments(segments: Sequence[SegmentLike]) -> list[SegmentLike]:
    return sorted(segments, key=lambda s: (s.start if s.start is not None else float("inf"), s.id))


def _plan_payload(meeting_id: str, kind: ChunkPlanKind, window_cap_s: float, chunks: Sequence[Chunk]) -> dict:
    return {
        "meeting_id": meeting_id,
        "kind": kind.value,
        "window_cap_s": window_cap_s,
        "chunks": [c.to_dict() for c in chunks],
    }


def _finalize(meeting_id: str, kind: ChunkPlanKind, window_cap_s: float, chunks: Sequence[Chunk]) -> ChunkPlan:
    payload = _plan_payload(meeting_id, kind, window_cap_s, chunks)
    return ChunkPlan(
        meeting_id=meeting_id,
        kind=kind,
        window_cap_s=window_cap_s,
        chunks=tuple(chunks),
        content_hash=config_hash(payload),
    )


def build_chunk_plan(
    segments: Sequence[SegmentLike],
    *,
    meeting_id: str = "",
    window_cap_s: float = DEFAULT_WINDOW_CAP_S,
    topic_marks: Sequence[float] = (),
    mode: str = "auto",
) -> ChunkPlan:
    """Build a :class:`ChunkPlan` from ``segments`` (E2's ``ResolvedMeeting``
    ``.transcript``, or a plain sequence of :class:`~.models.Segment`).

    ``mode``:
      - ``"auto"`` (default): ``single_pass`` if the episode's total span
        already fits under ``window_cap_s``, ``multi_chunk`` otherwise.
      - ``"single_pass"``: force one chunk regardless of duration -- the
        registered single-pass control arm.
      - ``"multi_chunk"``: force the chunking walk even if it would
        collapse to one chunk.
    """

    if window_cap_s <= 0:
        raise ValueError("window_cap_s must be positive")
    if mode not in _VALID_MODES:
        raise ValueError(f"unknown mode: {mode!r} (expected one of {_VALID_MODES})")

    ordered = _sorted_segments(segments)
    if not ordered:
        return _finalize(meeting_id, ChunkPlanKind.SINGLE_PASS, window_cap_s, ())

    span_start = ordered[0].start if ordered[0].start is not None else 0.0
    span_end = span_start
    for s in ordered:
        end = s.end if s.end is not None else s.start
        if end is not None and end > span_end:
            span_end = end
    total_span = span_end - span_start

    if mode == "single_pass" or (mode == "auto" and total_span <= window_cap_s):
        chunk = Chunk(
            index=0,
            start=span_start,
            end=span_end,
            segment_ids=tuple(s.id for s in ordered),
            boundary_source=BoundarySource.SINGLE_PASS,
        )
        return _finalize(meeting_id, ChunkPlanKind.SINGLE_PASS, window_cap_s, (chunk,))

    marks = sorted({m for m in topic_marks if m is not None})

    chunks: list[Chunk] = []
    chunk_start_idx = 0
    chunk_start_time = span_start
    chunk_idx = 0
    i = 0
    n = len(ordered)
    while i < n:
        seg = ordered[i]
        seg_end = seg.end if seg.end is not None else (seg.start if seg.start is not None else chunk_start_time)
        elapsed = seg_end - chunk_start_time
        is_last = i == n - 1

        if elapsed >= window_cap_s and not is_last:
            target = chunk_start_time + window_cap_s
            eligible_marks = [m for m in marks if chunk_start_time < m <= seg_end]
            if eligible_marks:
                boundary_time = min(eligible_marks, key=lambda m: abs(m - target))
                source = BoundarySource.TOPIC_MARK
                c = chunk_start_idx - 1
                for idx in range(chunk_start_idx, i + 1):
                    start = ordered[idx].start
                    if start is not None and start < boundary_time:
                        c = idx
                    else:
                        break
                if c < chunk_start_idx:
                    c = chunk_start_idx  # never emit an empty chunk
            else:
                boundary_time = seg_end
                source = BoundarySource.PLAIN_DURATION
                c = i

            chunk_ids = tuple(ordered[idx].id for idx in range(chunk_start_idx, c + 1))
            chunks.append(Chunk(chunk_idx, chunk_start_time, boundary_time, chunk_ids, source))
            chunk_idx += 1
            chunk_start_idx = c + 1
            chunk_start_time = boundary_time
            i = c  # the loop's `i += 1` below resumes exactly at the new chunk's first segment

        i += 1

    if chunk_start_idx < n:
        tail_ids = tuple(ordered[idx].id for idx in range(chunk_start_idx, n))
        chunks.append(Chunk(chunk_idx, chunk_start_time, span_end, tail_ids, BoundarySource.FINAL))

    return _finalize(meeting_id, ChunkPlanKind.MULTI_CHUNK, window_cap_s, chunks)
