"""Fixture mirrors docs/readiness/2026-08-18-saer-m-definition.md's worked
micro-example table exactly (s.1 through s.6) -- keep the two in sync."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.corpora.nxt.models import EvidenceLink
from meeting_minutes_agent.metrics.saer_m import (
    SAER_M_ALIGNMENT_F1_THRESHOLD,
    SAER_M_ALIGNMENT_METHOD,
    SpeakerAttributionPrediction,
    align_predictions_to_gold_sentences,
    compute_saer_m,
    token_f1,
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


# ---------------------------------------------------------------------------
# SAER-M definition v1.1: content-based alignment
# (docs/readiness/2026-08-19-g1-floors-verdict.md S1e -- the exact-id join
# intersects on 0 sentences when gold ids are NXT corpus ids and predicted
# ids are the minutes head's synthesized "<section>-<index>" ids)
# ---------------------------------------------------------------------------


def _link_with_text(link_id: str, sentence_id: str, sentence_text: str, speaker: str) -> EvidenceLink:
    return EvidenceLink(
        id=link_id,
        sentence_id=sentence_id,
        section="abstract",
        sentence_text=sentence_text,
        da_ids=("da.1",),
        speaker=speaker,
        start=0.0,
        end=1.0,
        text="some supporting text",
        word_ids=("w.1",),
    )


class TestTokenF1:
    def test_identical_text_scores_one(self):
        assert token_f1("alpha bravo charlie", "alpha bravo charlie") == pytest.approx(1.0)

    def test_disjoint_text_scores_zero(self):
        assert token_f1("alpha bravo", "charlie delta") == pytest.approx(0.0)

    def test_empty_text_scores_zero_not_a_division_error(self):
        assert token_f1("", "alpha") == 0.0
        assert token_f1("alpha", "") == 0.0
        assert token_f1("", "") == 0.0

    def test_is_symmetric(self):
        a, b = "the team approved the budget for next quarter", "team approved budget"
        assert token_f1(a, b) == pytest.approx(token_f1(b, a))

    def test_case_and_punctuation_insensitive(self):
        assert token_f1("Alpha, Bravo!", "alpha bravo") == pytest.approx(1.0)

    def test_method_constant_is_registered_as_token_f1(self):
        assert SAER_M_ALIGNMENT_METHOD == "token_f1"


class TestAlignmentMatchNoMatchThreshold:
    """Fixtures mirroring the G1 shape: a synthesized minutes-head bullet id
    (``"abstract-N"``) against an NXT-style gold sentence id."""

    def test_synthesized_bullet_id_aligns_to_nxt_gold_id_on_content_overlap(self):
        gold_id = "ES2011a.JacquelinePalmer.s.1"
        gold_text = "Jacqueline Palmer said the team would finalize the remote control design by next week."
        link = _link_with_text("sl.g1", gold_id, gold_text, "JacquelinePalmer")
        prediction = SpeakerAttributionPrediction(
            sentence_id="abstract-0",
            predicted_speaker="JacquelinePalmer",
            text="The team will finalize the remote control design by next week.",
        )

        report = compute_saer_m([link], [prediction])

        assert report.n_scored == 1
        assert report.accuracy == pytest.approx(1.0)
        result = report.per_sentence[0]
        assert result.sentence_id == gold_id  # aligned onto the gold id, not left at "abstract-0"
        assert result.outcome == "correct"

    def test_no_alignment_when_content_is_unrelated(self):
        gold_id = "ES2011a.JacquelinePalmer.s.2"
        link = _link_with_text(
            "sl.g2", gold_id, "The budget review meeting starts at nine tomorrow morning.", "JacquelinePalmer"
        )
        prediction = SpeakerAttributionPrediction(
            sentence_id="abstract-1",
            predicted_speaker="JacquelinePalmer",
            text="Software installation instructions for the remote control prototype.",
        )

        report = compute_saer_m([link], [prediction])

        by_id = {r.sentence_id: r for r in report.per_sentence}
        assert by_id[gold_id].outcome == "unattributed"  # no prediction ever aligned to the gold sentence
        assert by_id["abstract-1"].outcome == "hallucinated_speaker"  # kept its own synthesized id
        assert report.accuracy == pytest.approx(0.0)

    def test_threshold_boundary_at_exactly_registered_threshold_matches(self):
        # 10 unique tokens each side, 3 shared -> precision = recall = F1 = 0.3,
        # engineered to equal SAER_M_ALIGNMENT_F1_THRESHOLD exactly.
        gold_text = "alpha bravo charlie g1 g2 g3 g4 g5 g6 g7"
        pred_text = "alpha bravo charlie p1 p2 p3 p4 p5 p6 p7"
        assert token_f1(pred_text, gold_text) == pytest.approx(SAER_M_ALIGNMENT_F1_THRESHOLD)

        link = _link_with_text("sl.b1", "gold.boundary.1", gold_text, "spk_a")
        prediction = SpeakerAttributionPrediction(sentence_id="abstract-0", predicted_speaker="spk_a", text=pred_text)

        report = compute_saer_m([link], [prediction])
        result = next(r for r in report.per_sentence if r.sentence_id == "gold.boundary.1")
        assert result.outcome == "correct"  # >= threshold is inclusive

    def test_threshold_boundary_just_below_threshold_does_not_match(self):
        # Same shape, only 2 of 10 tokens shared -> F1 = 0.2, strictly below threshold.
        gold_text = "alpha bravo g1 g2 g3 g4 g5 g6 g7 g8"
        pred_text = "alpha bravo p1 p2 p3 p4 p5 p6 p7 p8"
        f1 = token_f1(pred_text, gold_text)
        assert f1 < SAER_M_ALIGNMENT_F1_THRESHOLD

        link = _link_with_text("sl.b2", "gold.boundary.2", gold_text, "spk_a")
        prediction = SpeakerAttributionPrediction(sentence_id="abstract-0", predicted_speaker="spk_a", text=pred_text)

        report = compute_saer_m([link], [prediction])
        by_id = {r.sentence_id: r for r in report.per_sentence}
        assert by_id["gold.boundary.2"].outcome == "unattributed"
        assert by_id["abstract-0"].outcome == "hallucinated_speaker"

    def test_prediction_without_text_falls_back_to_exact_id_join(self):
        # No `text` set (the default) -> never enters alignment; behaves
        # exactly like the pre-v1.1 exact-id join.
        link = _link_with_text("sl.b3", "s.exact", "irrelevant to this test", "spk_a")
        prediction = SpeakerAttributionPrediction(sentence_id="s.exact", predicted_speaker="spk_a")
        report = compute_saer_m([link], [prediction])
        assert report.per_sentence[0].outcome == "correct"

    def test_wrong_speaker_survives_alignment(self):
        # Content aligns; the attributed speaker is still checked against
        # gold membership exactly as before -- alignment only fixes the id,
        # not the taxonomy.
        gold_id = "ES2011a.JacquelinePalmer.s.3"
        gold_text = "The finance subgroup will report back on the component budget next session."
        link = _link_with_text("sl.g3", gold_id, gold_text, "JacquelinePalmer")
        prediction = SpeakerAttributionPrediction(
            sentence_id="abstract-2",
            predicted_speaker="WrongSpeaker",
            text="The finance subgroup reports back on the component budget next session.",
        )
        report = compute_saer_m([link], [prediction])
        result = next(r for r in report.per_sentence if r.sentence_id == gold_id)
        assert result.outcome == "wrong_speaker"


class TestGreedyOneToOneAssignment:
    def test_a_strong_prediction_cannot_double_book_two_gold_sentences(self):
        """Without a one-to-one constraint, an independent per-gold-sentence
        argmax would let predA (a decent match for BOTH gold sentences) win
        both pairings and starve predB (the only real candidate for gold2)
        of a match. The registered algorithm is a global greedy assignment
        over every above-threshold (prediction, gold) pair, processed in
        descending-score order: predA claims its best pairing (gold1,
        F1=1.0) first and is then unavailable for gold2, which correctly
        falls through to predB (F1=0.4)."""

        gold1_text = "kappa lambda mu nu"
        gold2_text = "kappa lambda golf hotel"
        pred_a_text = "kappa lambda mu nu"  # F1 vs gold1 = 1.0, vs gold2 = 0.5
        pred_b_text = "golf hotel p1 p2 p3 p4"  # F1 vs gold2 = 0.4, vs gold1 = 0.0

        link1 = _link_with_text("sl.g1", "gold.1", gold1_text, "S1")
        link2 = _link_with_text("sl.g2", "gold.2", gold2_text, "S2")
        pred_a = SpeakerAttributionPrediction(sentence_id="abstract-0", predicted_speaker="S1", text=pred_a_text)
        pred_b = SpeakerAttributionPrediction(sentence_id="abstract-1", predicted_speaker="S2", text=pred_b_text)

        report = compute_saer_m([link1, link2], [pred_a, pred_b])

        by_id = {r.sentence_id: r for r in report.per_sentence}
        assert by_id["gold.1"].outcome == "correct"
        assert by_id["gold.1"].predicted_speaker == "S1"
        assert by_id["gold.2"].outcome == "correct"
        assert by_id["gold.2"].predicted_speaker == "S2"
        assert report.accuracy == pytest.approx(1.0)

    def test_align_predictions_to_gold_sentences_is_one_to_one_directly(self):
        gold1_text = "kappa lambda mu nu"
        gold2_text = "kappa lambda golf hotel"
        pred_a_text = "kappa lambda mu nu"
        pred_b_text = "golf hotel p1 p2 p3 p4"

        evidence_links = [
            _link_with_text("sl.g1", "gold.1", gold1_text, "S1"),
            _link_with_text("sl.g2", "gold.2", gold2_text, "S2"),
        ]
        predictions = [
            SpeakerAttributionPrediction(sentence_id="abstract-0", predicted_speaker="S1", text=pred_a_text),
            SpeakerAttributionPrediction(sentence_id="abstract-1", predicted_speaker="S2", text=pred_b_text),
        ]
        gold_speakers = {"gold.1": ("S1",), "gold.2": ("S2",)}

        aligned = align_predictions_to_gold_sentences(evidence_links, predictions, gold_speakers)

        aligned_ids = {p.sentence_id for p in aligned}
        assert aligned_ids == {"gold.1", "gold.2"}  # both predictions were claimed, none left "abstract-N"


class TestAlignmentDeterminism:
    def test_repeated_calls_produce_identical_reports(self):
        evidence_links = [
            _link_with_text("sl.g1", "ES2011a.s.1", "The finance subgroup approved the design budget.", "S1"),
            _link_with_text("sl.g2", "ES2011a.s.2", "The team scheduled a follow-up meeting for Friday.", "S2"),
        ]
        predictions = [
            SpeakerAttributionPrediction(
                sentence_id="abstract-0", predicted_speaker="S1", text="Finance subgroup approved the budget."
            ),
            SpeakerAttributionPrediction(
                sentence_id="actions-0", predicted_speaker="S2", text="Team scheduled a follow-up for Friday."
            ),
            SpeakerAttributionPrediction(sentence_id="problems-0", predicted_speaker=None, text="No blockers noted."),
        ]

        first = compute_saer_m(evidence_links, predictions)
        second = compute_saer_m(evidence_links, predictions)

        assert first == second
        assert first.per_sentence == second.per_sentence


class TestSpeakerAttributionPredictionTextField:
    def test_text_defaults_to_none_for_backward_compatibility(self):
        assert SpeakerAttributionPrediction(sentence_id="s.1", predicted_speaker="spk_a").text is None
