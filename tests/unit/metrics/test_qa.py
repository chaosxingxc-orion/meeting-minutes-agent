from __future__ import annotations

import pytest

from meeting_minutes_agent.metrics.qa import (
    DEFAULT_NORMALIZATION_RULES,
    NormalizationRules,
    QAExample,
    normalize_answer,
    score_example,
    score_qa_examples,
)

# ---------------------------------------------------------------------------
# Normalization layer
# ---------------------------------------------------------------------------


def test_normalize_answer_lowercases_and_strips_punctuation():
    assert normalize_answer("Paris!") == "paris"


def test_normalize_answer_number_word_to_digit():
    assert normalize_answer("twenty dollars") == "20 dollars"


def test_normalize_answer_thousands_comma_removed_before_punct_strip():
    assert normalize_answer("1,000 attendees") == "1000 attendees"


def test_normalize_answer_collapses_whitespace():
    assert normalize_answer("  hello   world  ") == "hello world"


def test_normalize_answer_number_form_disabled_leaves_words_literal():
    rules = NormalizationRules(normalize_number_form=False)
    assert normalize_answer("twenty dollars", rules) == "twenty dollars"


def test_normalize_answer_punctuation_disabled_keeps_punctuation():
    rules = NormalizationRules(strip_punctuation=False)
    assert normalize_answer("Paris!", rules) == "paris!"


def test_rule_list_reflects_active_rules():
    assert DEFAULT_NORMALIZATION_RULES.rule_list() == (
        "lowercase",
        "normalize_number_form",
        "strip_punctuation",
        "collapse_whitespace",
    )
    assert NormalizationRules(lowercase=False).rule_list() == (
        "normalize_number_form",
        "strip_punctuation",
        "collapse_whitespace",
    )


def test_normalization_rules_content_hash_deterministic_and_sensitive():
    a = NormalizationRules()
    b = NormalizationRules()
    c = NormalizationRules(lowercase=False)
    assert a.content_hash() == b.content_hash()
    assert a.content_hash() != c.content_hash()


# ---------------------------------------------------------------------------
# Per-example scoring -- hand-computed
# ---------------------------------------------------------------------------


def test_exact_match_scores_f1_and_iou_of_one():
    example = QAExample("q1", reference_spans=("Paris",), prediction_spans=("Paris",))
    score = score_example(example)
    assert score.f1 == pytest.approx(1.0)
    assert score.iou == pytest.approx(1.0)


def test_partial_overlap_hand_computed():
    # pred tokens: [the, eiffel, tower] (3); ref tokens: [eiffel, tower] (2).
    # common = {eiffel, tower} -> num_same = 2.
    # precision = 2/3, recall = 2/2 = 1 -> F1 = 2*(2/3*1)/(2/3+1) = 0.8.
    # IoU: |{the,eiffel,tower} & {eiffel,tower}| / |union of 3| = 2/3.
    example = QAExample("q2", reference_spans=("eiffel tower",), prediction_spans=("the eiffel tower",))
    score = score_example(example)
    assert score.f1 == pytest.approx(0.8)
    assert score.iou == pytest.approx(2 / 3)


def test_no_overlap_scores_zero():
    example = QAExample("q3", reference_spans=("Paris",), prediction_spans=("London",))
    score = score_example(example)
    assert score.f1 == pytest.approx(0.0)
    assert score.iou == pytest.approx(0.0)


def test_correct_abstention_on_unanswerable_scores_one():
    example = QAExample("q4", reference_spans=(), prediction_spans=())
    score = score_example(example)
    assert score.f1 == pytest.approx(1.0)
    assert score.iou == pytest.approx(1.0)
    assert score.is_unanswerable is True
    assert score.correctly_abstained is True
    assert score.falsely_abstained is False


def test_hallucinated_answer_on_unanswerable_scores_zero():
    example = QAExample("q5", reference_spans=(), prediction_spans=("some answer",))
    score = score_example(example)
    assert score.f1 == pytest.approx(0.0)
    assert score.iou == pytest.approx(0.0)
    assert score.correctly_abstained is False


def test_false_abstention_on_answerable_scores_zero():
    example = QAExample("q6", reference_spans=("42",), prediction_spans=())
    score = score_example(example)
    assert score.f1 == pytest.approx(0.0)
    assert score.falsely_abstained is True


def test_multi_span_flattened_bag_hand_computed():
    # reference spans -> tokens [alice, bob]; prediction spans -> [alice, charlie].
    # common = {alice} -> num_same = 1. precision = 1/2, recall = 1/2 -> F1 = 0.5.
    # IoU: |{alice,bob} & {alice,charlie}| / |{alice,bob,charlie}| = 1/3.
    example = QAExample("q7", reference_spans=("alice", "bob"), prediction_spans=("alice", "charlie"))
    score = score_example(example)
    assert score.is_multi_span is True
    assert score.f1 == pytest.approx(0.5)
    assert score.iou == pytest.approx(1 / 3)


# ---------------------------------------------------------------------------
# Pooled report
# ---------------------------------------------------------------------------


def test_score_qa_examples_rejects_empty_list():
    with pytest.raises(ValueError):
        score_qa_examples([])


def test_score_qa_examples_macro_averages_and_sub_metrics():
    examples = [
        QAExample("q1", ("Paris",), ("Paris",)),  # answerable, correct, f1=1.0
        QAExample("q4", (), ()),  # unanswerable, correctly abstained, f1=1.0
        QAExample("q5", (), ("some answer",)),  # unanswerable, hallucinated, f1=0.0
        QAExample("q6", ("42",), ()),  # answerable, falsely abstained, f1=0.0
        QAExample("q7", ("alice", "bob"), ("alice", "charlie")),  # multi-span, f1=0.5
    ]
    report = score_qa_examples(examples)

    assert report.n_examples == 5
    assert report.macro_f1 == pytest.approx((1.0 + 1.0 + 0.0 + 0.0 + 0.5) / 5)

    # Unanswerable: q4 (correct) + q5 (hallucinated) -> accuracy 1/2.
    assert report.n_unanswerable == 2
    assert report.abstention_accuracy == pytest.approx(0.5)

    # Answerable: q1 (attempted) + q6 (falsely abstained) + q7 (attempted) -> 1/3 falsely abstained.
    assert report.n_answerable == 3
    assert report.false_abstention_rate == pytest.approx(1 / 3)

    assert report.n_multi_span == 1
    assert report.multi_span_macro_f1 == pytest.approx(0.5)
    assert report.multi_span_macro_iou == pytest.approx(1 / 3)

    assert report.normalization_rules == DEFAULT_NORMALIZATION_RULES.rule_list()
    assert report.normalization_rules_hash == DEFAULT_NORMALIZATION_RULES.content_hash()
    assert len(report.per_example) == 5


def test_score_qa_examples_reports_none_sub_metrics_when_category_absent():
    examples = [QAExample("q1", ("Paris",), ("Paris",))]
    report = score_qa_examples(examples)
    assert report.n_unanswerable == 0
    assert report.abstention_accuracy is None
    assert report.n_multi_span == 0
    assert report.multi_span_macro_f1 is None
    assert report.multi_span_macro_iou is None
