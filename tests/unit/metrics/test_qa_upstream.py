from __future__ import annotations

import pytest

from meeting_minutes_agent.metrics.qa import QAExample
from meeting_minutes_agent.metrics.qa_upstream import (
    UpstreamMeetingQAScoreReport,
    upstream_meetingqa_exact_match,
    upstream_meetingqa_f1,
    upstream_meetingqa_normalize_answer,
    upstream_meetingqa_remove_speaker_prefixes,
    upstream_meetingqa_score_example,
    upstream_meetingqa_score_examples,
    upstream_meetingqa_tokens,
)

# ---------------------------------------------------------------------------
# Normalization layer -- HF squad_v2 compute_score.py's normalize_answer,
# transcribed in qa_upstream.py's module docstring (design choices) with the
# live-source cross-check recorded there.
# ---------------------------------------------------------------------------


def test_normalize_answer_deletes_punctuation_without_inserting_a_space():
    # Contrast .qa.normalize_answer, which replaces punctuation with a
    # space (splitting "don't" into two tokens); upstream deletes the
    # character outright, merging "don't" into one token "dont".
    assert upstream_meetingqa_normalize_answer("Isn't it, Bob?") == "isnt it bob"


def test_normalize_answer_removes_whole_word_articles_only():
    # "a" inside "and"/"about" must NOT be touched (word-boundary regex);
    # only the standalone article tokens "the"/"a" are removed.
    assert upstream_meetingqa_normalize_answer("The cats and a dog") == "cats and dog"


def test_normalize_answer_has_no_number_word_handling():
    # Contrast .qa.normalize_answer's "twenty" -> "20"; upstream has no
    # such step at all.
    assert upstream_meetingqa_normalize_answer("twenty dollars") == "twenty dollars"


def test_normalize_answer_collapses_whitespace_left_by_article_removal():
    assert upstream_meetingqa_normalize_answer("the the") == ""


def test_get_tokens_of_falsy_string_is_empty_list():
    assert upstream_meetingqa_tokens("") == []


def test_get_tokens_of_degenerate_nonfalsy_string_still_splits_normalized_empty():
    # "the" is truthy going IN, so get_tokens calls normalize_answer("the").split()
    # rather than short-circuiting; normalize_answer("the") == "" and "".split() == [].
    # Same end result as the falsy-string branch, different code path -- both are
    # exercised by name here per qa_upstream.py's docstring on upstream_meetingqa_tokens.
    assert upstream_meetingqa_tokens("the") == []


def test_remove_speaker_prefixes_strips_digits_variant():
    assert (
        upstream_meetingqa_remove_speaker_prefixes("Speaker 3: Hello. Speaker 12: Bye.") == "Hello. Bye."
    )


def test_remove_speaker_prefixes_zero_digit_variant():
    assert upstream_meetingqa_remove_speaker_prefixes("Speaker : mystery") == "mystery"


def test_remove_speaker_prefixes_not_anchored_to_string_start():
    assert upstream_meetingqa_remove_speaker_prefixes("intro Speaker 1: mid text") == "intro mid text"


def test_remove_speaker_prefixes_no_match_is_identity():
    assert upstream_meetingqa_remove_speaker_prefixes("no prefix here") == "no prefix here"


# ---------------------------------------------------------------------------
# compute_exact / compute_f1 primitives -- hand-computed
# ---------------------------------------------------------------------------


def test_exact_match_after_article_normalization():
    # "the Denver Broncos" vs "Denver Broncos": upstream's article removal
    # makes these normalize identically even though .qa's normalizer
    # (no article removal) would not.
    assert upstream_meetingqa_exact_match("the Denver Broncos", "Denver Broncos") == 1.0


def test_f1_partial_overlap_hand_computed():
    # tokens gold: [super, bowl, 50] (3); tokens pred: [super, bowl, l] (3).
    # common = {super, bowl} -> num_same = 2.
    # precision = 2/3, recall = 2/3 -> F1 = 2*(2/3*2/3)/(4/3) = 2/3.
    assert upstream_meetingqa_f1("Super Bowl 50", "Super Bowl L") == pytest.approx(2 / 3)
    assert upstream_meetingqa_exact_match("Super Bowl 50", "Super Bowl L") == 0.0


def test_f1_both_empty_is_perfect():
    assert upstream_meetingqa_f1("", "") == 1.0
    assert upstream_meetingqa_exact_match("", "") == 1.0


def test_f1_one_side_empty_is_zero():
    assert upstream_meetingqa_f1("", "Denver") == 0.0
    assert upstream_meetingqa_f1("Denver", "") == 0.0


def test_f1_no_overlap_is_zero():
    assert upstream_meetingqa_f1("Paris", "London") == 0.0


# ---------------------------------------------------------------------------
# Per-example scoring -- hand-computed, mirroring test_qa.py's QAExample
# fixtures so the two families are easy to compare line by line.
# ---------------------------------------------------------------------------


def test_score_example_exact_match():
    example = QAExample("u1", reference_spans=("Paris",), prediction_spans=("Paris",))
    score = upstream_meetingqa_score_example(example)
    assert score.upstream_meetingqa_f1 == pytest.approx(1.0)
    assert score.upstream_meetingqa_exact_match == pytest.approx(1.0)
    assert score.scored_prediction_text == "Paris"
    assert score.scored_gold_answers == ("Paris",)


