"""Tests for :mod:`meeting_minutes_agent.probes.pattr_scoring`: gold-stream
extraction, per-speaker hypothesis-stream construction, cpWER-family scoring
and the A-grid boundary-respect diagnostic.

Meeteval-dependent tests are gated on import availability
(``pytest.importorskip``), mirroring ``tests/unit/metrics/test_wer.py``'s own
convention; numbers are hand-countable and independently confirmed against
the installed meeteval 0.4.3, per that module's discipline.
"""

from __future__ import annotations

import pytest

pytest.importorskip("meeteval")

from meeting_minutes_agent.corpora.nxt.models import ResolvedMeeting, Utterance
from meeting_minutes_agent.heads.transcribe_attribute import TranscribedSegment
from meeting_minutes_agent.metrics.pins import MetricPins
from meeting_minutes_agent.metrics.timestamps import PerSpeakerSegment
from meeting_minutes_agent.probes.pattr_scoring import (
    BoundaryRespectResult,
    HypothesisSegment,
    boundary_respect_diagnostic,
    extract_gold_streams_for_range,
    hypothesis_segment_from_turn_reply,
    hypothesis_stream_from_grid_or_free_parse,
    score_arm,
)

_PINS = MetricPins(meeteval_version="0.4.3")


def _resolved(transcript: tuple[Utterance, ...]) -> ResolvedMeeting:
    return ResolvedMeeting(
        meeting_id="MTG1",
        transcript=transcript,
        dialogue_acts=(),
        minutes=None,
        evidence_links=(),
        topics=(),
        orphans=(),
    )


# ---------------------------------------------------------------------------
# gold-stream extraction for a time range
# ---------------------------------------------------------------------------

_GOLD_TRANSCRIPT = (
    Utterance(id="u0", speaker="A", start=0.0, end=1.0, text="hello world", word_ids=()),
    Utterance(id="u1", speaker="B", start=1.0, end=2.0, text="foo bar", word_ids=()),
    Utterance(id="u2", speaker="A", start=95.0, end=96.0, text="outside the range", word_ids=()),
)


def test_extract_gold_streams_for_range_includes_only_overlapping_utterances():
    stream = extract_gold_streams_for_range(_resolved(_GOLD_TRANSCRIPT), start=0.0, end=90.0)
    assert [s.speaker for s in stream] == ["A", "B"]
    assert [s.words for s in stream] == ["hello world", "foo bar"]


def test_extract_gold_streams_for_range_clips_a_partially_overlapping_utterance():
    transcript = (Utterance(id="u0", speaker="A", start=80.0, end=100.0, text="spans the boundary", word_ids=()),)
    stream = extract_gold_streams_for_range(_resolved(transcript), start=0.0, end=90.0)
    assert len(stream) == 1
    assert stream[0].start == 80.0
    assert stream[0].end == 90.0


def test_extract_gold_streams_for_range_drops_utterances_with_no_text_or_no_span():
    transcript = (
        Utterance(id="u0", speaker="A", start=0.0, end=1.0, text="", word_ids=()),
        Utterance(id="u1", speaker="B", start=None, end=None, text="no span", word_ids=()),
    )
    stream = extract_gold_streams_for_range(_resolved(transcript), start=0.0, end=10.0)
    assert stream == ()


def test_extract_gold_streams_for_range_rejects_bad_range():
    with pytest.raises(ValueError):
        extract_gold_streams_for_range(_resolved(_GOLD_TRANSCRIPT), start=10.0, end=5.0)


# ---------------------------------------------------------------------------
# hypothesis-stream construction
# ---------------------------------------------------------------------------


def test_hypothesis_stream_from_grid_or_free_parse_is_never_real_timed():
    parsed = (TranscribedSegment(speaker="A", text="hello world"), TranscribedSegment(speaker="B", text="foo bar"))
    stream = hypothesis_stream_from_grid_or_free_parse(parsed, slice_start=0.0, slice_end=90.0)
    assert len(stream) == 2
    assert all(h.real_timing is False for h in stream)
    assert all((h.start, h.end) == (0.0, 90.0) for h in stream)
    assert [h.speaker for h in stream] == ["A", "B"]


def test_hypothesis_segment_from_turn_reply_is_real_timed():
    h = hypothesis_segment_from_turn_reply(known_speaker="A", transcribed_text="hello world", turn_start=0.0, turn_end=1.0)
    assert h.real_timing is True
    assert h.speaker == "A"
    assert (h.start, h.end) == (0.0, 1.0)


