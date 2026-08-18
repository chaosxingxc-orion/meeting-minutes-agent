"""Deterministic task-chunk planning (two-level design, ``docs/readiness/
2026-08-18-chunk-slice-granularity-analysis.md`` SS8.2).

:func:`build_chunk_plan` divides a sorted segment sequence into an ordered
sequence of task CHUNKS -- the unit of state consolidation and dispatch,
NEVER a transport unit (the transport unit is a slice, :mod:`.slicer`) --
bounded to ``[min_chunk_s, max_chunk_s]`` around a ``target_chunk_s``
target. A chunk boundary is never placed inside a segment (a segment is
never split). When the running chunk reaches the target, the boundary
snaps to the topic-segmentation mark closest to the target among the marks
that fall inside the segment that caused the crossing AND before the hard
``max_chunk_s`` cap; when no such mark is available (or none is
admissible, see :mod:`.leakage`) the boundary falls back to that segment's
own end time (the plain-duration fallback), still capped at
``max_chunk_s``. A trailing chunk shorter than ``min_chunk_s`` is merged
into its predecessor rather than emitted standalone.

``single_pass`` -- one chunk, no boundary decision at all -- is a
first-class plan kind, but it is gated behind an EXPLICIT opt-in
(``allow_single_pass=True``) plus a plan-time serving-context assertion
(:mod:`meeting_minutes_agent.context_budget`): 17-item change list item 3
requires this because the analysis found single-pass infeasible for every
one of the 18 AMI dev meetings at the locked serving config (SS7) -- it
must never be ``mode="auto"``'s silent default the way the old
``DEFAULT_WINDOW_CAP_S`` collapse allowed.
"""

from __future__ import annotations

from typing import Sequence

from ..context_budget import SlotContextConfig, assert_fits
from ..runreceipt import config_hash
from .constants import TASK_CHUNK_MAX_S, TASK_CHUNK_MIN_S, TASK_CHUNK_TARGET_S
from .leakage import BoundaryProvenance, assert_runtime_admissible
from .models import BoundarySource, Chunk, ChunkPlan, ChunkPlanKind, SegmentLike

_VALID_MODES = ("auto", "single_pass", "multi_chunk")


class SinglePassNotAdmittedError(ValueError):
    """``mode="single_pass"`` was requested without ``allow_single_pass=
    True``. 17-item change list item 3: single_pass must be selectable
    only explicitly, never ``mode="auto"``'s default -- the analysis found
    it infeasible for every one of the 18 AMI dev meetings at the locked
    serving config (SS7)."""


def _sorted_segments(segments: Sequence[SegmentLike]) -> list[SegmentLike]:
    return sorted(segments, key=lambda s: (s.start if s.start is not None else float("inf"), s.id))


def _plan_payload(
    meeting_id: str,
    kind: ChunkPlanKind,
    target_chunk_s: float,
    min_chunk_s: float,
    max_chunk_s: float,
    boundary_provenance: BoundaryProvenance,
    chunks: Sequence[Chunk],
) -> dict:
    return {
        "meeting_id": meeting_id,
        "kind": kind.value,
        "target_chunk_s": target_chunk_s,
        "min_chunk_s": min_chunk_s,
        "max_chunk_s": max_chunk_s,
        "boundary_provenance": boundary_provenance.value,
        "chunks": [c.to_dict() for c in chunks],
    }


def _finalize(
    meeting_id: str,
    kind: ChunkPlanKind,
    target_chunk_s: float,
    min_chunk_s: float,
    max_chunk_s: float,
    boundary_provenance: BoundaryProvenance,
    chunks: Sequence[Chunk],
) -> ChunkPlan:
    payload = _plan_payload(meeting_id, kind, target_chunk_s, min_chunk_s, max_chunk_s, boundary_provenance, chunks)
    return ChunkPlan(
        meeting_id=meeting_id,
        kind=kind,
        target_chunk_s=target_chunk_s,
        min_chunk_s=min_chunk_s,
        max_chunk_s=max_chunk_s,
        boundary_provenance=boundary_provenance,
        chunks=tuple(chunks),
        content_hash=config_hash(payload),
    )


def _renumber(chunks: Sequence[Chunk]) -> list[Chunk]:
    return [Chunk(idx, c.start, c.end, c.segment_ids, c.boundary_source) for idx, c in enumerate(chunks)]


def _merge_undersized_tail(chunks: list[Chunk], min_chunk_s: float) -> list[Chunk]:
    """A trailing chunk shorter than ``min_chunk_s`` is folded into its
    predecessor (design note, module docstring: "merge any topic shorter
    than 180s into its successor" applied to the walk's own leftover
    remainder -- its most common source of an undersized chunk). Never
    merges the ONLY chunk (nothing to merge into)."""

    if len(chunks) < 2:
        return chunks
    last = chunks[-1]
    if (last.end - last.start) >= min_chunk_s:
        return chunks
    prev = chunks[-2]
    merged = Chunk(
        index=prev.index,
        start=prev.start,
        end=last.end,
        segment_ids=prev.segment_ids + last.segment_ids,
        boundary_source=BoundarySource.FINAL,
    )
    return _renumber(chunks[:-2] + [merged])


