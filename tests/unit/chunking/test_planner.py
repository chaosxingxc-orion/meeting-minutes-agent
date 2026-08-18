"""Tests for :mod:`meeting_minutes_agent.chunking.planner`: the task-chunk
walk under ``[min_chunk_s, target_chunk_s, max_chunk_s]``, topic-mark
boundary snapping (with its M1 leakage-tier gate), the plain-duration
fallback, the undersized-tail merge, determinism, the segment-partition
invariant, and the ``single_pass`` gate (explicit opt-in + plan-time
serving-context assertion)."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.chunking.leakage import BoundaryLeakageTierViolation, BoundaryProvenance
from meeting_minutes_agent.chunking.models import BoundarySource, ChunkPlanKind, Segment
from meeting_minutes_agent.chunking.planner import SinglePassNotAdmittedError, build_chunk_plan
from meeting_minutes_agent.context_budget import SlotContextConfig, SlotContextExceededError

from .fixtures import (
    long_meeting_segments,
    long_meeting_segments_two_crossings,
    long_meeting_topic_marks,
    short_meeting_segments,
    two_crossings_topic_marks,
)


# ---------------------------------------------------------------------------
# mode="auto": always walks, never silently collapses to single_pass
# ---------------------------------------------------------------------------


def test_auto_mode_never_produces_single_pass_even_for_a_short_meeting():
    segs = short_meeting_segments()
    plan = build_chunk_plan(segs, meeting_id="m1")

    assert plan.kind is ChunkPlanKind.MULTI_CHUNK
    assert plan.chunks  # at least one chunk
    assert all(c.boundary_source is not BoundarySource.SINGLE_PASS for c in plan.chunks)


def test_empty_segments_gives_empty_single_pass_plan():
    # The one degenerate exception: zero segments implies zero requests, so
    # there is nothing to gate.
    plan = build_chunk_plan([], meeting_id="empty")
    assert plan.kind is ChunkPlanKind.SINGLE_PASS
    assert plan.chunks == ()


# ---------------------------------------------------------------------------
# the walk: target/max bounds, topic-mark snapping, plain-duration fallback
# ---------------------------------------------------------------------------


def test_single_crossing_snaps_to_topic_mark():
    segs = long_meeting_segments()
    marks = long_meeting_topic_marks()
    plan = build_chunk_plan(
        segs,
        meeting_id="m2",
        target_chunk_s=2400.0,
        max_chunk_s=2400.0,
        topic_marks=marks,
        boundary_provenance=BoundaryProvenance.SIGNAL,
    )

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
    plan = build_chunk_plan(segs, meeting_id="m3", target_chunk_s=2400.0, max_chunk_s=2400.0, topic_marks=marks)

    assert plan.kind is ChunkPlanKind.MULTI_CHUNK
    assert len(plan.chunks) == 3

    c0, c1, c2 = plan.chunks
    assert c0.end == 2350.0
    assert c0.boundary_source is BoundarySource.TOPIC_MARK
    assert c0.segment_ids == ("s0", "s1", "s2", "s3")

    # The second crossing has no nearby mark, AND its causing segment (s7,
    # ending at 4800) would overshoot max_chunk_s (2350+2400=4750) if
    # accepted whole -- unlike the old single-soft-cap design (which
    # accepted the overshoot), max_chunk_s is now a REAL hard bound: the
    # walk cuts at the END OF THE PREVIOUS segment (s6, 4200) instead, so
    # no chunk here ever exceeds max_chunk_s.
    assert c1.start == 2350.0
    assert c1.end == 4200.0
    assert c1.boundary_source is BoundarySource.PLAIN_DURATION
    assert c1.segment_ids == ("s4", "s5", "s6")
    assert (c1.end - c1.start) <= 2400.0

    assert c2.start == 4200.0
    assert c2.end == 6000.0
    assert c2.boundary_source is BoundarySource.FINAL
    assert c2.segment_ids == ("s7", "s8", "s9")


def test_a_segment_is_never_split_across_chunks():
    segs = long_meeting_segments_two_crossings()
    marks = two_crossings_topic_marks()
    plan = build_chunk_plan(segs, meeting_id="m3", target_chunk_s=2400.0, max_chunk_s=2400.0, topic_marks=marks)

    seen: list[str] = []
    for chunk in plan.chunks:
        seen.extend(chunk.segment_ids)
    assert seen == [s.id for s in segs]  # every id exactly once, in order -- a clean partition


def test_mode_multi_chunk_forces_the_walk_even_under_the_target():
    segs = short_meeting_segments()
    plan = build_chunk_plan(segs, meeting_id="m5", target_chunk_s=2400.0, max_chunk_s=2400.0, mode="multi_chunk")

    # Nothing crosses the target, so this collapses to one chunk -- but the
    # KIND is still multi_chunk, never single_pass.
    assert plan.kind is ChunkPlanKind.MULTI_CHUNK
    assert len(plan.chunks) == 1
    assert plan.chunks[0].boundary_source is BoundarySource.FINAL


def test_default_bounds_walk_a_short_meeting_into_multiple_task_chunks():
    # The DEFAULT bounds (target 360s / [180, 900]) are much tighter than
    # the old 2400s single cap: an 18-minute (1080s) meeting now produces
    # more than one task chunk even with no topic marks at all.
    segs = short_meeting_segments()
    plan = build_chunk_plan(segs, meeting_id="m-default")
    assert plan.kind is ChunkPlanKind.MULTI_CHUNK
    assert len(plan.chunks) >= 2
    for c in plan.chunks:
        assert c.end - c.start <= 900.0


def test_undersized_trailing_chunk_is_merged_into_its_predecessor():
    # 3 segments of 400s each = 1200s total; target=360 crosses after the
    # first segment (400s), crosses again after the second (800s), leaving
    # a 400s tail -- long enough on its own, so use a case that leaves a
    # deliberately SHORT tail below min_chunk_s to exercise the merge.
    segs = (
        Segment("a", "A", 0.0, 380.0, "x"),
        Segment("b", "A", 380.0, 760.0, "x"),
        Segment("c", "A", 760.0, 800.0, "x"),  # 40s tail -- well under min_chunk_s=180
    )
    plan = build_chunk_plan(segs, meeting_id="merge-tail", target_chunk_s=360.0, min_chunk_s=180.0, max_chunk_s=900.0)
    # The 40s tail must not survive as its own undersized chunk.
    assert all((c.end - c.start) >= 180.0 or len(plan.chunks) == 1 for c in plan.chunks)
    seen = [seg_id for c in plan.chunks for seg_id in c.segment_ids]
    assert seen == ["a", "b", "c"]


def test_a_single_segment_longer_than_max_chunk_s_is_accepted_whole():
    segs = (Segment("solo", "A", 0.0, 1200.0, "one very long segment"),)
    plan = build_chunk_plan(segs, meeting_id="solo-long", target_chunk_s=360.0, min_chunk_s=180.0, max_chunk_s=900.0)
    assert len(plan.chunks) == 1
    assert plan.chunks[0].end - plan.chunks[0].start == 1200.0
    assert plan.chunks[0].segment_ids == ("solo",)


# ---------------------------------------------------------------------------
# topic-mark boundary provenance gate (M1 leakage tier, :mod:`.leakage`)
# ---------------------------------------------------------------------------


def test_oracle_topic_marks_refused_without_explicit_admission():
    segs = long_meeting_segments()
    marks = long_meeting_topic_marks()
    with pytest.raises(BoundaryLeakageTierViolation):
        build_chunk_plan(
            segs,
            meeting_id="m-oracle",
            target_chunk_s=2400.0,
            max_chunk_s=2400.0,
            topic_marks=marks,
            boundary_provenance=BoundaryProvenance.ORACLE_TOPIC,
        )


def test_oracle_topic_marks_admitted_with_explicit_ceiling_arm_flag():
    segs = long_meeting_segments()
    marks = long_meeting_topic_marks()
    plan = build_chunk_plan(
        segs,
        meeting_id="m-oracle-ok",
        target_chunk_s=2400.0,
        max_chunk_s=2400.0,
        topic_marks=marks,
        boundary_provenance=BoundaryProvenance.ORACLE_TOPIC,
        allow_oracle_boundaries=True,
    )
    assert plan.chunks[0].boundary_source is BoundarySource.TOPIC_MARK
    assert plan.boundary_provenance is BoundaryProvenance.ORACLE_TOPIC


def test_signal_provenance_never_needs_the_oracle_flag():
    segs = long_meeting_segments()
    marks = long_meeting_topic_marks()
    plan = build_chunk_plan(
        segs, meeting_id="m-signal", target_chunk_s=2400.0, max_chunk_s=2400.0, topic_marks=marks
    )  # boundary_provenance defaults to SIGNAL, allow_oracle_boundaries defaults to False
    assert plan.chunks[0].boundary_source is BoundarySource.TOPIC_MARK


# ---------------------------------------------------------------------------
# single_pass: explicit opt-in + plan-time serving-context assertion
# ---------------------------------------------------------------------------


def test_single_pass_refused_without_allow_single_pass():
    segs = short_meeting_segments()
    with pytest.raises(SinglePassNotAdmittedError):
        build_chunk_plan(segs, meeting_id="m4", mode="single_pass")


def test_single_pass_refused_at_plan_time_when_it_does_not_fit_the_slot_context():
    # short_meeting_segments spans 1080s -- even AMI's shortest dev meeting
    # (943.8s) does not fit a single-pass request at the locked -np4 slot
    # (analysis SS7); this must be a plan-time refusal.
    segs = short_meeting_segments()
    with pytest.raises(SlotContextExceededError):
        build_chunk_plan(segs, meeting_id="m4", mode="single_pass", allow_single_pass=True)


def test_single_pass_succeeds_when_admitted_and_it_actually_fits():
    tiny = (Segment("s0", "A", 0.0, 80.0, "short clip"),)
    plan = build_chunk_plan(tiny, meeting_id="m-tiny", mode="single_pass", allow_single_pass=True)
    assert plan.kind is ChunkPlanKind.SINGLE_PASS
    assert len(plan.chunks) == 1
    assert plan.chunks[0].boundary_source is BoundarySource.SINGLE_PASS
    assert plan.chunks[0].segment_ids == ("s0",)


def test_single_pass_context_assertion_is_config_driven_not_hard_coded_49152():
    # At a wider (e.g. -np1-equivalent) slot the same meeting that failed
    # at the default (-np4-equivalent) config fits -- proving the check
    # reads slot_context_tokens as a declared value, never a hard-coded
    # constant.
    segs = short_meeting_segments()  # 1080s
    wide = SlotContextConfig(slot_context_tokens=49152)
    plan = build_chunk_plan(segs, meeting_id="m-wide", mode="single_pass", allow_single_pass=True, slot_context=wide)
    assert plan.kind is ChunkPlanKind.SINGLE_PASS


# ---------------------------------------------------------------------------
# determinism, validation, to_dict shape
# ---------------------------------------------------------------------------


def test_unsorted_input_is_sorted_before_planning():
    segs = short_meeting_segments()
    reversed_segs = tuple(reversed(segs))
    plan_sorted = build_chunk_plan(segs, meeting_id="m6")
    plan_reversed = build_chunk_plan(reversed_segs, meeting_id="m6")
    assert plan_sorted == plan_reversed


def test_determinism_same_input_same_hash_and_equal_plan():
    segs = long_meeting_segments_two_crossings()
    marks = two_crossings_topic_marks()
    plan_a = build_chunk_plan(segs, meeting_id="m7", target_chunk_s=2400.0, max_chunk_s=2400.0, topic_marks=marks)
    plan_b = build_chunk_plan(segs, meeting_id="m7", target_chunk_s=2400.0, max_chunk_s=2400.0, topic_marks=marks)

    assert plan_a == plan_b
    assert plan_a.content_hash == plan_b.content_hash
    assert len(plan_a.content_hash) == 64  # sha256 hex digest


def test_content_hash_changes_with_target_chunk_s():
    segs = long_meeting_segments_two_crossings()
    marks = two_crossings_topic_marks()
    plan_a = build_chunk_plan(segs, meeting_id="m8", target_chunk_s=2400.0, max_chunk_s=2400.0, topic_marks=marks)
    plan_b = build_chunk_plan(segs, meeting_id="m8", target_chunk_s=1800.0, max_chunk_s=1800.0, topic_marks=marks)
    assert plan_a.content_hash != plan_b.content_hash


@pytest.mark.parametrize(
    "kwargs",
    [
        {"target_chunk_s": 0.0},
        {"target_chunk_s": -1.0},
        {"min_chunk_s": 0.0},
        {"max_chunk_s": 0.0},
        {"min_chunk_s": 500.0, "target_chunk_s": 100.0, "max_chunk_s": 900.0},  # min > target
        {"min_chunk_s": 100.0, "target_chunk_s": 1000.0, "max_chunk_s": 900.0},  # target > max
    ],
)
def test_chunk_bounds_must_be_positive_and_ordered(kwargs):
    with pytest.raises(ValueError):
        build_chunk_plan(short_meeting_segments(), **kwargs)


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        build_chunk_plan(short_meeting_segments(), mode="bogus")


def test_to_dict_roundtrip_shapes():
    segs = short_meeting_segments()
    plan = build_chunk_plan(segs, meeting_id="m9")
    d = plan.to_dict()
    assert d["meeting_id"] == "m9"
    assert d["kind"] == "multi_chunk"
    assert d["target_chunk_s"] == 360.0
    assert d["min_chunk_s"] == 180.0
    assert d["max_chunk_s"] == 900.0
    assert d["boundary_provenance"] == "signal"
    assert d["chunks"]
    assert d["content_hash"] == plan.content_hash


def test_segment_protocol_accepts_plain_segment_directly():
    # The Segment dataclass itself is used as SegmentLike input elsewhere
    # in this file; this test just pins that no adapter is required.
    seg = Segment("x0", "A", 0.0, 10.0, "hi")
    plan = build_chunk_plan([seg], meeting_id="solo")
    assert plan.chunks[0].segment_ids == ("x0",)
