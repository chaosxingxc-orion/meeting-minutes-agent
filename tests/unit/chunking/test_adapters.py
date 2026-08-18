"""Tests for :mod:`meeting_minutes_agent.chunking.adapters`: flattening a
``ResolvedMeeting``'s (possibly nested) topic tree into chunk-boundary
marks, extracting its gold turn table, and the
``build_chunk_plan_for_resolved_meeting`` convenience wrapper's M1
leakage-tier fallback (AMI's topic layer is gold annotation -- it must NOT
be forwarded into a runtime plan unless a ceiling arm explicitly admits
it)."""

from __future__ import annotations

from meeting_minutes_agent.chunking.adapters import (
    build_chunk_plan_for_resolved_meeting,
    topic_marks_from_resolved_meeting,
    turn_table_from_resolved_meeting,
    turn_table_provenance,
)
from meeting_minutes_agent.chunking.leakage import BoundaryLeakageTier, BoundaryProvenance, tier_of
from meeting_minutes_agent.chunking.models import BoundarySource, ChunkPlanKind
from meeting_minutes_agent.chunking.slicer import TurnSpan
from meeting_minutes_agent.corpora.nxt.models import ResolvedMeeting, Topic, Utterance


def _utterance(id_: str, speaker: str, start: float, end: float, text: str) -> Utterance:
    return Utterance(id=id_, speaker=speaker, start=start, end=end, text=text, word_ids=())


def _resolved_meeting(topics: tuple[Topic, ...], transcript: tuple[Utterance, ...]) -> ResolvedMeeting:
    return ResolvedMeeting(
        meeting_id="ADAPT1",
        transcript=transcript,
        dialogue_acts=(),
        minutes=None,
        evidence_links=(),
        topics=topics,
        orphans=(),
    )


def test_topic_marks_flattens_nested_children_sorted_and_deduplicated():
    child = Topic(id="t1.1", description="sub", type_href=None, start=500.0, end=600.0, text="", word_ids=())
    parent = Topic(
        id="t1",
        description="top",
        type_href=None,
        start=100.0,
        end=900.0,
        text="",
        word_ids=(),
        children=(child,),
    )
    duplicate_start = Topic(id="t2", description=None, type_href=None, start=100.0, end=200.0, text="", word_ids=())
    no_start = Topic(id="t3", description=None, type_href=None, start=None, end=None, text="", word_ids=())

    resolved = _resolved_meeting((parent, duplicate_start, no_start), ())
    marks = topic_marks_from_resolved_meeting(resolved)

    assert marks == (100.0, 500.0)  # sorted, deduplicated, None dropped


def test_topic_marks_empty_when_no_topics():
    resolved = _resolved_meeting((), ())
    assert topic_marks_from_resolved_meeting(resolved) == ()


# ---------------------------------------------------------------------------
# M1 leakage-tier fallback: gold topic marks are NOT forwarded by default
# ---------------------------------------------------------------------------


def test_build_chunk_plan_for_resolved_meeting_falls_back_to_signal_by_default():
    child = Topic(id="t1.1", description=None, type_href=None, start=2350.0, end=2400.0, text="", word_ids=())
    topics = (
        Topic(id="t1", description=None, type_href=None, start=0.0, end=2400.0, text="", word_ids=(), children=(child,)),
    )
    transcript = tuple(
        _utterance(f"u{i}", "A" if i % 2 == 0 else "B", i * 600.0, i * 600.0 + 600.0, f"seg {i}") for i in range(7)
    )
    resolved = _resolved_meeting(topics, transcript)

    # allow_oracle_topic defaults to False: the gold marks (2350.0 present
    # in the topic tree) must NOT reach the plan -- boundaries fall back to
    # pure signal/plain-duration packing.
    plan = build_chunk_plan_for_resolved_meeting(resolved, target_chunk_s=2400.0, max_chunk_s=2400.0)

    assert plan.meeting_id == "ADAPT1"
    assert plan.boundary_provenance is BoundaryProvenance.SIGNAL
    assert all(c.boundary_source is not BoundarySource.TOPIC_MARK for c in plan.chunks)


def test_build_chunk_plan_for_resolved_meeting_uses_the_topic_tree_when_admitted():
    child = Topic(id="t1.1", description=None, type_href=None, start=2350.0, end=2400.0, text="", word_ids=())
    topics = (
        Topic(id="t1", description=None, type_href=None, start=0.0, end=2400.0, text="", word_ids=(), children=(child,)),
    )
    transcript = tuple(
        _utterance(f"u{i}", "A" if i % 2 == 0 else "B", i * 600.0, i * 600.0 + 600.0, f"seg {i}") for i in range(7)
    )
    resolved = _resolved_meeting(topics, transcript)

    plan = build_chunk_plan_for_resolved_meeting(
        resolved, target_chunk_s=2400.0, max_chunk_s=2400.0, allow_oracle_topic=True
    )

    assert plan.meeting_id == "ADAPT1"
    assert plan.kind is ChunkPlanKind.MULTI_CHUNK
    assert plan.boundary_provenance is BoundaryProvenance.ORACLE_TOPIC
    assert len(plan.chunks) == 2
    assert plan.chunks[0].end == 2350.0
    assert plan.chunks[0].boundary_source is BoundarySource.TOPIC_MARK


def test_build_chunk_plan_for_resolved_meeting_short_meeting_is_multi_chunk_not_single_pass():
    transcript = (_utterance("u0", "A", 0.0, 100.0, "hi"),)
    resolved = _resolved_meeting((), transcript)

    # mode="auto" (default) never collapses to single_pass (17-item change
    # list item 3).
    plan = build_chunk_plan_for_resolved_meeting(resolved)
    assert plan.kind is ChunkPlanKind.MULTI_CHUNK
    assert plan.chunks[0].segment_ids == ("u0",)


def test_resolved_meeting_utterances_satisfy_segmentlike_without_adaptation():
    from meeting_minutes_agent.chunking.models import SegmentLike

    u = _utterance("u0", "A", 0.0, 10.0, "hi")
    assert isinstance(u, SegmentLike)


# ---------------------------------------------------------------------------
# turn table extraction (2026-08-18 diarization-aware slicer amendment):
# AMI's gold segment/dialogue-act layer, tagged oracle-turn (Tier-M1)
# ---------------------------------------------------------------------------


def test_turn_table_from_resolved_meeting_extracts_sorted_spans():
    transcript = (
        _utterance("u1", "B", 10.0, 20.0, "second"),
        _utterance("u0", "A", 0.0, 10.0, "first"),
        _utterance("u2", "A", 20.0, 20.0, "zero-length, dropped"),  # end == start
        _utterance("u3", "B", None, 30.0, "missing start, dropped"),
    )
    resolved = _resolved_meeting((), transcript)

    turns = turn_table_from_resolved_meeting(resolved)

    assert turns == (TurnSpan(0.0, 10.0, "A"), TurnSpan(10.0, 20.0, "B"))


def test_turn_table_from_resolved_meeting_empty_when_no_transcript():
    resolved = _resolved_meeting((), ())
    assert turn_table_from_resolved_meeting(resolved) == ()


def test_turn_table_provenance_is_oracle_turn_tier_m1():
    assert turn_table_provenance() is BoundaryProvenance.ORACLE_TURN
    assert tier_of(turn_table_provenance()) is BoundaryLeakageTier.M1
