"""Tests for :mod:`meeting_minutes_agent.chunking.planner`: single-pass
selection, topic-mark boundary snapping, the plain-duration fallback,
determinism, and the segment-partition invariant."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.chunking.models import BoundarySource, ChunkPlanKind, Segment
from meeting_minutes_agent.chunking.planner import build_chunk_plan

from .fixtures import (
    long_meeting_segments,
    long_meeting_segments_two_crossings,
    long_meeting_topic_marks,
    short_meeting_segments,
    two_crossings_topic_marks,
)


def test_short_meeting_is_single_pass_in_auto_mode():
    segs = short_meeting_segments()
    plan = build_chunk_plan(segs, meeting_id="m1", window_cap_s=2400.0)

    assert plan.kind is ChunkPlanKind.SINGLE_PASS
    assert len(plan.chunks) == 1
    chunk = plan.chunks[0]
    assert chunk.boundary_source is BoundarySource.SINGLE_PASS
    assert chunk.start == 0.0
    assert chunk.end == 1080.0
    assert chunk.segment_ids == tuple(s.id for s in segs)


def test_empty_segments_gives_empty_single_pass_plan():
    plan = build_chunk_plan([], meeting_id="empty")
    assert plan.kind is ChunkPlanKind.SINGLE_PASS
    assert plan.chunks == ()


def test_single_crossing_snaps_to_topic_mark():
    segs = long_meeting_segments()
    marks = long_meeting_topic_marks()
    plan = build_chunk_plan(segs, meeting_id="m2", window_cap_s=2400.0, topic_marks=marks)

    assert plan.kind is ChunkPlanKind.MULTI_CHUNK
    assert len(plan.chunks) == 2

    c0, c1 = plan.chunks
    assert c0.index == 0
    assert c0.start == 0.0
    assert c0.end == 2350.0
    assert c0.boundary_source is BoundarySource.TOPIC_MARK
    assert c0.segment_ids == ("s0", "s1", "s2", "s3")

    assert c1.index == 1
    assert c1.start == 2350.0
    assert c1.end == 4200.0
    assert c1.boundary_source is BoundarySource.FINAL
    assert c1.segment_ids == ("s4", "s5", "s6")


def test_two_crossings_snap_then_fall_back_to_plain_duration():
    segs = long_meeting_segments_two_crossings()
    marks = two_crossings_topic_marks()
    plan = build_chunk_plan(segs, meeting_id="m3", window_cap_s=2400.0, topic_marks=marks)

    assert plan.kind is ChunkPlanKind.MULTI_CHUNK
    assert len(plan.chunks) == 3

    c0, c1, c2 = plan.chunks
    assert c0.end == 2350.0
    assert c0.boundary_source is BoundarySource.TOPIC_MARK
    assert c0.segment_ids == ("s0", "s1", "s2", "s3")

    assert c1.start == 2350.0
    assert c1.end == 4800.0
    assert c1.boundary_source is BoundarySource.PLAIN_DURATION
    assert c1.segment_ids == ("s4", "s5", "s6", "s7")

    assert c2.start == 4800.0
    assert c2.end == 6000.0
    assert c2.boundary_source is BoundarySource.FINAL
    assert c2.segment_ids == ("s8", "s9")


def test_a_segment_is_never_split_across_chunks():
    segs = long_meeting_segments_two_crossings()
    marks = two_crossings_topic_marks()
    plan = build_chunk_plan(segs, meeting_id="m3", window_cap_s=2400.0, topic_marks=marks)

    seen: list[str] = []
    for chunk in plan.chunks:
        seen.extend(chunk.segment_ids)
    assert seen == [s.id for s in segs]  # every id exactly once, in order -- a clean partition


def test_mode_single_pass_forces_one_chunk_even_over_the_cap():
    segs = long_meeting_segments()
    plan = build_chunk_plan(segs, meeting_id="m4", window_cap_s=2400.0, mode="single_pass")

    assert plan.kind is ChunkPlanKind.SINGLE_PASS
    assert len(plan.chunks) == 1
    assert plan.chunks[0].boundary_source is BoundarySource.SINGLE_PASS
    assert plan.chunks[0].segment_ids == tuple(s.id for s in segs)


def test_mode_multi_chunk_forces_the_walk_even_under_the_cap():
    segs = short_meeting_segments()
    plan = build_chunk_plan(segs, meeting_id="m5", window_cap_s=2400.0, mode="multi_chunk")

    # Still collapses to one chunk (nothing crosses the cap), but the KIND
    # and boundary_source distinguish this from the auto-mode single_pass
    # plan for the identical segment set.
    assert plan.kind is ChunkPlanKind.MULTI_CHUNK
    assert len(plan.chunks) == 1
    assert plan.chunks[0].boundary_source is BoundarySource.FINAL


def test_unsorted_input_is_sorted_before_planning():
    segs = short_meeting_segments()
    reversed_segs = tuple(reversed(segs))
    plan_sorted = build_chunk_plan(segs, meeting_id="m6")
    plan_reversed = build_chunk_plan(reversed_segs, meeting_id="m6")
    assert plan_sorted == plan_reversed


def test_determinism_same_input_same_hash_and_equal_plan():
    segs = long_meeting_segments_two_crossings()
    marks = two_crossings_topic_marks()
    plan_a = build_chunk_plan(segs, meeting_id="m7", window_cap_s=2400.0, topic_marks=marks)
    plan_b = build_chunk_plan(segs, meeting_id="m7", window_cap_s=2400.0, topic_marks=marks)

    assert plan_a == plan_b
    assert plan_a.content_hash == plan_b.content_hash
    assert len(plan_a.content_hash) == 64  # sha256 hex digest


def test_content_hash_changes_with_window_cap():
    segs = long_meeting_segments_two_crossings()
    marks = two_crossings_topic_marks()
    plan_a = build_chunk_plan(segs, meeting_id="m8", window_cap_s=2400.0, topic_marks=marks)
    plan_b = build_chunk_plan(segs, meeting_id="m8", window_cap_s=1800.0, topic_marks=marks)
    assert plan_a.content_hash != plan_b.content_hash


def test_window_cap_must_be_positive():
    with pytest.raises(ValueError):
        build_chunk_plan(short_meeting_segments(), window_cap_s=0.0)
    with pytest.raises(ValueError):
        build_chunk_plan(short_meeting_segments(), window_cap_s=-1.0)


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        build_chunk_plan(short_meeting_segments(), mode="bogus")


def test_to_dict_roundtrip_shapes():
    segs = short_meeting_segments()
    plan = build_chunk_plan(segs, meeting_id="m9")
    d = plan.to_dict()
    assert d["meeting_id"] == "m9"
    assert d["kind"] == "single_pass"
    assert d["window_cap_s"] == 2400.0
    assert len(d["chunks"]) == 1
    assert d["chunks"][0]["boundary_source"] == "single_pass"
    assert d["content_hash"] == plan.content_hash


def test_segment_protocol_accepts_plain_segment_directly():
    # The Segment dataclass itself is used as SegmentLike input elsewhere
    # in this file; this test just pins that no adapter is required.
    seg = Segment("x0", "A", 0.0, 10.0, "hi")
    plan = build_chunk_plan([seg], meeting_id="solo")
    assert plan.chunks[0].segment_ids == ("x0",)