def test_score_example_correct_abstention_on_unanswerable():
    example = QAExample("u2", reference_spans=(), prediction_spans=())
    score = upstream_meetingqa_score_example(example)
    assert score.upstream_meetingqa_f1 == pytest.approx(1.0)
    assert score.upstream_meetingqa_exact_match == pytest.approx(1.0)
    assert score.scored_prediction_text == ""
    # Empty reference_spans falls back to the upstream no-answer sentinel.
    assert score.scored_gold_answers == ("",)


def test_score_example_hallucinated_answer_on_unanswerable():
    example = QAExample("u3", reference_spans=(), prediction_spans=("some answer",))
    score = upstream_meetingqa_score_example(example)
    assert score.upstream_meetingqa_f1 == pytest.approx(0.0)
    assert score.upstream_meetingqa_exact_match == pytest.approx(0.0)


def test_score_example_gold_multi_span_is_max_over_alternatives_not_a_join():
    # reference has TWO distinct spans; prediction covers only the FIRST
    # one, verbatim. Upstream treats the two gold spans as alternative
    # candidate answers and keeps the MAX score -- matching span 1 exactly
    # scores a perfect 1.0/1.0 even though span 2 was never mentioned.
    # (Compare test_qa_comparison.py, which shows .qa's flatten-then-score
    # gives this same example a materially LOWER score.)
    example = QAExample(
        "u4",
        reference_spans=("we should think about a prototype", "duplication of effort is the issue"),
        prediction_spans=("we should think about a prototype",),
    )
    score = upstream_meetingqa_score_example(example)
    assert score.upstream_meetingqa_f1 == pytest.approx(1.0)
    assert score.upstream_meetingqa_exact_match == pytest.approx(1.0)
    assert score.scored_prediction_text == "we should think about a prototype"
    assert score.scored_gold_answers == (
        "we should think about a prototype",
        "duplication of effort is the issue",
    )


def test_score_example_degenerate_article_only_gold_scores_as_unanswerable():
    # Gold is a single span consisting ONLY of the article "a". Structurally
    # this is an ANSWERABLE example (reference_spans is non-empty), but
    # upstream's normalize_answer("a") == "" filters it out of gold_answers
    # entirely, falling back to the no-answer sentinel [""] -- so ANY
    # non-empty prediction, however good, scores 0 against it. (Compare
    # test_qa_comparison.py, which shows .qa scores this example's genuine
    # partial token overlap with "a" instead.)
    example = QAExample("u5", reference_spans=("a",), prediction_spans=("a lot",))
    score = upstream_meetingqa_score_example(example)
    assert score.upstream_meetingqa_f1 == pytest.approx(0.0)
    assert score.upstream_meetingqa_exact_match == pytest.approx(0.0)
    assert score.scored_gold_answers == ("",)


def test_score_example_speaker_prefix_stripped_identically_on_both_sides():
    # Different speaker numbers on the two sides must not affect the score
    # once both are stripped -- and scored_prediction_text/scored_gold_answers
    # show the prefix-free text that was actually compared.
    example = QAExample(
        "u6",
        reference_spans=("Speaker 3: The budget is fine.",),
        prediction_spans=("Speaker 7: The budget is fine.",),
    )
    score = upstream_meetingqa_score_example(example)
    assert score.upstream_meetingqa_f1 == pytest.approx(1.0)
    assert score.upstream_meetingqa_exact_match == pytest.approx(1.0)
    assert score.scored_prediction_text == "The budget is fine."
    assert score.scored_gold_answers == ("The budget is fine.",)


def test_score_example_prediction_multi_span_is_joined_with_a_space():
    # Structured (list-of-spans) prediction on an ordinary single-span
    # gold: the two predicted spans are joined with " " before scoring,
    # matching the --pred-ref-type path (qa_upstream.py design choice 2).
    example = QAExample("u7", reference_spans=("cat sat mat",), prediction_spans=("cat sat", "mat"))
    score = upstream_meetingqa_score_example(example)
    assert score.scored_prediction_text == "cat sat mat"
    assert score.upstream_meetingqa_f1 == pytest.approx(1.0)
    assert score.upstream_meetingqa_exact_match == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Pooled report
# ---------------------------------------------------------------------------


def test_score_examples_rejects_empty_list():
    with pytest.raises(ValueError):
        upstream_meetingqa_score_examples([])


def test_score_examples_macro_averages_hand_computed():
    examples = [
        QAExample("u1", ("Paris",), ("Paris",)),  # f1=1.0, em=1.0
        QAExample("u2", (), ()),  # f1=1.0, em=1.0
        QAExample("u3", (), ("some answer",)),  # f1=0.0, em=0.0
        QAExample("u5", ("a",), ("a lot",)),  # f1=0.0, em=0.0
    ]
    report = upstream_meetingqa_score_examples(examples)
    assert isinstance(report, UpstreamMeetingQAScoreReport)
    assert report.n_examples == 4
    assert report.upstream_meetingqa_macro_f1 == pytest.approx((1.0 + 1.0 + 0.0 + 0.0) / 4)
    assert report.upstream_meetingqa_macro_exact_match == pytest.approx((1.0 + 1.0 + 0.0 + 0.0) / 4)
    assert len(report.per_example) == 4
    assert [s.example_id for s in report.per_example] == ["u1", "u2", "u3", "u5"]
