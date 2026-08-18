"""ROUGE legacy row -- rouge-score wrappers, clearly labeled LEGACY, never a
headline metric for this repository (word-overlap summarization metrics
correlate poorly with factual accuracy; the task brief pins this as a
legacy row only).

Also provides a stub interface for the faithfulness ensemble the eventual
protocol wants (AlignScore / SummaC / QAFactEval): named functions that
raise :class:`FaithfulnessScorerNotInstalled` with an explicit message.
These packages are NOT installed in the shared venv and must not be
installed by an agent -- the task brief is explicit: "do not install
them". The stub exists so downstream code can reference the intended
interface today and get a clear, actionable error instead of an
``ImportError`` deep in a third-party stack trace.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

__all__ = [
    "RougeScore",
    "compute_rouge_legacy",
    "FaithfulnessScorerNotInstalled",
    "align_score",
    "summac_score",
    "qafacteval_score",
]

DEFAULT_ROUGE_TYPES: tuple[str, ...] = ("rouge1", "rouge2", "rougeL")


@dataclass(frozen=True)
class RougeScore:
    precision: float
    recall: float
    fmeasure: float


def compute_rouge_legacy(
    prediction: str,
    reference: str,
    *,
    rouge_types: Sequence[str] = DEFAULT_ROUGE_TYPES,
    use_stemmer: bool = False,
) -> dict[str, RougeScore]:
    """LEGACY row only -- see module docstring. Thin wrapper around
    ``rouge_score.rouge_scorer.RougeScorer``; no reimplementation."""

    from rouge_score import rouge_scorer

    scorer = rouge_scorer.RougeScorer(list(rouge_types), use_stemmer=use_stemmer)
    raw = scorer.score(reference, prediction)
    return {
        rouge_type: RougeScore(precision=s.precision, recall=s.recall, fmeasure=s.fmeasure)
        for rouge_type, s in raw.items()
    }


class FaithfulnessScorerNotInstalled(RuntimeError):
    """Raised by every faithfulness-ensemble stub below. Not a bug --
    these scorers are intentionally not installed (owner-scoped E5 task
    brief: meeteval + jiwer + rouge-score only, no further installs)."""


def _not_installed_stub(name: str):
    def _stub(*_args, **_kwargs):
        raise FaithfulnessScorerNotInstalled(
            f"{name} is NOT INSTALLED in this environment. This is a placeholder interface for "
            f"the future faithfulness-ensemble row (AlignScore / SummaC / QAFactEval) named in the "
            f"2026-08-17 founding workplan's E5 row -- do not install {name} without explicit "
            f"owner approval; this stub exists only so calling code has a stable interface to "
            f"target ahead of that decision."
        )

    _stub.__name__ = f"{name.lower()}_score"
    return _stub


align_score = _not_installed_stub("AlignScore")
summac_score = _not_installed_stub("SummaC")
qafacteval_score = _not_installed_stub("QAFactEval")
