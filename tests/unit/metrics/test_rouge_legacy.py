"""rouge-score-dependent tests -- gated on import availability
(`pytest.importorskip`), meant to run in the WSL2 shared venv where
rouge-score is installed."""

from __future__ import annotations

import pytest

pytest.importorskip("rouge_score")

from meeting_minutes_agent.metrics.rouge_legacy import (
    FaithfulnessScorerNotInstalled,
    align_score,
    compute_rouge_legacy,
    qafacteval_score,
    summac_score,
)


def test_identical_text_scores_perfect_rouge_on_every_type():
    # Prediction == reference -> every rouge type must score a perfect
    # 1.0 precision/recall/fmeasure regardless of the library's internal
    # n-gram/LCS mechanics -- this is true by definition of "identical".
    text = "the quick brown fox jumps over the lazy dog"
    scores = compute_rouge_legacy(text, text)
    assert set(scores) == {"rouge1", "rouge2", "rougeL"}
    for rouge_type, score in scores.items():
        assert score.precision == pytest.approx(1.0), rouge_type
        assert score.recall == pytest.approx(1.0), rouge_type
        assert score.fmeasure == pytest.approx(1.0), rouge_type


def test_completely_disjoint_text_scores_zero():
    scores = compute_rouge_legacy("alpha beta gamma", "one two three")
    for rouge_type, score in scores.items():
        assert score.fmeasure == pytest.approx(0.0), rouge_type


def test_custom_rouge_types_selection():
    scores = compute_rouge_legacy("a b c", "a b c", rouge_types=("rouge1",))
    assert set(scores) == {"rouge1"}


def test_faithfulness_stubs_raise_with_explicit_not_installed_message():
    for stub, name in [(align_score, "AlignScore"), (summac_score, "SummaC"), (qafacteval_score, "QAFactEval")]:
        with pytest.raises(FaithfulnessScorerNotInstalled, match=f"{name} is NOT INSTALLED"):
            stub("prediction", "reference")


def test_faithfulness_stubs_never_silently_succeed():
    with pytest.raises(FaithfulnessScorerNotInstalled):
        align_score()
