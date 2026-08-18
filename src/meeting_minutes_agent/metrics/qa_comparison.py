"""Side-by-side comparability report between this repository's own headline
MeetingQA scorer (:mod:`.qa`) and the faithful upstream-scorer
reimplementation (:mod:`.qa_upstream`), run over the SAME
predictions/gold, plus a divergence report flagging examples where the two
disagree materially.

This module exists to close the upstream-scorer comparability gap: it never
changes, wraps, or re-exports either metric family as "the" score -- it only
juxtaposes them. See :mod:`.qa_upstream`'s module docstring (design choices
1-3) for WHY the two families are expected to diverge on gold multi-span
answers and on degenerate (article/stopword-only) gold spans; this module's
own tests build hand-computed fixtures that exhibit both."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .qa import QAExample, QAScoreReport, score_qa_examples
from .qa_upstream import UpstreamMeetingQAScoreReport, upstream_meetingqa_score_examples

# Strictly-greater-than threshold on |ours.f1 - upstream.f1| for an example
# to be flagged as a "material" divergence in the report. 0.2 is a bounded,
# documented default (not tuned against any dataset) chosen to be well above
# ordinary floating-point/formula noise (e.g. the 1/3-vs-1/2-token-count
# rounding seen in small hand fixtures) while still catching the
# abstention-convention and multi-span-joining gaps this module exists to
# surface; callers scoring larger example sets should pass their own
# threshold rather than rely on this default.
DEFAULT_DIVERGENCE_THRESHOLD = 0.2


@dataclass(frozen=True)
class QAComparisonRow:
    """One example's two scores side by side. ``f1_gap`` is signed:
    positive means :mod:`.qa` scored the example higher than the upstream
    reimplementation, negative means the reverse."""

    example_id: str
    ours_f1: float
    ours_iou: float
    upstream_f1: float
    upstream_exact_match: float
    f1_gap: float
    is_material_divergence: bool


@dataclass(frozen=True)
class QAComparisonReport:
    n_examples: int
    ours: QAScoreReport
    upstream: UpstreamMeetingQAScoreReport
    rows: tuple[QAComparisonRow, ...]
    divergent_rows: tuple[QAComparisonRow, ...]
    divergence_threshold: float


def compare_qa_examples(
    examples: Sequence[QAExample],
    divergence_threshold: float = DEFAULT_DIVERGENCE_THRESHOLD,
) -> QAComparisonReport:
    """Score ``examples`` with both metric families and return them side by
    side. Raises the same ``ValueError`` as :func:`.qa.score_qa_examples`
    on an empty ``examples`` (both scorers require non-empty input; this
    surfaces that early with one message rather than one scorer's)."""

    if not examples:
        raise ValueError("compare_qa_examples: examples must be non-empty")

    ours_report = score_qa_examples(examples)
    upstream_report = upstream_meetingqa_score_examples(examples)

    rows: list[QAComparisonRow] = []
    for ours_score, upstream_score in zip(ours_report.per_example, upstream_report.per_example, strict=True):
        # Both reports are built from the same `examples` sequence in the
        # same order (score_qa_examples/upstream_meetingqa_score_examples
        # both preserve input order via a plain per-example map), so the
        # zip is aligned by position; this assertion catches a future
        # refactor that breaks that invariant rather than silently
        # mispairing rows.
        assert ours_score.example_id == upstream_score.example_id
        gap = ours_score.f1 - upstream_score.upstream_meetingqa_f1
        rows.append(
            QAComparisonRow(
                example_id=ours_score.example_id,
                ours_f1=ours_score.f1,
                ours_iou=ours_score.iou,
                upstream_f1=upstream_score.upstream_meetingqa_f1,
                upstream_exact_match=upstream_score.upstream_meetingqa_exact_match,
                f1_gap=gap,
                is_material_divergence=abs(gap) > divergence_threshold,
            )
        )

    rows_t = tuple(rows)
    divergent = tuple(row for row in rows_t if row.is_material_divergence)
    return QAComparisonReport(
        n_examples=len(examples),
        ours=ours_report,
        upstream=upstream_report,
        rows=rows_t,
        divergent_rows=divergent,
        divergence_threshold=divergence_threshold,
    )


__all__ = [
    "DEFAULT_DIVERGENCE_THRESHOLD",
    "QAComparisonRow",
    "QAComparisonReport",
    "compare_qa_examples",
]