# ---------------------------------------------------------------------------
# score_arm: hand-computed cpWER-family cases
# ---------------------------------------------------------------------------


def test_score_arm_content_only_errors_unambiguous_attribution():
    # Reference: A "hello world", B "foo bar" (4 words). Hypothesis: A
    # "hello there" (1 sub), B "foo bar baz" (1 ins). errors=2, length=4,
    # cpWER == ORC-WER == 0.5 exactly (content alone disambiguates the
    # speakers, so no confusion is possible) -- secondary_confusion_cost == 0.
    reference = (
        PerSpeakerSegment(speaker="A", start=0.0, end=1.0, words="hello world"),
        PerSpeakerSegment(speaker="B", start=1.0, end=2.0, words="foo bar"),
    )
    hypothesis = hypothesis_stream_from_grid_or_free_parse(
        (TranscribedSegment(speaker="A", text="hello there"), TranscribedSegment(speaker="B", text="foo bar baz")),
        slice_start=0.0, slice_end=2.0,
    )
    result = score_arm("A-grid", "MTG1", reference, hypothesis, pins=_PINS)
    assert result.cp_wer.error_rate == pytest.approx(0.5)
    assert result.secondary_confusion_cost.confusion_cost == pytest.approx(0.0)
    assert result.n_reference_segments == 2
    assert result.n_hypothesis_segments == 2
    # A-grid/A-free hypothesis carries no real per-segment timing -- the
    # time-constrained primary metric must be structurally skipped, never
    # fabricated (module docstring, G1 binding rule).
    assert result.primary_confusion_cost is None
    assert result.primary_confusion_cost_skipped_reason is not None
    assert "synthetic" in result.primary_confusion_cost_skipped_reason


def test_score_arm_wrong_attribution_shows_up_in_confusion_cost():
    # A speaks turns 0 and 2 ("one two", "five six"); B speaks turn 1
    # ("three four"). Every word is transcribed correctly, but the model
    # MISATTRIBUTES A's second turn to B, so the hypothesis has only two
    # streams: A="one two", B="three four five six" (B's real turn plus
    # A's misattributed one, concatenated in time order). Note a plain
    # LABEL SWAP would NOT show up here -- cpWER/ORC-WER are permutation-
    # matched, so renaming clusters is free (docs/readiness/2026-08-18-
    # g1-preregistration-draft.md SS0: "model-side cluster naming is
    # irrelevant"); this is a genuine cross-speaker misattribution instead.
    # No single GLOBAL speaker permutation undoes it (cpWER pays), but
    # ORC-WER may freely regroup reference utterances per hypothesis stream
    # (refA-turn0 -> hypA, refB-turn1+refA-turn2 -> hypB) and finds a
    # PERFECT regrouping -- mirroring tests/unit/metrics/test_wer.py's own
    # over-segmented fixture, just built from the scoring path's own
    # hypothesis-stream constructor instead of a hand-built PerSpeakerSegment
    # list.
    reference = (
        PerSpeakerSegment(speaker="A", start=0.0, end=1.0, words="one two"),
        PerSpeakerSegment(speaker="B", start=1.0, end=2.0, words="three four"),
        PerSpeakerSegment(speaker="A", start=2.0, end=3.0, words="five six"),
    )
    hypothesis = hypothesis_stream_from_grid_or_free_parse(
        (
            TranscribedSegment(speaker="A", text="one two"),
            TranscribedSegment(speaker="B", text="three four five six"),
        ),
        slice_start=0.0, slice_end=3.0,
    )
    result = score_arm("A-grid", "MTG1", reference, hypothesis, pins=_PINS)
    assert result.secondary_confusion_cost.minuend.metric == "cpWER"
    assert result.secondary_confusion_cost.subtrahend.metric == "ORC-WER"
    # ORC-WER may freely regroup reference utterances per hypothesis stream
    # -- a perfect regrouping exists here, so it is exactly 0.
    assert result.secondary_confusion_cost.subtrahend.error_rate == pytest.approx(0.0)
    # cpWER is stuck with ONE global permutation and cannot avoid the
    # misattribution -- strictly positive, and therefore so is the
    # confusion cost: the wrong attribution shows up.
    assert result.cp_wer.error_rate > 0.0
    assert result.secondary_confusion_cost.confusion_cost > 0.0
    assert result.secondary_confusion_cost.confusion_cost == pytest.approx(result.cp_wer.error_rate)


