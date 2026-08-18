"""P-ATTR offline scoring path: parsed replies -> per-speaker hypothesis
streams -> cpWER-family confusion cost against the AMI gold streams, plus
the A-grid boundary-respect diagnostic.

Read-only and OFFLINE, per mission scope: every function here scores
already-collected records (a flight's parsed replies) against the AMI gold
transcript already resolved by :mod:`meeting_minutes_agent.corpora.nxt`;
nothing in this module performs a model or network call.

Timing discipline (binding, ``docs/readiness/2026-08-18-g1-preregistration-
draft.md`` SS0/SS"Timing rule"): a time-constrained metric (tcpWER/tcORC-WER,
i.e. :func:`~meeting_minutes_agent.metrics.wer.primary_confusion_cost`) may
only be computed on a hypothesis stream carrying REAL per-segment timing --
never a fabricated/synthetic one. The A-grid/A-free reply grammar
(``<speaker>|<text>`` lines, :mod:`meeting_minutes_agent.heads.
transcribe_attribute`) carries no per-segment timestamp at all, so this
module never invents one for those two arms (the coarse whole-slice bounds
recorded on their :class:`HypothesisSegment`\\ s are for provenance/reporting
only, never fed to a time-constrained metric -- see
:attr:`HypothesisSegment.real_timing`). A-turn is different: each request
already maps 1:1 onto one manifest turn with a real, gold-provenance span, so
its hypothesis stream is REAL-timed by construction and is the only stream
:func:`score_arm` will compute ``primary_confusion_cost`` for. This is
recorded explicitly, per meeting/arm, on
:attr:`PattrArmScore.primary_confusion_cost_skipped_reason` rather than
silently omitted -- the same "an honest metric blind spot, recorded here"
discipline the pre-registration draft itself uses for utterance
segmentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from ..metrics.pins import MetricPins
from ..metrics.timestamps import PerSpeakerSegment
from ..metrics.wer import (
    ConfusionCostResult,
    WerResult,
    compute_cp_wer,
    primary_confusion_cost,
    secondary_confusion_cost,
)

if TYPE_CHECKING:
    from ..corpora.nxt.models import ResolvedMeeting
    from ..heads.transcribe_attribute import TranscribedSegment

_PRIMARY_SKIPPED_REASON = (
    "hypothesis stream carries no real per-segment timing (the A-grid/A-free reply grammar "
    "has none); the G1 binding rule refuses a synthetic/even-split timestamp for a "
    "time-constrained metric, so primary_confusion_cost (tcpWER - tcORC-WER) is not computed "
    "for this stream -- only secondary_confusion_cost (cpWER - ORC-WER, untimed) is reported"
)

__all__ = [
    "extract_gold_streams_for_range",
    "HypothesisSegment",
    "hypothesis_stream_from_grid_or_free_parse",
    "hypothesis_segment_from_turn_reply",
    "PattrArmScore",
    "score_arm",
    "BoundaryRespectResult",
    "boundary_respect_diagnostic",
]


# ---------------------------------------------------------------------------
# gold-stream extraction for a time range
# ---------------------------------------------------------------------------


def extract_gold_streams_for_range(
    resolved: "ResolvedMeeting", *, start: float, end: float
) -> tuple[PerSpeakerSegment, ...]:
    """Every gold ``Utterance`` in ``resolved.transcript`` whose span
    overlaps ``[start, end)``, CLIPPED to that range, as a chronologically
    ordered :class:`~meeting_minutes_agent.metrics.timestamps.PerSpeakerSegment`
    stream -- the reference side of every P-ATTR score. An utterance with no
    start/end, no overlap, or no reconstructed text is dropped rather than
    included with a fabricated span."""

    if end <= start:
        raise ValueError(f"extract_gold_streams_for_range requires end > start, got start={start}, end={end}")

    out: list[PerSpeakerSegment] = []
    for u in resolved.transcript:
        if u.start is None or u.end is None or not u.text:
            continue
        clipped_start = max(u.start, start)
        clipped_end = min(u.end, end)
        if clipped_end <= clipped_start:
            continue
        out.append(PerSpeakerSegment(speaker=u.speaker, start=clipped_start, end=clipped_end, words=u.text))
    out.sort(key=lambda s: (s.start, s.end))
    return tuple(out)


# ---------------------------------------------------------------------------
# hypothesis streams
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HypothesisSegment:
    """One parsed/attributed hypothesis segment, plus the coarse timing it
    inherits from the manifest and whether that timing is REAL (module
    docstring). ``real_timing=False`` segments still carry a ``(start,
    end)`` pair (the whole slice's bounds) purely for reporting/provenance;
    :func:`score_arm` never feeds them to a time-constrained metric."""

    speaker: str
    text: str
    start: float
    end: float
    real_timing: bool

    def as_per_speaker_segment(self) -> PerSpeakerSegment:
        return PerSpeakerSegment(speaker=self.speaker, start=self.start, end=self.end, words=self.text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "speaker": self.speaker,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "real_timing": self.real_timing,
        }


def hypothesis_stream_from_grid_or_free_parse(
    parsed_segments: Sequence["TranscribedSegment"], *, slice_start: float, slice_end: float
) -> tuple[HypothesisSegment, ...]:
    """A-grid/A-free hypothesis stream: the parsed ``{speaker, text}``
    records from ONE slice's reply, in reply order. Every segment is
    stamped with the whole SLICE's bounds (``real_timing=False``) -- the
    reply grammar carries no finer timing than that (module docstring)."""

    return tuple(
        HypothesisSegment(speaker=s.speaker, text=s.text, start=slice_start, end=slice_end, real_timing=False)
        for s in parsed_segments
    )


def hypothesis_segment_from_turn_reply(
    *, known_speaker: str, transcribed_text: str, turn_start: float, turn_end: float
) -> HypothesisSegment:
    """A-turn hypothesis segment: attribution is BY CONSTRUCTION (the
    speaker is read from the manifest, never parsed out of the reply -- the
    transcribe-only template asks for none) and timing is REAL (the
    manifest's own gold-provenance turn span) -- the one arm whose stream
    may legitimately feed a time-constrained metric."""

    return HypothesisSegment(
        speaker=known_speaker, text=transcribed_text, start=turn_start, end=turn_end, real_timing=True
    )


# ---------------------------------------------------------------------------
# per-arm scoring
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PattrArmScore:
    arm: str
    meeting_id: str
    n_reference_segments: int
    n_hypothesis_segments: int
    cp_wer: WerResult
    secondary_confusion_cost: ConfusionCostResult
    primary_confusion_cost: ConfusionCostResult | None
    primary_confusion_cost_skipped_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "meeting_id": self.meeting_id,
            "n_reference_segments": self.n_reference_segments,
            "n_hypothesis_segments": self.n_hypothesis_segments,
            "cp_wer": self.cp_wer.to_dict(),
            "secondary_confusion_cost": self.secondary_confusion_cost.to_dict(),
            "primary_confusion_cost": (
                self.primary_confusion_cost.to_dict() if self.primary_confusion_cost is not None else None
            ),
            "primary_confusion_cost_skipped_reason": self.primary_confusion_cost_skipped_reason,
        }


def score_arm(
    arm: str,
    meeting_id: str,
    reference: Sequence[PerSpeakerSegment],
    hypothesis: Sequence[HypothesisSegment],
    *,
    pins: MetricPins | None = None,
) -> PattrArmScore:
    """Score one arm's one meeting: cpWER and secondary_confusion_cost
    (cpWER - ORC-WER, untimed -- always computable) always; primary
    confusion cost (tcpWER - tcORC-WER, collar 5s) ONLY when every
    hypothesis segment carries real per-segment timing (module docstring)
    -- otherwise ``primary_confusion_cost`` is ``None`` and
    ``primary_confusion_cost_skipped_reason`` explains why, never silently
    dropped.

    Known upstream limitation (not handled specially here): a COMPLETELY
    empty ``hypothesis`` (zero segments, e.g. a slice whose reply parsed to
    nothing at all) can trip an internal consistency assertion inside
    meeteval 0.4.3's own ORC-WER implementation before this function gets a
    chance to return a result -- confirmed against the installed version,
    not something this module's cpWER-family wrapper layer can paper over.
    A caller scoring a real flight should treat a genuinely empty reply as
    its own diagnostic case (e.g. "0 segments parsed") rather than routing
    it into this function."""

    hyp_psegs = tuple(h.as_per_speaker_segment() for h in hypothesis)
    cp = compute_cp_wer(reference, hyp_psegs, pins=pins)
    secondary = secondary_confusion_cost(reference, hyp_psegs, pins=pins)

    all_real = bool(hypothesis) and all(h.real_timing for h in hypothesis)
    if all_real:
        primary: ConfusionCostResult | None = primary_confusion_cost(reference, hyp_psegs, pins=pins)
        reason: str | None = None
    else:
        primary = None
        reason = _PRIMARY_SKIPPED_REASON

    return PattrArmScore(
        arm=arm,
        meeting_id=meeting_id,
        n_reference_segments=len(reference),
        n_hypothesis_segments=len(hypothesis),
        cp_wer=cp,
        secondary_confusion_cost=secondary,
        primary_confusion_cost=primary,
        primary_confusion_cost_skipped_reason=reason,
    )


# ---------------------------------------------------------------------------
# A-grid boundary-respect diagnostic
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BoundaryRespectResult:
    """``n_compared`` is ``min(len(parsed_segments), len(declared_grid_turns))``
    -- a count MISMATCH (the model emitting more or fewer segments than the
    declared grid) is itself diagnostic and stays visible via the caller's
    own record of both raw lengths, never silently folded into
    :attr:`fraction_matched`."""

    n_compared: int
    n_matched: int

    @property
    def fraction_matched(self) -> float:
        return self.n_matched / self.n_compared if self.n_compared else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_compared": self.n_compared,
            "n_matched": self.n_matched,
            "fraction_matched": self.fraction_matched,
        }


def boundary_respect_diagnostic(
    parsed_segments: Sequence["TranscribedSegment"], declared_grid_turns: Sequence[Mapping[str, Any]]
) -> BoundaryRespectResult:
    """A-grid ONLY: for each position ``i`` where both a parsed segment and
    a declared grid entry exist, does the parsed segment's speaker match
    the declared span's speaker AT THAT SAME POSITION/ORDER -- not by time
    overlap (the parsed reply carries no timing to overlap with, module
    docstring), by the same ordering
    :func:`~meeting_minutes_agent.heads.transcribe_attribute.build_declared_grid_block`
    numbered the grid with. Comparison is case-/whitespace-insensitive
    (``str.strip().casefold()``) -- a speaker label differing only in case
    is not a boundary-respect failure."""

    n = min(len(parsed_segments), len(declared_grid_turns))
    matched = 0
    for i in range(n):
        parsed_speaker = parsed_segments[i].speaker.strip().casefold()
        declared_speaker = str(declared_grid_turns[i]["speaker"]).strip().casefold()
        if parsed_speaker == declared_speaker:
            matched += 1
    return BoundaryRespectResult(n_compared=n, n_matched=matched)