def build_chunk_plan(
    segments: Sequence[SegmentLike],
    *,
    meeting_id: str = "",
    target_chunk_s: float = TASK_CHUNK_TARGET_S,
    min_chunk_s: float = TASK_CHUNK_MIN_S,
    max_chunk_s: float = TASK_CHUNK_MAX_S,
    topic_marks: Sequence[float] = (),
    boundary_provenance: BoundaryProvenance = BoundaryProvenance.SIGNAL,
    allow_oracle_boundaries: bool = False,
    mode: str = "auto",
    allow_single_pass: bool = False,
    slot_context: SlotContextConfig | None = None,
) -> ChunkPlan:
    """Build a :class:`ChunkPlan` from ``segments`` (E2's ``ResolvedMeeting``
    ``.transcript``, or a plain sequence of :class:`~.models.Segment`).

    ``mode``:
      - ``"auto"`` (default) and ``"multi_chunk"``: both always walk the
        chunk-packing loop -- ``"auto"`` NEVER collapses to ``single_pass``
        (unlike the old ``DEFAULT_WINDOW_CAP_S``-gated design; item 3).
      - ``"single_pass"``: force one chunk covering the whole span.
        Requires ``allow_single_pass=True`` (else
        :class:`SinglePassNotAdmittedError`) and passes a plan-time
        serving-context assertion against ``slot_context`` (else
        :class:`~meeting_minutes_agent.context_budget.SlotContextExceededError`)
        -- both fail-closed, at plan time.

    ``topic_marks`` are gated by ``boundary_provenance``/
    ``allow_oracle_boundaries`` (:mod:`.leakage`): a Tier-M1 provenance
    (e.g. AMI/ICSI gold topic marks) with ``allow_oracle_boundaries=False``
    raises rather than silently using the marks.
    """

    if target_chunk_s <= 0 or min_chunk_s <= 0 or max_chunk_s <= 0:
        raise ValueError(
            "target_chunk_s/min_chunk_s/max_chunk_s must all be positive, got "
            f"{target_chunk_s}, {min_chunk_s}, {max_chunk_s}"
        )
    if not (min_chunk_s <= target_chunk_s <= max_chunk_s):
        raise ValueError(
            "chunk bounds must satisfy min_chunk_s <= target_chunk_s <= max_chunk_s, got "
            f"min={min_chunk_s}, target={target_chunk_s}, max={max_chunk_s}"
        )
    if mode not in _VALID_MODES:
        raise ValueError(f"unknown mode: {mode!r} (expected one of {_VALID_MODES})")
    if topic_marks:
        assert_runtime_admissible(
            boundary_provenance, allow_oracle=allow_oracle_boundaries, label="topic_marks provenance"
        )

    ordered = _sorted_segments(segments)
    if not ordered:
        return _finalize(
            meeting_id, ChunkPlanKind.SINGLE_PASS, target_chunk_s, min_chunk_s, max_chunk_s, boundary_provenance, ()
        )

    span_start = ordered[0].start if ordered[0].start is not None else 0.0
    span_end = span_start
    for s in ordered:
        end = s.end if s.end is not None else s.start
        if end is not None and end > span_end:
            span_end = end
    total_span = span_end - span_start

    if mode == "single_pass":
        if not allow_single_pass:
            raise SinglePassNotAdmittedError(
                f"mode='single_pass' requires allow_single_pass=True (meeting {meeting_id!r}, "
                f"{total_span}s of segments) -- single_pass must be selectable only explicitly, "
                "never mode='auto''s default (17-item change list item 3; "
                "docs/readiness/2026-08-18-chunk-slice-granularity-analysis.md SS7 found it "
                "infeasible for every one of the 18 AMI dev meetings at the locked serving config)"
            )
        context = (slot_context or SlotContextConfig()).validate()
        assert_fits(total_span, context, label=f"single_pass plan for meeting {meeting_id!r}")
        chunk = Chunk(
            index=0,
            start=span_start,
            end=span_end,
            segment_ids=tuple(s.id for s in ordered),
            boundary_source=BoundarySource.SINGLE_PASS,
        )
        return _finalize(
            meeting_id,
            ChunkPlanKind.SINGLE_PASS,
            target_chunk_s,
            min_chunk_s,
            max_chunk_s,
            boundary_provenance,
            (chunk,),
        )

    # mode in ("auto", "multi_chunk"): always walk the packing loop --
    # "auto" never silently collapses to single_pass (module docstring).
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

        if elapsed >= target_chunk_s and not is_last:
            hard_cap_time = chunk_start_time + max_chunk_s
            target_time = chunk_start_time + target_chunk_s
            eligible_marks = [m for m in marks if chunk_start_time < m <= min(seg_end, hard_cap_time)]
            if eligible_marks:
                boundary_time = min(eligible_marks, key=lambda m: abs(m - target_time))
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
            elif seg_end <= hard_cap_time:
                boundary_time = seg_end
                source = BoundarySource.PLAIN_DURATION
                c = i
            elif i > chunk_start_idx:
                # This segment alone would push the chunk past max_chunk_s
                # and no mark rescues it: cut at the END of the PREVIOUS
                # segment instead (the "a segment is never split" invariant
                # still holds), so this segment opens the NEXT chunk.
                prev_end = ordered[i - 1].end
                boundary_time = prev_end if prev_end is not None else chunk_start_time
                source = BoundarySource.PLAIN_DURATION
                c = i - 1
            else:
                # A single segment already exceeds max_chunk_s on its own;
                # accepted whole (nothing shorter to cut to without
                # splitting it).
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

    chunks = _merge_undersized_tail(chunks, min_chunk_s)

    return _finalize(
        meeting_id, ChunkPlanKind.MULTI_CHUNK, target_chunk_s, min_chunk_s, max_chunk_s, boundary_provenance, chunks
    )


__all__ = ["SinglePassNotAdmittedError", "build_chunk_plan"]
