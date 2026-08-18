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

ORC feasibility guard (forced deviation, 2026-08-18, decided BEFORE any
error rate was read -- the P-PROMPT analogue of the P-ATTR read's own
recorded meeteval refusals, ``docs/readiness/2026-08-18-pattr-verdict.md``
SS4): meeteval 0.4.3's ORC-WER dynamic program allocates memory roughly
proportional to ``n_reference_utterances x prod_over_hypothesis_streams
(stream_word_count + 1)``. Two flown replies (the T1-A2/T1-A3 twins on
IS1008d slice0005, which parse to 7 hypothesis speaker streams) push that
product to ~7.9e9 -- an estimated ~190 GB, unconditionally infeasible on
the 54 GB read host: the first two read attempts were OOM-killed by the
kernel at ~56 GB before writing anything. A subprocess feasibility probe
(rlimit-capped, flags only, no error rate surfaced) confirmed cpWER is
cheap on every flown reply (Hungarian assignment) while ORC-WER is the
sole explosion. :func:`score_slice` therefore (a) refuses to ATTEMPT the
ORC term when :func:`orc_dp_bound` exceeds :data:`ORC_DP_BOUND_CAP`, and
(b) records a ``MemoryError`` raised inside an attempted ORC term the same
way; in both cases the slice keeps its real cpWER (computed by the same
committed :func:`~meeting_minutes_agent.metrics.wer.compute_cp_wer` that
:func:`~.pattr_scoring.score_arm` itself calls) and carries
``confusion_cost=None`` plus a per-slice ``orc_refusal`` reason -- recorded
as data, never silently dropped (:class:`CellScore` means skip refused
slices and expose ``n_confusion_refused``). The cap (2.0e9) sits in the
observed 8x gap between the largest empirically feasible structure
(~9.5e8) and the infeasible twins (~7.9e9). The winner rule's PRIMARY
criterion (mean cpWER) and the compliance gate are unaffected: cpWER is
complete for all 336 replies; only the tie-break's confusion-cost
ingredient averages over the slices whose ORC term was computable.
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
    "ORC_DP_BOUND_CAP",
    "orc_dp_bound",
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
# ORC feasibility guard (module docstring: the recorded forced deviation)
# ---------------------------------------------------------------------------

#: Refuse to ATTEMPT the ORC-WER term when :func:`orc_dp_bound` exceeds this.
#: Placement rationale in the module docstring: the observed feasible maximum
#: on the flown data is ~9.5e8 and the observed-infeasible minimum ~7.9e9
#: (est. ~190 GB); 2.0e9 sits inside that gap with >2x margin on both sides.
ORC_DP_BOUND_CAP = 2.0e9


def orc_dp_bound(n_reference_utterances: int, parsed_segments) -> float:
    """Deterministic proxy for meeteval 0.4.3's ORC-WER dynamic-program
    memory: ``n_reference_utterances x prod over distinct-speaker hypothesis
    streams of (stream word count + 1)`` (observed ~24 bytes per unit on
    this host's meeteval build). Computed from the PARSED reply structure
    alone -- no metric math, no gold text."""

    stream_words: dict[str, int] = {}
    for seg in parsed_segments:
        stream_words[seg.speaker] = stream_words.get(seg.speaker, 0) + len(seg.text.split())
    prod = 1.0
    for words in stream_words.values():
        prod *= words + 1
    return max(n_reference_utterances, 1) * prod


# ---------------------------------------------------------------------------
# per-slice scoring
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SliceScore:
    arm: str
    meeting_id: str
    slice_index: int
    cp_wer: float
    confusion_cost: float | None
    compliance: float
    n_reference_segments: int
    n_hypothesis_segments: int
    n_malformed_lines: int
    hypothesis_empty: bool
    #: Non-``None`` iff the ORC-WER term was refused (state-space cap or a
    #: caught ``MemoryError``); such a slice keeps its real cpWER and carries
    #: ``confusion_cost=None`` -- recorded, never silently dropped.
    orc_refusal: str | None = None

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
            "orc_refusal": self.orc_refusal,
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
    orc_dp_bound_cap: float = ORC_DP_BOUND_CAP,
) -> SliceScore:
    """Score one arm's one slice reply against its already-extracted gold
    reference stream (:func:`~.pattr_scoring.extract_gold_streams_for_range`
    is the caller's own job -- this function takes the reference stream
    directly, never a ``ResolvedMeeting``, keeping this module corpus-
    access-free). ``orc_dp_bound_cap`` is an injection seam for tests; the
    production read always runs with :data:`ORC_DP_BOUND_CAP`."""

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

    def _orc_refused(reason: str) -> SliceScore:
        # The refusal path keeps the slice's REAL cpWER, produced by the very
        # same committed function score_arm itself calls -- never a second
        # implementation of the math (module docstring).
        from ..metrics.wer import compute_cp_wer

        cp = compute_cp_wer(reference, tuple(h.as_per_speaker_segment() for h in hypothesis), pins=pins)
        return SliceScore(
            arm=arm,
            meeting_id=meeting_id,
            slice_index=slice_index,
            cp_wer=cp.error_rate,
            confusion_cost=None,
            compliance=compliance,
            n_reference_segments=len(reference),
            n_hypothesis_segments=len(parsed.segments),
            n_malformed_lines=len(parsed.malformed_lines),
            hypothesis_empty=False,
            orc_refusal=reason,
        )

    bound = orc_dp_bound(len(reference), parsed.segments)
    if bound > orc_dp_bound_cap:
        return _orc_refused(
            f"ORC-WER not attempted: orc_dp_bound {bound:.3e} exceeds cap {orc_dp_bound_cap:.1e} "
            "(state-space infeasible on the read host; module docstring)"
        )
    try:
        arm_score = score_arm(arm, meeting_id, reference, hypothesis, pins=pins)
    except MemoryError:
        return _orc_refused(
            f"ORC-WER MemoryError at orc_dp_bound {bound:.3e} (host memory pressure at read time; "
            "cpWER retained, confusion term refused)"
        )
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
    def n_confusion_refused(self) -> int:
        """Slices whose ORC term was refused (``confusion_cost is None``,
        module docstring's forced deviation) -- recorded, never hidden."""

        return sum(1 for s in self.slices if s.confusion_cost is None)

    @property
    def mean_confusion_cost(self) -> float:
        """Mean over the slices whose confusion cost was computable. A cell
        with NO computable slice raises rather than inventing a number."""

        values = [s.confusion_cost for s in self.slices if s.confusion_cost is not None]
        if not values:
            raise ValueError(
                f"cell {self.arm!r} has no slice with a computable confusion cost "
                f"({self.n_confusion_refused} ORC-refused) -- mean_confusion_cost is undefined"
            )
        return statistics.fmean(values)

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
            "n_confusion_refused": self.n_confusion_refused,
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
