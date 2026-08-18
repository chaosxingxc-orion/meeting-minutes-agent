"""P-PROMPT offline scoring path: parsed replies -> per-slice cpWER-family
scores -> per-cell aggregates -> the mechanical winner rule + the corrupt-
context verdicts, EXACTLY as registered
(``docs/readiness/2026-08-18-pprompt-preregistration.md`` SS4).

Read-only and OFFLINE, per mission scope: every function here scores
already-collected records against the AMI gold transcript; nothing performs
a model or network call. Every WER-family number is produced by
:mod:`meeting_minutes_agent.probes.pattr_scoring` -- this module never
reimplements cpWER/confusion-cost math, it only adds what P-PROMPT needs on
top: grammar-compliance scoring, per-cell aggregation, and the two
registered mechanical rules (winner selection, corrupt-arm verdict).

Grammar-compliance rate (prereg: "parseable lines / total lines"): reuses
:func:`meeting_minutes_agent.heads.transcribe_attribute.
parse_transcribe_attribute_response` -- the SAME parser the transcribe-
attribute head itself defines, never a second, drifting implementation.
A reply that parses to ZERO segments (including a genuinely empty reply) is
never handed to meeteval (whose ORC-WER implementation can trip an internal
assertion on an empty hypothesis, per
:func:`meeting_minutes_agent.probes.pattr_scoring.score_arm`'s own
docstring): it is instead recorded as the worst-case cpWER (1.0, matching
cpWER's own definition when the hypothesis is empty: every reference word
is a deletion) with ``hypothesis_empty=True`` on its
:class:`SliceScore`, never silently dropped from a cell's mean.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..heads.transcribe_attribute import parse_transcribe_attribute_response
from ..metrics.pins import MetricPins
from ..metrics.timestamps import PerSpeakerSegment
from .pattr_scoring import extract_gold_streams_for_range, hypothesis_stream_from_grid_or_free_parse, score_arm
from .pprompt import ARM_X1, ARM_X2, ARRANGEMENTS, GRID_CELLS, REFERENCE_CELL, TEMPLATES

__all__ = [
    "COMPLIANCE_GATE",
    "TIE_SET_MARGIN",
    "CONTEXT_SENSITIVE_THRESHOLD",
    "CONTEXT_INERT_THRESHOLD",
    "GRAMMAR_BLOCKED",
    "grammar_compliance",
    "SliceScore",
    "score_slice",
    "CellScore",
    "aggregate_cell",
    "aggregate_by_arm",
    "WinnerResult",
    "apply_winner_rule",
    "CorruptVerdict",
    "evaluate_corrupt_arm",
    "evaluate_all_corrupt_arms",
    "PromptSweepOutputExistsError",
    "assert_one_shot_output_dir",
]

# ---------------------------------------------------------------------------
# grammar compliance
# ---------------------------------------------------------------------------


def grammar_compliance(raw_text: str):
    """``(compliance_rate, parse_result)``. ``compliance_rate`` is
    ``len(parsed segments) / (parsed segments + malformed lines)``, or
    ``0.0`` when the reply carried no non-blank lines at all (an empty reply
    is never vacuously "fully compliant")."""

    parsed = parse_transcribe_attribute_response(raw_text)
    total_lines = len(parsed.segments) + len(parsed.malformed_lines)
    rate = (len(parsed.segments) / total_lines) if total_lines else 0.0
    return rate, parsed


# ---------------------------------------------------------------------------
# per-slice scoring
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SliceScore:
    arm: str
    meeting_id: str
    slice_index: int
    cp_wer: float
    confusion_cost: float
    compliance: float
    n_reference_segments: int
    n_hypothesis_segments: int
    n_malformed_lines: int
    hypothesis_empty: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "meeting_id": self.meeting_id,
            "slice_index": self.slice_index,
            "cp_wer": self.cp_wer,
            "confusion_cost": self.confusion_cost,
            "compliance": self.compliance,
            "n_reference_segments": self.n_reference_segments,
            "n_hypothesis_segments": self.n_hypothesis_segments,
            "n_malformed_lines": self.n_malformed_lines,
            "hypothesis_empty": self.hypothesis_empty,
        }


def score_slice(
    arm: str,
    meeting_id: str,
    slice_index: int,
    reference: Sequence[PerSpeakerSegment],
    raw_reply_text: str,
    *,
    slice_start: float,
    slice_end: float,
    pins: MetricPins | None = None,
) -> SliceScore:
    """Score one arm's one slice reply against its already-extracted gold
    reference stream (:func:`~.pattr_scoring.extract_gold_streams_for_range`
    is the caller's own job -- this function takes the reference stream
    directly, never a ``ResolvedMeeting``, keeping this module corpus-
    access-free)."""

    compliance, parsed = grammar_compliance(raw_reply_text)
    if not parsed.segments:
        return SliceScore(
            arm=arm,
            meeting_id=meeting_id,
            slice_index=slice_index,
            cp_wer=1.0,
            confusion_cost=0.0,
            compliance=compliance,
            n_reference_segments=len(reference),
            n_hypothesis_segments=0,
            n_malformed_lines=len(parsed.malformed_lines),
            hypothesis_empty=True,
        )
    hypothesis = hypothesis_stream_from_grid_or_free_parse(parsed.segments, slice_start=slice_start, slice_end=slice_end)
    arm_score = score_arm(arm, meeting_id, reference, hypothesis, pins=pins)
    return SliceScore(
        arm=arm,
        meeting_id=meeting_id,
        slice_index=slice_index,
        cp_wer=arm_score.cp_wer.error_rate,
        confusion_cost=arm_score.secondary_confusion_cost.confusion_cost,
        compliance=compliance,
        n_reference_segments=len(reference),
        n_hypothesis_segments=len(parsed.segments),
        n_malformed_lines=len(parsed.malformed_lines),
        hypothesis_empty=False,
    )


# ---------------------------------------------------------------------------
# per-cell aggregation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CellScore:
    arm: str
    slices: tuple[SliceScore, ...]

    def __post_init__(self) -> None:
        if not self.slices:
            raise ValueError(f"CellScore for arm {self.arm!r} requires at least one slice score")
        mismatched = [s.arm for s in self.slices if s.arm != self.arm]
        if mismatched:
            raise ValueError(f"CellScore for arm {self.arm!r} received slice score(s) tagged {mismatched}")

    @property
    def n_slices(self) -> int:
        return len(self.slices)

    @property
    def mean_cp_wer(self) -> float:
        return statistics.fmean(s.cp_wer for s in self.slices)

    @property
    def mean_confusion_cost(self) -> float:
        return statistics.fmean(s.confusion_cost for s in self.slices)

    @property
    def mean_compliance(self) -> float:
        return statistics.fmean(s.compliance for s in self.slices)

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "n_slices": self.n_slices,
            "mean_cp_wer": self.mean_cp_wer,
            "mean_confusion_cost": self.mean_confusion_cost,
            "mean_compliance": self.mean_compliance,
            "slices": [s.to_dict() for s in self.slices],
        }


def aggregate_cell(arm: str, slice_scores: Sequence[SliceScore]) -> CellScore:
    return CellScore(arm=arm, slices=tuple(slice_scores))


def aggregate_by_arm(scores: Sequence[SliceScore]) -> dict[str, CellScore]:
    """Group a flat sequence of :class:`SliceScore` by their own ``arm``
    field into one :class:`CellScore` per arm actually present."""

    by_arm: dict[str, list[SliceScore]] = {}
    for s in scores:
        by_arm.setdefault(s.arm, []).append(s)
    return {arm: aggregate_cell(arm, slices) for arm, slices in by_arm.items()}


# ---------------------------------------------------------------------------
# the mechanical winner rule (prereg SS4, verbatim)
# ---------------------------------------------------------------------------

COMPLIANCE_GATE = 0.90
TIE_SET_MARGIN = 0.01
GRAMMAR_BLOCKED = "GRAMMAR-BLOCKED"

#: Float-representation-noise guard (mirrored below for the corrupt-arm
#: thresholds) applied to the tie-set margin so a cell mathematically
#: exactly at the 0.01 boundary is never excluded by IEEE 754 subtraction
#: noise.
_TIE_SET_EPSILON = 1e-9


def _template_index(arm: str) -> int:
    template_id = arm.split("-", 1)[0]
    return TEMPLATES.index(template_id)


def _arrangement_index(arm: str) -> int:
    arrangement_id = arm.split("-", 1)[1]
    return ARRANGEMENTS.index(arrangement_id)


@dataclass(frozen=True)
class WinnerResult:
    status: str  # "WINNER" | GRAMMAR_BLOCKED
    winner_arm: str | None
    tie_set: tuple[str, ...]
    eligible_arms: tuple[str, ...]
    ranked_by_cp_wer: tuple[tuple[str, float], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "winner_arm": self.winner_arm,
            "tie_set": list(self.tie_set),
            "eligible_arms": list(self.eligible_arms),
            "ranked_by_cp_wer": [[arm, cp_wer] for arm, cp_wer in self.ranked_by_cp_wer],
        }


def apply_winner_rule(cells: Mapping[str, CellScore]) -> WinnerResult:
    """The mechanical selection rule, exactly as registered (prereg SS4):

    Winner := lowest mean cpWER among cells with grammar-compliance >= 0.90;
    cells within 0.01 cpWER of the best are a TIE-SET broken by (1) lower
    speaker-confusion, (2) higher grammar-compliance, (3) simpler template
    (lower T index), then simpler arrangement (lower A index). If NO cell
    reaches compliance 0.90: GRAMMAR-BLOCKED.

    Only the 12 grid cells (:data:`~.pprompt.GRID_CELLS`) ever compete --
    ``cells`` may harmlessly also carry X1/X2 (this function filters them
    out), so a caller need not pre-filter its own aggregate dict.
    """

    grid_cells = {arm: cell for arm, cell in cells.items() if arm in GRID_CELLS}
    ranked = tuple(sorted(((arm, cell.mean_cp_wer) for arm, cell in grid_cells.items()), key=lambda pair: pair[1]))
    eligible = {arm: cell for arm, cell in grid_cells.items() if cell.mean_compliance >= COMPLIANCE_GATE}

    if not eligible:
        return WinnerResult(status=GRAMMAR_BLOCKED, winner_arm=None, tie_set=(), eligible_arms=(), ranked_by_cp_wer=ranked)

    best_cp_wer = min(cell.mean_cp_wer for cell in eligible.values())
    tie_set = tuple(
        sorted(arm for arm, cell in eligible.items() if cell.mean_cp_wer - best_cp_wer <= TIE_SET_MARGIN + _TIE_SET_EPSILON)
    )

    def _tiebreak_key(arm: str) -> tuple[float, float, int, int]:
        cell = eligible[arm]
        return (cell.mean_confusion_cost, -cell.mean_compliance, _template_index(arm), _arrangement_index(arm))

    winner = tie_set[0] if len(tie_set) == 1 else min(tie_set, key=_tiebreak_key)

    return WinnerResult(
        status="WINNER",
        winner_arm=winner,
        tie_set=tie_set,
        eligible_arms=tuple(sorted(eligible)),
        ranked_by_cp_wer=ranked,
    )


# ---------------------------------------------------------------------------
# corrupt-context verdicts (prereg SS4, verbatim, each vs the reference cell)
# ---------------------------------------------------------------------------

CONTEXT_SENSITIVE_THRESHOLD = 0.05
CONTEXT_INERT_THRESHOLD = 0.01

#: Float-representation tolerance for the two threshold comparisons below
#: (e.g. ``0.25 - 0.20`` is ``0.04999999999999999`` in IEEE 754 double
#: precision, not exactly ``0.05``) -- without this, a degradation that is
#: mathematically exactly at a registered threshold could fall on the wrong
#: side of it purely from float noise. Small relative to both thresholds, so
#: it never blurs the CONTEXT-INDETERMINATE band itself.
_THRESHOLD_EPSILON = 1e-9


@dataclass(frozen=True)
class CorruptVerdict:
    arm: str
    reference_arm: str
    reference_mean_cp_wer: float
    corrupt_mean_cp_wer: float
    degradation: float  # corrupt_mean_cp_wer - reference_mean_cp_wer
    verdict: str  # "CONTEXT-SENSITIVE" | "CONTEXT-INERT" | "CONTEXT-INDETERMINATE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "reference_arm": self.reference_arm,
            "reference_mean_cp_wer": self.reference_mean_cp_wer,
            "corrupt_mean_cp_wer": self.corrupt_mean_cp_wer,
            "degradation": self.degradation,
            "verdict": self.verdict,
        }


def evaluate_corrupt_arm(corrupt_cell: CellScore, reference_cell: CellScore) -> CorruptVerdict:
    """One corrupt arm's verdict vs ``reference_cell`` (always
    :data:`~.pprompt.REFERENCE_CELL`, T2/A1): degradation >= 0.05 absolute ->
    CONTEXT-SENSITIVE; degradation <= 0.01 -> CONTEXT-INERT (this also
    covers a corrupt arm that scored BETTER than the reference -- a negative
    degradation is, a fortiori, not a sensitivity signal); otherwise
    CONTEXT-INDETERMINATE."""

    degradation = corrupt_cell.mean_cp_wer - reference_cell.mean_cp_wer
    if degradation >= CONTEXT_SENSITIVE_THRESHOLD - _THRESHOLD_EPSILON:
        verdict = "CONTEXT-SENSITIVE"
    elif degradation <= CONTEXT_INERT_THRESHOLD + _THRESHOLD_EPSILON:
        verdict = "CONTEXT-INERT"
    else:
        verdict = "CONTEXT-INDETERMINATE"
    return CorruptVerdict(
        arm=corrupt_cell.arm,
        reference_arm=reference_cell.arm,
        reference_mean_cp_wer=reference_cell.mean_cp_wer,
        corrupt_mean_cp_wer=corrupt_cell.mean_cp_wer,
        degradation=degradation,
        verdict=verdict,
    )


def evaluate_all_corrupt_arms(cells: Mapping[str, CellScore]) -> dict[str, CorruptVerdict]:
    """Both X1 and X2's verdicts vs the reference cell, keyed by arm id.
    Raises :class:`KeyError` if either corrupt arm or the reference cell is
    absent from ``cells`` -- a partial corrupt-verdict read is a defect, not
    a silently incomplete report."""

    reference_cell = cells[REFERENCE_CELL]
    return {arm: evaluate_corrupt_arm(cells[arm], reference_cell) for arm in (ARM_X1, ARM_X2)}


# ---------------------------------------------------------------------------
# one-shot idempotence guard
# ---------------------------------------------------------------------------


class PromptSweepOutputExistsError(RuntimeError):
    """Raised by :func:`assert_one_shot_output_dir` when the read's output
    directory already carries a prior read's output -- the "one-shot read"
    discipline (prereg SS6): a second read into the same directory is
    refused rather than silently overwriting a committed verdict, unless the
    caller explicitly opts in via ``force=True``."""


def assert_one_shot_output_dir(out_dir: Path | str, *, filenames: Sequence[str] = ("verdict.json",), force: bool = False) -> None:
    """Refuse (raise :class:`PromptSweepOutputExistsError`) if ``out_dir``
    already contains any of ``filenames``, unless ``force`` is set. A
    missing/empty ``out_dir`` always passes."""

    if force:
        return
    resolved = Path(out_dir)
    existing = [name for name in filenames if (resolved / name).exists()]
    if existing:
        raise PromptSweepOutputExistsError(
            f"{resolved} already carries prior read output {existing} -- the P-PROMPT read is "
            "one-shot (prereg SS6); pass force=True (--force) only if you intend to replace a "
            "committed verdict"
        )