def test_score_arm_a_turn_case_real_timing_computes_both_metrics():
    reference = (PerSpeakerSegment(speaker="A", start=0.0, end=1.0, words="hello world"),)
    hypothesis = (hypothesis_segment_from_turn_reply(known_speaker="A", transcribed_text="hello world", turn_start=0.0, turn_end=1.0),)
    result = score_arm("A-turn", "MTG1", reference, hypothesis, pins=_PINS)
    assert result.cp_wer.error_rate == pytest.approx(0.0)
    assert result.secondary_confusion_cost.confusion_cost == pytest.approx(0.0)
    assert result.primary_confusion_cost is not None
    assert result.primary_confusion_cost_skipped_reason is None
    assert result.primary_confusion_cost.minuend.metric == "tcpWER"
    assert result.primary_confusion_cost.confusion_cost == pytest.approx(0.0)


def test_score_arm_mixed_real_and_fake_timing_still_skips_primary():
    # If even ONE hypothesis segment in the stream lacks real timing, the
    # whole stream is not eligible for a time-constrained metric.
    reference = (
        PerSpeakerSegment(speaker="A", start=0.0, end=1.0, words="hello world"),
        PerSpeakerSegment(speaker="B", start=1.0, end=2.0, words="foo bar"),
    )
    hypothesis = (
        hypothesis_segment_from_turn_reply(known_speaker="A", transcribed_text="hello world", turn_start=0.0, turn_end=1.0),
        HypothesisSegment(speaker="B", text="foo bar", start=1.0, end=2.0, real_timing=False),
    )
    result = score_arm("mixed", "MTG1", reference, hypothesis, pins=_PINS)
    assert result.primary_confusion_cost is None
    assert result.primary_confusion_cost_skipped_reason is not None


def test_pattr_arm_score_to_dict_shape():
    reference = (PerSpeakerSegment(speaker="A", start=0.0, end=1.0, words="hi"),)
    hypothesis = (hypothesis_segment_from_turn_reply(known_speaker="A", transcribed_text="hi", turn_start=0.0, turn_end=1.0),)
    result = score_arm("A-turn", "MTG1", reference, hypothesis, pins=_PINS)
    d = result.to_dict()
    assert d["arm"] == "A-turn"
    assert d["meeting_id"] == "MTG1"
    assert d["primary_confusion_cost"] is not None
    assert d["primary_confusion_cost_skipped_reason"] is None


# ---------------------------------------------------------------------------
# A-grid boundary-respect diagnostic
# ---------------------------------------------------------------------------

_DECLARED_GRID = (
    {"speaker": "A", "slice_offset_start": 0.0, "slice_offset_end": 40.0},
    {"speaker": "B", "slice_offset_start": 40.0, "slice_offset_end": 90.0},
)


def test_boundary_respect_perfect_match():
    parsed = (TranscribedSegment(speaker="A", text="x"), TranscribedSegment(speaker="B", text="y"))
    result = boundary_respect_diagnostic(parsed, _DECLARED_GRID)
    assert isinstance(result, BoundaryRespectResult)
    assert result.n_compared == 2
    assert result.n_matched == 2
    assert result.fraction_matched == pytest.approx(1.0)


def test_boundary_respect_case_insensitive_and_whitespace_insensitive():
    parsed = (TranscribedSegment(speaker=" a ", text="x"), TranscribedSegment(speaker="B", text="y"))
    result = boundary_respect_diagnostic(parsed, _DECLARED_GRID)
    assert result.n_matched == 2


def test_boundary_respect_mismatch_reduces_fraction():
    # Position 0 mismatches (declared A, model says B); position 1 matches.
    parsed = (TranscribedSegment(speaker="B", text="x"), TranscribedSegment(speaker="B", text="y"))
    result = boundary_respect_diagnostic(parsed, _DECLARED_GRID)
    assert result.n_compared == 2
    assert result.n_matched == 1
    assert result.fraction_matched == pytest.approx(0.5)


def test_boundary_respect_fewer_parsed_segments_than_grid_compares_the_shorter_length():
    parsed = (TranscribedSegment(speaker="A", text="x"),)
    result = boundary_respect_diagnostic(parsed, _DECLARED_GRID)
    assert result.n_compared == 1
    assert result.n_matched == 1


def test_boundary_respect_no_grid_entries_gives_zero_fraction_not_a_crash():
    parsed = (TranscribedSegment(speaker="A", text="x"),)
    result = boundary_respect_diagnostic(parsed, ())
    assert result.n_compared == 0
    assert result.fraction_matched == pytest.approx(0.0)


def test_boundary_respect_to_dict_shape():
    d = boundary_respect_diagnostic((), ()).to_dict()
    assert d == {"n_compared": 0, "n_matched": 0, "fraction_matched": 0.0}
