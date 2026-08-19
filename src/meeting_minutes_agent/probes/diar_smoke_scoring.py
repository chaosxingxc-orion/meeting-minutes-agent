"""DIAR-SMOKE offline scoring path: a flight's RTTM outputs (already
collected by ``scripts/launch_diar_smoke.py``) + the NXT oracle turn table
(SCORING-SIDE reference ONLY -- prereg SS3: "no annotation of any kind
enters tool input") -> every registered metric (prereg SS4) -> the five
mechanical verdicts (prereg SS5), evaluated with numeric clause margins.

Read-only and OFFLINE, per mission scope: every function here scores
already-collected RTTM/turn tables; nothing performs a tool subprocess call
or a model contact. DER/JER come from
:mod:`meeting_minutes_agent.metrics.diarization_error` (native, stdlib +
numpy) -- this module never reimplements that math, it only adds what the
smoke needs on top: the packing-change metric (bound directly to the real
:func:`~meeting_minutes_agent.chunking.slicer.build_turn_aware_slice_plan`),
turn-boundary displacement, speaker-count accuracy, pooling, and the
mechanical verdict evaluator.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..chunking.leakage import BoundaryProvenance
from ..chunking.slicer import TurnSpan, build_turn_aware_slice_plan
from ..metrics.diarization_error import DerBreakdown, JerResult, compute_der, compute_jer, pool_der_breakdowns

__all__ = [
    "CONVENTION_COLLAR_NO_OVERLAP",
    "CONVENTION_NO_COLLAR_WITH_OVERLAP",
    "CONVENTIONS",
    "MeetingMetrics",
    "score_meeting",
    "boundary_displacements",
    "displacement_summary",
    "PackingChangeResult",
    "packing_change_for_meeting",
    "pool_meeting_metrics_by_convention",
    "PARITY_ABS_THRESHOLD_DER",
    "TOOL_LOCKED_MAX_DER",
    "CAVEAT_MAX_DER",
    "IN_DOMAIN_CAVEAT",
    "STATUS_TOOL_LOCKED_B",
    "STATUS_TOOL_LOCKED_A",
    "STATUS_TOOL_USABLE_WITH_CAVEAT",
    "STATUS_FALLBACK_NEEDED",
    "ClauseEvaluation",
    "DiarSmokeVerdict",
    "evaluate_diar_smoke_verdict",
    "DiarSmokeReadOutputExistsError",
    "assert_one_shot_output_dir",
]

#: The two registered scoring conventions (prereg SS4).
CONVENTION_COLLAR_NO_OVERLAP = "collar_0.25_no_overlap"
CONVENTION_NO_COLLAR_WITH_OVERLAP = "no_collar_with_overlap"
CONVENTIONS: tuple[tuple[str, float, bool], ...] = (
    (CONVENTION_COLLAR_NO_OVERLAP, 0.25, True),
    (CONVENTION_NO_COLLAR_WITH_OVERLAP, 0.0, False),
)


# ---------------------------------------------------------------------------
# per-meeting metric bundle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MeetingMetrics:
    meeting_id: str
    n_reference_speakers: int
    n_hypothesis_speakers: int
    speaker_count_correct: bool
    der_by_convention: Mapping[str, DerBreakdown]
    jer_by_convention: Mapping[str, JerResult]
    boundary_displacement_seconds: tuple[float, ...]
    packing: "PackingChangeResult"

    def to_dict(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "n_reference_speakers": self.n_reference_speakers,
            "n_hypothesis_speakers": self.n_hypothesis_speakers,
            "speaker_count_correct": self.speaker_count_correct,
            "der_by_convention": {k: v.to_dict() for k, v in self.der_by_convention.items()},
            "jer_by_convention": {k: v.to_dict() for k, v in self.jer_by_convention.items()},
            "boundary_displacement_seconds": list(self.boundary_displacement_seconds),
            "boundary_displacement_summary": displacement_summary(self.boundary_displacement_seconds),
            "packing": self.packing.to_dict(),
        }


def score_meeting(
    meeting_id: str,
    reference_turns: Sequence[TurnSpan],
    hypothesis_turns: Sequence[TurnSpan],
    *,
    total_duration_s: float | None = None,
    fallback_pause_transitions: Sequence[float] = (),
) -> MeetingMetrics:
    """Every registered per-meeting metric (prereg SS4) for one meeting's
    ``(oracle turns, tool turns)`` pair: DER + JER under both conventions,
    speaker-count comparison, turn-boundary displacement, and the
    packing-change diagnostic. Pure over already-in-memory turn tables --
    the caller resolves the oracle turns (NXT, scoring-side only) and the
    tool turns (RTTM-parsed) before calling this."""

    der_by_convention: dict[str, DerBreakdown] = {}
    jer_by_convention: dict[str, JerResult] = {}
    for name, collar, skip_overlap in CONVENTIONS:
        der_by_convention[name] = compute_der(reference_turns, hypothesis_turns, collar=collar, skip_overlap=skip_overlap)
        jer_by_convention[name] = compute_jer(reference_turns, hypothesis_turns, collar=collar, skip_overlap=skip_overlap)

    n_ref_speakers = len({t.speaker for t in reference_turns})
    n_hyp_speakers = len({t.speaker for t in hypothesis_turns})

    displacement = boundary_displacements(reference_turns, hypothesis_turns)
    packing = packing_change_for_meeting(
        meeting_id,
        reference_turns,
        hypothesis_turns,
        total_duration_s=total_duration_s,
        fallback_pause_transitions=fallback_pause_transitions,
    )

    return MeetingMetrics(
        meeting_id=meeting_id,
        n_reference_speakers=n_ref_speakers,
        n_hypothesis_speakers=n_hyp_speakers,
        speaker_count_correct=n_ref_speakers == n_hyp_speakers,
        der_by_convention=der_by_convention,
        jer_by_convention=jer_by_convention,
        boundary_displacement_seconds=displacement,
        packing=packing,
    )


# ---------------------------------------------------------------------------
# turn-boundary displacement
# ---------------------------------------------------------------------------


def _boundary_times(turns: Sequence[TurnSpan]) -> tuple[float, ...]:
    points: set[float] = set()
    for t in turns:
        points.add(t.start)
        points.add(t.end)
    return tuple(sorted(points))


def boundary_displacements(
    reference_turns: Sequence[TurnSpan], hypothesis_turns: Sequence[TurnSpan]
) -> tuple[float, ...]:
    """For every reference (oracle) turn boundary -- start or end time --
    the absolute distance to the NEAREST hypothesis (tool) turn boundary:
    the "boundary-displacement distribution vs oracle turns" (prereg SS4).
    An empty hypothesis turn table yields an empty distribution -- nothing
    to measure displacement against -- never a fabricated infinite value."""

    ref_points = _boundary_times(reference_turns)
    hyp_points = _boundary_times(hypothesis_turns)
    if not hyp_points:
        return ()
    return tuple(min(abs(p - h) for h in hyp_points) for p in ref_points)


def displacement_summary(displacements: Sequence[float]) -> dict[str, Any]:
    if not displacements:
        return {"n": 0, "mean": None, "median": None, "max": None}
    return {
        "n": len(displacements),
        "mean": statistics.fmean(displacements),
        "median": statistics.median(displacements),
        "max": max(displacements),
    }


# ---------------------------------------------------------------------------
# packing-change metric -- bound directly to the real slicer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PackingChangeResult:
    meeting_id: str
    n_slices_oracle: int
    n_slices_tool: int
    n_compared: int
    n_changed: int
    changed_slice_indices: tuple[int, ...]

    @property
    def fraction_changed(self) -> float:
        return self.n_changed / self.n_compared if self.n_compared else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "n_slices_oracle": self.n_slices_oracle,
            "n_slices_tool": self.n_slices_tool,
            "n_compared": self.n_compared,
            "n_changed": self.n_changed,
            "fraction_changed": self.fraction_changed,
            "changed_slice_indices": list(self.changed_slice_indices),
        }


def packing_change_for_meeting(
    meeting_id: str,
    oracle_turns: Sequence[TurnSpan],
    tool_turns: Sequence[TurnSpan],
    *,
    total_duration_s: float | None = None,
    fallback_pause_transitions: Sequence[float] = (),
) -> PackingChangeResult:
    """Build BOTH 90 s turn-aware slice plans through the SAME real slicer
    entry point (:func:`~meeting_minutes_agent.chunking.slicer.
    build_turn_aware_slice_plan` -- no reimplementation, no approximation):
    one over the oracle turns (``BoundaryProvenance.ORACLE_TURN``, admitted
    via ``allow_oracle_turns=True`` as the declared ceiling-arm choice this
    scoring-side comparison is), one over the tool turns
    (``BoundaryProvenance.TOOL_DIAR``, always admissible). Reports the
    fraction of slices whose positional ``(start, end)`` bound differs
    between the two plans -- "the fraction of 90 s transport slices whose
    packing CHANGES when oracle turns are replaced by tool turns" (prereg
    SS4) -- plus the raw slice counts and which indices changed."""

    oracle_plan = build_turn_aware_slice_plan(
        meeting_id,
        oracle_turns,
        turn_provenance=BoundaryProvenance.ORACLE_TURN,
        allow_oracle_turns=True,
        total_duration_s=total_duration_s,
        fallback_pause_transitions=fallback_pause_transitions,
    )
    tool_plan = build_turn_aware_slice_plan(
        meeting_id,
        tool_turns,
        turn_provenance=BoundaryProvenance.TOOL_DIAR,
        total_duration_s=total_duration_s,
        fallback_pause_transitions=fallback_pause_transitions,
    )

    oracle_bounds = [(round(s.start, 6), round(s.end, 6)) for s in oracle_plan.slices]
    tool_bounds = [(round(s.start, 6), round(s.end, 6)) for s in tool_plan.slices]
    n = max(len(oracle_bounds), len(tool_bounds))
    changed = [
        i
        for i in range(n)
        if (oracle_bounds[i] if i < len(oracle_bounds) else None) != (tool_bounds[i] if i < len(tool_bounds) else None)
    ]
    return PackingChangeResult(
        meeting_id=meeting_id,
        n_slices_oracle=len(oracle_bounds),
        n_slices_tool=len(tool_bounds),
        n_compared=n,
        n_changed=len(changed),
        changed_slice_indices=tuple(changed),
    )


# ---------------------------------------------------------------------------
# pooling
# ---------------------------------------------------------------------------


def pool_meeting_metrics_by_convention(meeting_metrics: Sequence[MeetingMetrics], convention: str) -> DerBreakdown:
    """Duration-weighted pooled DER (:func:`~meeting_minutes_agent.metrics.
    diarization_error.pool_der_breakdowns`) across every meeting's
    ``der_by_convention[convention]`` breakdown."""

    return pool_der_breakdowns([m.der_by_convention[convention] for m in meeting_metrics])


# ---------------------------------------------------------------------------
# the five mechanical verdicts (prereg SS5)
# ---------------------------------------------------------------------------

PARITY_ABS_THRESHOLD_DER = 2.0
TOOL_LOCKED_MAX_DER = 22.0
CAVEAT_MAX_DER = 30.0

IN_DOMAIN_CAVEAT = (
    "AMI appears in the NVIDIA models' training data (partition unstated by the card); this "
    "smoke's DER is therefore an in-domain number and is cited as such -- it licenses tool USE, "
    "never a generalization claim. Carried in ALL outcomes (prereg SS5)."
)

STATUS_TOOL_LOCKED_B = "TOOL-LOCKED(B)"
STATUS_TOOL_LOCKED_A = "TOOL-LOCKED(A)"
STATUS_TOOL_USABLE_WITH_CAVEAT = "TOOL-USABLE-WITH-CAVEAT"
STATUS_FALLBACK_NEEDED = "FALLBACK-NEEDED"


@dataclass(frozen=True)
class ClauseEvaluation:
    name: str
    fires: bool
    margin: float | None
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "fires": self.fires, "margin": self.margin, "detail": self.detail}


@dataclass(frozen=True)
class DiarSmokeVerdict:
    status: str
    der_a_no_collar_overlap: float | None
    der_b_no_collar_overlap: float | None
    a_load_failed: bool
    b_load_failed: bool
    best_arm: str | None
    best_arm_der: float | None
    clauses: Mapping[str, ClauseEvaluation]
    in_domain_caveat: str = IN_DOMAIN_CAVEAT

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "der_a_no_collar_overlap": self.der_a_no_collar_overlap,
            "der_b_no_collar_overlap": self.der_b_no_collar_overlap,
            "a_load_failed": self.a_load_failed,
            "b_load_failed": self.b_load_failed,
            "best_arm": self.best_arm,
            "best_arm_der": self.best_arm_der,
            "clauses": {k: v.to_dict() for k, v in self.clauses.items()},
            "in_domain_caveat": self.in_domain_caveat,
        }


def evaluate_diar_smoke_verdict(
    *,
    der_a: float | None,
    der_b: float | None,
    a_load_failed: bool = False,
    b_load_failed: bool = False,
) -> DiarSmokeVerdict:
    """Mechanically evaluate the five registered clauses (prereg SS5) in
    priority order, each carrying a numeric margin to its own threshold
    regardless of whether it ends up deciding ``status`` -- so a read stays
    auditable even far from a threshold. ``der_a``/``der_b`` are expected to
    be the POOLED DER under the no-collar-with-overlap convention
    (:data:`CONVENTION_NO_COLLAR_WITH_OVERLAP`); the parity clause and both
    TOOL-LOCKED clauses are explicitly registered against that convention
    (prereg SS5).

    Spec-ambiguity note (recorded, mirroring ``scripts/
    build_pattr_manifest.py``'s own such notes): SS5 item 3 reads "parity
    fails but DER(A) <= 22.0". This function fires TOOL-LOCKED(A) whenever
    TOOL-LOCKED(B) does NOT fire -- whether because parity failed, or
    because DER(B) itself exceeded 22.0 while parity still held -- AND
    DER(A) qualifies. That is the natural total ordering of the same
    four-way priority chain (2 -> 3 -> 4 -> 5) and the only reading under
    which the four clauses jointly cover every ``(der_a, der_b,
    load-failure)`` combination without a gap."""

    a_ok = (not a_load_failed) and der_a is not None
    b_ok = (not b_load_failed) and der_b is not None

    if a_ok and b_ok:
        parity_gap = abs(der_b - der_a)
        parity_passed = parity_gap <= PARITY_ABS_THRESHOLD_DER
        parity_margin: float | None = PARITY_ABS_THRESHOLD_DER - parity_gap
        parity_detail = f"|DER(B)={der_b:.2f} - DER(A)={der_a:.2f}| = {parity_gap:.2f} (threshold {PARITY_ABS_THRESHOLD_DER})"
    else:
        parity_passed = False
        parity_margin = None
        parity_detail = "parity not evaluable: at least one arm failed to load / produce a DER"

    tool_locked_b_fires = bool(parity_passed) and b_ok and der_b <= TOOL_LOCKED_MAX_DER
    tool_locked_b_margin = (TOOL_LOCKED_MAX_DER - der_b) if b_ok else None

    tool_locked_a_fires = (not tool_locked_b_fires) and a_ok and der_a <= TOOL_LOCKED_MAX_DER
    tool_locked_a_margin = (TOOL_LOCKED_MAX_DER - der_a) if a_ok else None

    candidates = [(name, value) for name, value, ok in (("A", der_a, a_ok), ("B", der_b, b_ok)) if ok]
    both_failed = not candidates
    best_arm, best_der = min(candidates, key=lambda kv: kv[1]) if candidates else (None, None)

    caveat_fires = (
        not tool_locked_b_fires
        and not tool_locked_a_fires
        and best_der is not None
        and TOOL_LOCKED_MAX_DER < best_der <= CAVEAT_MAX_DER
    )
    caveat_margin = (CAVEAT_MAX_DER - best_der) if best_der is not None else None

    fallback_fires = not (tool_locked_b_fires or tool_locked_a_fires or caveat_fires)
    fallback_margin = (best_der - CAVEAT_MAX_DER) if best_der is not None else None

    if tool_locked_b_fires:
        status = STATUS_TOOL_LOCKED_B
    elif tool_locked_a_fires:
        status = STATUS_TOOL_LOCKED_A
    elif caveat_fires:
        status = STATUS_TOOL_USABLE_WITH_CAVEAT
    else:
        status = STATUS_FALLBACK_NEEDED

    clauses = {
        "parity": ClauseEvaluation("parity", bool(parity_passed), parity_margin, parity_detail),
        "tool_locked_b": ClauseEvaluation(
            "tool_locked_b", tool_locked_b_fires, tool_locked_b_margin,
            f"parity AND DER(B) <= {TOOL_LOCKED_MAX_DER}",
        ),
        "tool_locked_a": ClauseEvaluation(
            "tool_locked_a", tool_locked_a_fires, tool_locked_a_margin,
            f"DER(A) <= {TOOL_LOCKED_MAX_DER} (when TOOL-LOCKED(B) did not fire)",
        ),
        "tool_usable_with_caveat": ClauseEvaluation(
            "tool_usable_with_caveat", caveat_fires, caveat_margin,
            f"best-arm DER in ({TOOL_LOCKED_MAX_DER}, {CAVEAT_MAX_DER}]",
        ),
        "fallback_needed": ClauseEvaluation(
            "fallback_needed", fallback_fires, fallback_margin,
            f"best-arm DER > {CAVEAT_MAX_DER} or both arms failed to load (both_failed={both_failed})",
        ),
    }

    return DiarSmokeVerdict(
        status=status,
        der_a_no_collar_overlap=der_a,
        der_b_no_collar_overlap=der_b,
        a_load_failed=a_load_failed,
        b_load_failed=b_load_failed,
        best_arm=best_arm,
        best_arm_der=best_der,
        clauses=clauses,
    )


# ---------------------------------------------------------------------------
# one-shot read output-dir guard (mirrors scripts/pprompt_read.py's own)
# ---------------------------------------------------------------------------


class DiarSmokeReadOutputExistsError(RuntimeError):
    """Raised by :func:`assert_one_shot_output_dir` when the read's output
    directory already carries a prior read's output -- one-shot read
    discipline (prereg SS7's "One-shot read via a pinned scoring CLI"),
    mirroring ``scripts/pprompt_read.py``'s own guard."""


def assert_one_shot_output_dir(
    out_dir: Path | str, *, filenames: Sequence[str] = ("verdict.json",), force: bool = False
) -> None:
    """Refuse (raise :class:`DiarSmokeReadOutputExistsError`) if ``out_dir``
    already contains any of ``filenames``, unless ``force`` is set. A
    missing/empty ``out_dir`` always passes."""

    if force:
        return
    resolved = Path(out_dir)
    existing = [name for name in filenames if (resolved / name).exists()]
    if existing:
        raise DiarSmokeReadOutputExistsError(
            f"{resolved} already carries prior read output {existing} -- the DIAR-SMOKE read is "
            "one-shot; pass force=True (--force) only if you intend to replace a committed verdict"
        )
