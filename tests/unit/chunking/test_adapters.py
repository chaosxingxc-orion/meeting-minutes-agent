"""Tests for :mod:`meeting_minutes_agent.chunking.adapters`: flattening a
``ResolvedMeeting``'s (possibly nested) topic tree into chunk-boundary
marks, and the ``build_chunk_plan_for_resolved_meeting`` convenience
wrapper."""

from __future__ import annotations

from meeting_minutes_agent.chunking.adapters import (
    build_chunk_plan_for_resolved_meeting,
    topic_marks_from_resolved_meeting,
)
from meeting_minutes_agent.chunking.models import BoundarySource, ChunkPlanKind
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


def test_build_chunk_plan_for_resolved_meeting_uses_the_topic_tree():
    child = Topic(id="t1.1", description=None, type_href=None, start=2350.0, end=2400.0, text="", word_ids=())
    topics = (
        Topic(id="t1", description=None, type_href=None, start=0.0, end=2400.0, text="", word_ids=(), children=(child,)),
    )
    transcript = tuple(
        _utterance(f"u{i}", "A" if i % 2 == 0 else "B", i * 600.0, i * 600.0 + 600.0, f"seg {i}") for i in range(7)
    )
    resolved = _resolved_meeting(topics, transcript)

    plan = build_chunk_plan_for_resolved_meeting(resolved, window_cap_s=2400.0)

    assert plan.meeting_id == "ADAPT1"
    assert plan.kind is ChunkPlanKind.MULTI_CHUNK
    assert len(plan.chunks) == 2
    assert plan.chunks[0].end == 2350.0
    assert plan.chunks[0].boundary_source is BoundarySource.TOPIC_MARK


def test_build_chunk_plan_for_resolved_meeting_single_pass_when_short():
    transcript = (_utterance("u0", "A", 0.0, 100.0, "hi"),)
    resolved = _resolved_meeting((), transcript)

    plan = build_chunk_plan_for_resolved_meeting(resolved, window_cap_s=2400.0)
    assert plan.kind is ChunkPlanKind.SINGLE_PASS
    assert plan.chunks[0].segment_ids == ("u0",)


def test_resolved_meeting_utterances_satisfy_segmentlike_without_adaptation():
    from meeting_minutes_agent.chunking.models import SegmentLike

    u = _utterance("u0", "A", 0.0, 10.0, "hi")
    assert isinstance(u, SegmentLike)
