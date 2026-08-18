"""Fixture mirrors docs/readiness/2026-08-18-saer-m-definition.md's worked
micro-example table exactly (s.1 through s.6) -- keep the two in sync."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.corpora.nxt.models import EvidenceLink
from meeting_minutes_agent.metrics.saer_m import (
    SpeakerAttributionPrediction,
    compute_saer_m,
)


def _link(link_id: str, sentence_id: str, speaker: str) -> EvidenceLink:
    return EvidenceLink(
        id=link_id,
        sentence_id=sentence_id,
        section="abstract",
        sentence_text=f"text for {sentence_id}",
        da_ids=("da.1",),
        speaker=speaker,
        start=0.0,
        end=1.0,
        text="some supporting text",
        word_ids=("w.1",),
    )


def _worked_example_inputs():
    evidence_links = [
        _link("sl.1", "s.1", "spk_a"),
        _link("sl.2", "s.2", "spk_b"),
        _link("sl.3", "s.3", "spk_a"),
        _link("sl.4", "s.5", "spk_a"),  # s.5 has TWO evidence links, different speakers
        _link("sl.5", "s.5", "spk_b"),
    ]
    predictions = [
        SpeakerAttributionPrediction("s.1", "spk_a"),  # correct
        SpeakerAttributionPrediction("s.2", "spk_a"),  # wrong_speaker (gold is spk_b)
        # s.3 intentionally has NO prediction entry -> unattributed
        SpeakerAttributionPrediction("s.4", "spk_b"),  # hallucinated_speaker (no gold evidence)
        SpeakerAttributionPrediction("s.5", "spk_b"),  # correct (member of ambiguous gold set)
        SpeakerAttributionPrediction("s.6", None),  # not_scored (neither side has anything)
    ]
    return evidence_links, predictions


def test_worked_example_matches_definition_doc():
    evidence_links, predictions = _worked_example_inputs()
    report = compute_saer_m(evidence_links, predictions)

    by_id = {r.sentence_id: r for r in report.per_sentence}
    assert by_id["s.1"].outcome == "correct"
    assert by_id["s.2"].outcome == "wrong_speaker"
    assert by_id["s.3"].outcome == "unattributed"
    assert by_id["s.4"].outcome == "hallucinated_speaker"
    assert by_id["s.5"].outcome == "correct"
    assert by_id["s.6"].outcome == "not_scored"

    assert report.n_correct == 2
    assert report.n_wrong_speaker == 1
    assert report.n_unattributed == 1
    assert report.n_hallucinated_speaker == 1
    assert report.n_not_scored == 1
    assert report.n_scored == 4  # correct + wrong_speaker + unattributed only
    assert report.accuracy == pytest.approx(0.5)


def test_ambiguous_gold_scores_correct_for_either_member():
    evidence_links = [
        _link("sl.1", "s.5", "spk_a"),
        _link("sl.2", "s.5", "spk_b"),
    ]
    for candidate in ("spk_a", "spk_b"):
        report = compute_saer_m(evidence_links, [SpeakerAttributionPrediction("s.5", candidate)])
        assert report.per_sentence[0].outcome == "correct"


def test_ambiguous_gold_from_single_link_pipe_joined_speaker_field():
    # MeetingResolver.resolve_evidence_links itself can emit ONE link whose
    # `speaker` field is already "spk_a|spk_b" (multi-agent dialogue-act
    # span) rather than two separate links -- must be handled the same way.
    evidence_links = [_link("sl.1", "s.5", "spk_a|spk_b")]
    report = compute_saer_m(evidence_links, [SpeakerAttributionPrediction("s.5", "spk_b")])
    assert report.per_sentence[0].outcome == "correct"
    assert report.per_sentence[0].gold_speakers == ("spk_a", "spk_b")


def test_wrong_speaker_against_ambiguous_gold():
    evidence_links = [_link("sl.1", "s.5", "spk_a|spk_b")]
    report = compute_saer_m(evidence_links, [SpeakerAttributionPrediction("s.5", "spk_c")])
    assert report.per_sentence[0].outcome == "wrong_speaker"


def test_empty_inputs_give_none_accuracy_not_zero_division():
    report = compute_saer_m([], [])
    assert report.per_sentence == ()
    assert report.n_scored == 0
    assert report.accuracy is None


def test_empty_speaker_string_link_is_skipped_not_treated_as_gold():
    evidence_links = [_link("sl.1", "s.9", "")]
    report = compute_saer_m(evidence_links, [SpeakerAttributionPrediction("s.9", "spk_a")])
    # no non-empty gold speaker was ever recorded for s.9 -> hallucinated, not correct/wrong.
    assert report.per_sentence[0].outcome == "hallucinated_speaker"


def test_perfect_attribution_gives_accuracy_one():
    evidence_links = [_link("sl.1", "s.1", "spk_a"), _link("sl.2", "s.2", "spk_b")]
    predictions = [
        SpeakerAttributionPrediction("s.1", "spk_a"),
        SpeakerAttributionPrediction("s.2", "spk_b"),
    ]
    report = compute_saer_m(evidence_links, predictions)
    assert report.accuracy == pytest.approx(1.0)
    assert report.n_wrong_speaker == 0
    assert report.n_unattributed == 0
    assert report.n_hallucinated_speaker == 0
