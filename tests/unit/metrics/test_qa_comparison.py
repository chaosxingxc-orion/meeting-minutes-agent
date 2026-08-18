from __future__ import annotations

import pytest

from meeting_minutes_agent.metrics.qa import QAExample
from meeting_minutes_agent.metrics.qa_comparison import (
    DEFAULT_DIVERGENCE_THRESHOLD,
    QAComparisonReport,
    compare_qa_examples,
)

# ---------------------------------------------------------------------------
# Agreement case -- both families should score an exact single-span match
# identically, so nothing is flagged.
# ---------------------------------------------------------------------------


def test_agreeing_example_is_not_flagged():
    example = QAExample("c1", reference_spans=("Paris",), prediction_spans=("Paris",))
    report = compare_qa_examples([example])

    assert isinstance(report, QAComparisonReport)
    assert report.n_examples == 1
    row = report.rows[0]
    assert row.example_id == "c1"
    assert row.ours_f1 == pytest.approx(1.0)
    assert row.upstream_f1 == pytest.approx(1.0)
    assert row.f1_gap == pytest.approx(0.0)
    assert row.is_material_divergence is False
    assert report.divergent_rows == ()
    assert report.divergence_threshold == DEFAULT_DIVERGENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Divergence source 1 (abstention/unanswerable-convention handling): a
# structurally-answerable gold span that is nothing but an article
# degenerates to upstream's no-answer sentinel, but .qa scores it as an
# ordinary partial-overlap answer. Hand-computed in both directions:
#
#   .qa:  ref_tokens=["a"], pred_tokens=["a","lot"].
#         common={"a"} -> num_same=1. precision=1/2, recall=1/1=1.
#         F1 = 2*(0.5*1)/(0.5+1) = 2/3.
#   upstream: normalize_answer("a") == "" -> gold_answers falls back to
#         ("",); prediction "a lot" normalizes to "lot" (nonempty) -> the
#         empty/nonempty mismatch forces F1 = 0.0 regardless of the "a"
#         overlap .qa credits.
# ---------------------------------------------------------------------------


def test_degenerate_article_only_gold_is_a_material_divergence():
    example = QAExample("c2", reference_spans=("a",), prediction_spans=("a lot",))
    report = compare_qa_examples([example])

    row = report.rows[0]
    assert row.ours_f1 == pytest.approx(2 / 3)
    assert row.upstream_f1 == pytest.approx(0.0)
    assert row.f1_gap == pytest.approx(2 / 3)
    assert row.is_material_divergence is True
    assert report.divergent_rows == (row,)


# ---------------------------------------------------------------------------
# Divergence source 2 (multi-span joining/aggregation): gold has two
# genuinely distinct spans; the prediction covers only the first one,
# verbatim.
#
#   .qa: flattens BOTH gold spans into one 12-token bag and scores the
#        6-token prediction against the union -> partial credit.
#        pred_tokens=[we,should,think,about,a,prototype] (6);
#        ref_tokens = span1 tokens (6) + span2 tokens (6) = 12.
#        common = 6 (all of span1). precision=6/6=1, recall=6/12=0.5.
#        F1 = 2*(1*0.5)/(1.5) = 2/3.
#   upstream: takes the MAX over the two gold spans as independent
#        alternatives; matching span 1 exactly scores a perfect 1.0,
#        with span 2 never counted against the prediction at all.
#
# Note the gap is NEGATIVE here (upstream scores higher) -- the opposite
# sign from the abstention fixture above, so both directions of the
# divergence are exercised.
# ---------------------------------------------------------------------------


def test_gold_multi_span_joining_is_a_material_divergence():
    example = QAExample(
        "c3",
        reference_spans=("we should think about a prototype", "duplication of effort is the issue"),
        prediction_spans=("we should think about a prototype",),
    )
    report = compare_qa_examples([example])

    row = report.rows[0]
    assert row.ours_f1 == pytest.approx(2 / 3)
    assert row.upstream_f1 == pytest.approx(1.0)
    assert row.f1_gap == pytest.approx(2 / 3 - 1.0)
    assert row.f1_gap < 0
    assert row.is_material_divergence is True
    assert report.divergent_rows == (row,)


# ---------------------------------------------------------------------------
# Threshold behavior and report-level plumbing
# ---------------------------------------------------------------------------


def test_custom_divergence_threshold_suppresses_a_flag():
    example = QAExample("c2", reference_spans=("a",), prediction_spans=("a lot",))
    report = compare_qa_examples([example], divergence_threshold=0.9)
    assert report.divergence_threshold == 0.9
    assert report.rows[0].is_material_divergence is False
    assert report.divergent_rows == ()


def test_rows_preserve_input_order_and_report_carries_both_pooled_reports():
    examples = [
        QAExample("c1", ("Paris",), ("Paris",)),
        QAExample("c2", ("a",), ("a lot",)),
        QAExample("c3", ("we should think about a prototype", "duplication of effort is the issue"),
                  ("we should think about a prototype",)),
    ]
    report = compare_qa_examples(examples)

    assert [row.example_id for row in report.rows] == ["c1", "c2", "c3"]
    assert report.n_examples == 3
    assert len(report.divergent_rows) == 2  # c2 and c3, not c1

    # The pooled reports underneath are the SAME shapes .qa/.qa_upstream
    # produce standalone -- this utility juxtaposes, it does not recompute.
    assert report.ours.macro_f1 == pytest.approx((1.0 + 2 / 3 + 2 / 3) / 3)
    assert report.upstream.upstream_meetingqa_macro_f1 == pytest.approx((1.0 + 0.0 + 1.0) / 3)


def test_compare_qa_examples_rejects_empty_list():
    with pytest.raises(ValueError):
        compare_qa_examples([])
