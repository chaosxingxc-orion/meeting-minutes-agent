"""Native DER/JER diarization scorer -- stdlib + numpy only.

meeteval (this repository's WER-family engine, :mod:`.wer`) does not
provide a diarization-error-rate implementation, and DIAR-SMOKE's mission
brief forbids adding a new dependency for one. This module reimplements the
standard NIST/pyannote-family algorithm directly:

1. **Optimal speaker mapping** (:func:`optimal_speaker_mapping`): a
   one-to-one reference-speaker -> hypothesis-speaker assignment maximizing
   total overlap duration, found by brute-force search over
   ``itertools.permutations`` -- always exact (never a greedy
   approximation), and cheap at the speaker counts this program's corpora
   ever carry (AMI scenario meetings have exactly 4 speakers; the pinned
   Sortformer checkpoints cap at 4; see :data:`MAX_BRUTE_FORCE_SPEAKERS` for
   the fail-closed size guard).
2. **Event-driven interval decomposition** (:func:`scored_intervals`): the
   reference and hypothesis segment boundaries (plus, when a collar is
   requested, every ``[boundary - collar, boundary + collar]`` edge) are
   merged into one sorted, deduplicated timeline. Within each elementary
   interval the active reference/hypothesis speaker sets are constant by
   construction, so missed/false-alarm/confusion time can be integrated
   exactly -- no frame-quantization error, and no need for the region-
   trimming machinery a discretized approach would carry separately.
3. **Two registered scoring conventions**
   (``docs/readiness/2026-08-18-diar-smoke-preregistration.md`` SS4): a
   0.25 s collar around every reference-segment boundary with overlapped
   reference regions skipped entirely (``collar=0.25, skip_overlap=True``),
   and no collar with overlap scored (``collar=0.0, skip_overlap=False`` --
   the published pyannote-3.1 AMI anchor's own convention). Both
   :func:`compute_der` and :func:`compute_jer` take ``collar``/
   ``skip_overlap`` directly, so a caller reproduces either convention (or
   any other) without a second implementation.

DER formula (standard NIST accounting, reproduced here for the reader):
within an elementary interval of duration ``dt`` with ``N_ref`` active
reference speakers, ``N_hyp`` active hypothesis speakers, and ``N_correct``
of the reference speakers whose MAPPED hypothesis speaker is also active,

* ``confusion += min(N_ref - N_correct, N_hyp - N_correct) * dt``
* ``missed   += max(0, (N_ref - N_correct) - (N_hyp - N_correct)) * dt``
* ``false_alarm += max(0, (N_hyp - N_correct) - (N_ref - N_correct)) * dt``

and ``DER = (missed + false_alarm + confusion) / total_reference_seconds``,
where ``total_reference_seconds`` is the integral of ``N_ref(t)`` over the
scored region (reference speaker-seconds, overlap counted multiply).

JER (Jaccard error rate, DIHARD-family definition) uses the SAME optimal
mapping: for each reference speaker with a mapped hypothesis speaker,
``JER_i = 1 - intersection_i / union_i`` (a Jaccard distance between that
pair's active-time sets, restricted to the scored region); a reference
speaker with no mapped hypothesis speaker scores ``JER_i = 1.0``. The
overall JER is the unweighted mean over reference speakers -- unlike DER,
every speaker counts equally regardless of how much they spoke.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

import numpy as np

__all__ = [
    "DiarizationScoringError",
    "SpeakerSegment",
    "MAX_BRUTE_FORCE_SPEAKERS",
    "optimal_speaker_mapping",
    "scored_intervals",
    "DerBreakdown",
    "compute_der",
    "pool_der_breakdowns",
    "JerResult",
    "compute_jer",
    "speaker_set",
]


class DiarizationScoringError(ValueError):
    """A DER/JER input was invalid (a non-finite or inverted segment span,
    an oversized brute-force mapping search, incompatible pooling
    conventions, ...)."""


@runtime_checkable
class SpeakerSegment(Protocol):
    """Structural type this module accepts: anything exposing ``speaker``/
    ``start``/``end`` -- :class:`meeting_minutes_agent.chunking.slicer.TurnSpan`
    (RTTM-parsed tool turns, NXT oracle turns) satisfies this by construction,
    with no adapter/conversion step needed. This module never imports
    :mod:`meeting_minutes_agent.chunking` itself (module docstring: stdlib +
    numpy only, no cross-package coupling for a pure metric)."""

    speaker: str
    start: float
    end: float


#: Fail-closed guard on :func:`optimal_speaker_mapping`'s brute-force search:
#: ``size!`` permutations are checked, so this caps runtime at ``8! =
#: 40,320`` in the worst case. AMI scenario meetings carry exactly 4
#: speakers and the pinned Sortformer checkpoints cap at 4 (selection
#: ticket SS2.3); a real tool output exceeding this on the registered
#: 6-meeting smoke would itself be diagnostic (a badly over-segmenting
#: diarizer), not a case this scorer should silently spend minutes on.
MAX_BRUTE_FORCE_SPEAKERS = 8


@dataclass(frozen=True)
class _Seg:
    speaker: str
    start: float
    end: float


def _validate_segments(segments: Sequence[SpeakerSegment], *, label: str) -> tuple[_Seg, ...]:
    out: list[_Seg] = []
    for i, s in enumerate(segments):
        start = float(s.start)
        end = float(s.end)
        if not math.isfinite(start) or not math.isfinite(end) or end <= start:
            raise DiarizationScoringError(
                f"{label}[{i}] (speaker={getattr(s, 'speaker', None)!r}) has an invalid span: "
                f"start={start}, end={end} (require finite, end > start)"
            )
        out.append(_Seg(speaker=str(s.speaker), start=start, end=end))
    return tuple(out)


def speaker_set(segments: Sequence[SpeakerSegment]) -> tuple[str, ...]:
    """The distinct speaker labels in ``segments``, sorted."""

    return tuple(sorted({str(s.speaker) for s in segments}))


# ---------------------------------------------------------------------------
# optimal speaker mapping
# ---------------------------------------------------------------------------


def _overlap_duration_matrix(
    reference: Sequence[_Seg], hypothesis: Sequence[_Seg], ref_speakers: Sequence[str], hyp_speakers: Sequence[str]
) -> "np.ndarray":
    matrix = np.zeros((len(ref_speakers), len(hyp_speakers)), dtype=np.float64)
    ref_index = {s: i for i, s in enumerate(ref_speakers)}
    hyp_index = {s: j for j, s in enumerate(hyp_speakers)}
    for r in reference:
        i = ref_index[r.speaker]
        for h in hypothesis:
            overlap = min(r.end, h.end) - max(r.start, h.start)
            if overlap > 0:
                matrix[i, hyp_index[h.speaker]] += overlap
    return matrix


def optimal_speaker_mapping(
    reference: Sequence[SpeakerSegment], hypothesis: Sequence[SpeakerSegment]
) -> dict[str, str]:
    """The one-to-one reference-speaker -> hypothesis-speaker mapping
    maximizing total overlap duration (module docstring). Reference
    speakers with no positive-overlap counterpart are simply absent from
    the returned mapping -- never forced onto an unrelated label. Computed
    on the FULL (un-collared, overlap-included) segment sets regardless of
    which scoring convention a caller later applies -- the correspondence
    between speakers is a property of the whole recording, not of a
    collar/overlap-exclusion choice (standard NIST/dscore practice: the
    mapping is fixed once per file, then reused by every convention)."""

    ref = _validate_segments(reference, label="reference")
    hyp = _validate_segments(hypothesis, label="hypothesis")
    ref_speakers = speaker_set(ref)
    hyp_speakers = speaker_set(hyp)
    if not ref_speakers or not hyp_speakers:
        return {}

    size = max(len(ref_speakers), len(hyp_speakers))
    if size > MAX_BRUTE_FORCE_SPEAKERS:
        raise DiarizationScoringError(
            f"optimal_speaker_mapping: {len(ref_speakers)} reference / {len(hyp_speakers)} hypothesis "
            f"speaker(s) exceeds the brute-force search guard MAX_BRUTE_FORCE_SPEAKERS="
            f"{MAX_BRUTE_FORCE_SPEAKERS} (module docstring)"
        )

    matrix = _overlap_duration_matrix(ref, hyp, ref_speakers, hyp_speakers)
    n, m = matrix.shape
    padded = np.zeros((size, size), dtype=np.float64)
    padded[:n, :m] = matrix

    best_perm: tuple[int, ...] | None = None
    best_score = -1.0
    for perm in itertools.permutations(range(size)):
        score = sum(padded[i, perm[i]] for i in range(size))
        if score > best_score:
            best_score = score
            best_perm = perm
    assert best_perm is not None  # size >= 1 here (both speaker sets non-empty)

    mapping: dict[str, str] = {}
    for i in range(n):
        j = best_perm[i]
        if j < m and matrix[i, j] > 0:
            mapping[ref_speakers[i]] = hyp_speakers[j]
    return mapping


# ---------------------------------------------------------------------------
# event-driven interval decomposition (shared by DER and JER)
# ---------------------------------------------------------------------------

_ROUND_NDIGITS = 9


def _active_speakers(segments: Sequence[_Seg], t0: float, t1: float, *, eps: float) -> frozenset[str]:
    return frozenset(s.speaker for s in segments if s.start <= t0 + eps and s.end >= t1 - eps)


def scored_intervals(
    reference: Sequence[SpeakerSegment],
    hypothesis: Sequence[SpeakerSegment],
    *,
    collar: float = 0.0,
    skip_overlap: bool = False,
    eps: float = 1e-9,
) -> tuple[tuple[float, float, frozenset[str], frozenset[str]], ...]:
    """The elementary, non-excluded ``(t0, t1, active_ref_speakers,
    active_hyp_speakers)`` intervals a scoring convention keeps (module
    docstring). Boundary points are the union of every reference/hypothesis
    segment start+end, plus (when ``collar > 0``) every
    ``reference_boundary +/- collar`` edge, so exclusion is exact rather
    than approximated on a coarse grid. An interval is dropped when
    ``skip_overlap`` and more than one reference speaker is active, or when
    its midpoint falls within ``collar`` of any reference-segment boundary."""

    if collar < 0:
        raise DiarizationScoringError(f"collar must be non-negative, got {collar!r}")

    ref = _validate_segments(reference, label="reference")
    hyp = _validate_segments(hypothesis, label="hypothesis")

    ref_boundaries = sorted({round(s.start, _ROUND_NDIGITS) for s in ref} | {round(s.end, _ROUND_NDIGITS) for s in ref})

    points: set[float] = set(ref_boundaries)
    for s in hyp:
        points.add(round(s.start, _ROUND_NDIGITS))
        points.add(round(s.end, _ROUND_NDIGITS))
    if collar > 0:
        for b in ref_boundaries:
            points.add(round(b - collar, _ROUND_NDIGITS))
            points.add(round(b + collar, _ROUND_NDIGITS))

    ordered = sorted(points)
    out: list[tuple[float, float, frozenset[str], frozenset[str]]] = []
    for t0, t1 in zip(ordered, ordered[1:]):
        if t1 - t0 <= eps:
            continue
        mid = (t0 + t1) / 2.0
        active_ref = _active_speakers(ref, t0, t1, eps=eps)
        if skip_overlap and len(active_ref) > 1:
            continue
        if collar > 0 and any(abs(mid - b) < collar for b in ref_boundaries):
            continue
        active_hyp = _active_speakers(hyp, t0, t1, eps=eps)
        out.append((t0, t1, active_ref, active_hyp))
    return tuple(out)


# ---------------------------------------------------------------------------
# DER
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DerBreakdown:
    missed_seconds: float
    false_alarm_seconds: float
    confusion_seconds: float
    correct_seconds: float
    total_reference_seconds: float
    scored_seconds: float
    collar_seconds: float
    skip_overlap: bool
    speaker_mapping: Mapping[str, str]

    @property
    def der(self) -> float:
        if self.total_reference_seconds <= 0:
            return 0.0
        return (self.missed_seconds + self.false_alarm_seconds + self.confusion_seconds) / self.total_reference_seconds

    @property
    def der_pct(self) -> float:
        return self.der * 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "missed_seconds": self.missed_seconds,
            "false_alarm_seconds": self.false_alarm_seconds,
            "confusion_seconds": self.confusion_seconds,
            "correct_seconds": self.correct_seconds,
            "total_reference_seconds": self.total_reference_seconds,
            "scored_seconds": self.scored_seconds,
            "collar_seconds": self.collar_seconds,
            "skip_overlap": self.skip_overlap,
            "speaker_mapping": dict(self.speaker_mapping),
            "der": self.der,
            "der_pct": self.der_pct,
        }


def compute_der(
    reference: Sequence[SpeakerSegment],
    hypothesis: Sequence[SpeakerSegment],
    *,
    collar: float = 0.0,
    skip_overlap: bool = False,
    speaker_mapping: Mapping[str, str] | None = None,
) -> DerBreakdown:
    """Diarization error rate under one scoring convention (module
    docstring). ``speaker_mapping`` is an injection seam (tests can pin a
    known mapping rather than re-deriving it); a real caller omits it and
    gets :func:`optimal_speaker_mapping` computed fresh."""

    mapping = dict(speaker_mapping) if speaker_mapping is not None else optimal_speaker_mapping(reference, hypothesis)
    intervals = scored_intervals(reference, hypothesis, collar=collar, skip_overlap=skip_overlap)

    missed = false_alarm = confusion = correct = total_ref = scored = 0.0
    for t0, t1, active_ref, active_hyp in intervals:
        dt = t1 - t0
        n_ref = len(active_ref)
        n_hyp = len(active_hyp)
        n_correct = sum(1 for r in active_ref if mapping.get(r) in active_hyp)
        leftover_ref = n_ref - n_correct
        leftover_hyp = n_hyp - n_correct
        confusion += min(leftover_ref, leftover_hyp) * dt
        missed += max(0, leftover_ref - leftover_hyp) * dt
        false_alarm += max(0, leftover_hyp - leftover_ref) * dt
        correct += n_correct * dt
        total_ref += n_ref * dt
        scored += dt

    return DerBreakdown(
        missed_seconds=missed,
        false_alarm_seconds=false_alarm,
        confusion_seconds=confusion,
        correct_seconds=correct,
        total_reference_seconds=total_ref,
        scored_seconds=scored,
        collar_seconds=collar,
        skip_overlap=skip_overlap,
        speaker_mapping=mapping,
    )


def pool_der_breakdowns(breakdowns: Sequence[DerBreakdown]) -> DerBreakdown:
    """Duration-weighted pooled DER across multiple meetings/files -- sum
    every error/total component, THEN recompute the ratio (the standard
    "score the whole test set as one file" NIST pooling convention), never
    a plain mean of per-meeting DER percentages. Every input must share the
    same ``(collar_seconds, skip_overlap)`` convention; ``speaker_mapping``
    is dropped (a pooled result spans multiple files, each with its own
    mapping -- reported empty rather than misleadingly picking one)."""

    if not breakdowns:
        raise DiarizationScoringError("pool_der_breakdowns requires at least one DerBreakdown")
    collars = {b.collar_seconds for b in breakdowns}
    skips = {b.skip_overlap for b in breakdowns}
    if len(collars) > 1 or len(skips) > 1:
        raise DiarizationScoringError(
            f"pool_der_breakdowns requires every input to share one (collar, skip_overlap) "
            f"convention; got collars={sorted(collars)}, skip_overlap={sorted(skips)}"
        )
    return DerBreakdown(
        missed_seconds=sum(b.missed_seconds for b in breakdowns),
        false_alarm_seconds=sum(b.false_alarm_seconds for b in breakdowns),
        confusion_seconds=sum(b.confusion_seconds for b in breakdowns),
        correct_seconds=sum(b.correct_seconds for b in breakdowns),
        total_reference_seconds=sum(b.total_reference_seconds for b in breakdowns),
        scored_seconds=sum(b.scored_seconds for b in breakdowns),
        collar_seconds=collars.pop(),
        skip_overlap=skips.pop(),
        speaker_mapping={},
    )


# ---------------------------------------------------------------------------
# JER
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JerResult:
    per_speaker_jer: Mapping[str, float]
    jer: float
    speaker_mapping: Mapping[str, str]
    collar_seconds: float
    skip_overlap: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "per_speaker_jer": dict(self.per_speaker_jer),
            "jer": self.jer,
            "speaker_mapping": dict(self.speaker_mapping),
            "collar_seconds": self.collar_seconds,
            "skip_overlap": self.skip_overlap,
        }


def compute_jer(
    reference: Sequence[SpeakerSegment],
    hypothesis: Sequence[SpeakerSegment],
    *,
    collar: float = 0.0,
    skip_overlap: bool = False,
    speaker_mapping: Mapping[str, str] | None = None,
) -> JerResult:
    """Jaccard error rate under one scoring convention (module docstring).
    Reuses :func:`optimal_speaker_mapping` (or an injected ``speaker_mapping``)
    and :func:`scored_intervals` -- the same mapping/exclusion machinery
    :func:`compute_der` uses, so a DER/JER pair computed on the same
    ``(reference, hypothesis, collar, skip_overlap)`` always agrees on which
    speaker corresponds to which and which time is in-scope."""

    mapping = dict(speaker_mapping) if speaker_mapping is not None else optimal_speaker_mapping(reference, hypothesis)
    ref_speakers = speaker_set(_validate_segments(reference, label="reference"))
    intervals = scored_intervals(reference, hypothesis, collar=collar, skip_overlap=skip_overlap)

    ref_time: dict[str, float] = {s: 0.0 for s in ref_speakers}
    hyp_time: dict[str, float] = {}
    intersection: dict[str, float] = {s: 0.0 for s in ref_speakers}

    for t0, t1, active_ref, active_hyp in intervals:
        dt = t1 - t0
        for r in active_ref:
            ref_time[r] = ref_time.get(r, 0.0) + dt
            mapped = mapping.get(r)
            if mapped is not None and mapped in active_hyp:
                intersection[r] = intersection.get(r, 0.0) + dt
        for h in active_hyp:
            hyp_time[h] = hyp_time.get(h, 0.0) + dt

    per_speaker: dict[str, float] = {}
    for r in ref_speakers:
        mapped = mapping.get(r)
        if mapped is None:
            per_speaker[r] = 1.0
            continue
        union = ref_time.get(r, 0.0) + hyp_time.get(mapped, 0.0) - intersection.get(r, 0.0)
        per_speaker[r] = 1.0 - (intersection.get(r, 0.0) / union) if union > 0 else 0.0

    jer = (sum(per_speaker.values()) / len(per_speaker)) if per_speaker else 0.0
    return JerResult(
        per_speaker_jer=per_speaker, jer=jer, speaker_mapping=mapping, collar_seconds=collar, skip_overlap=skip_overlap
    )
