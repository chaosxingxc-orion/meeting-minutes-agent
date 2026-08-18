"""Thin, pinned wrappers around meeteval's attribution/WER-family metrics.

Never reimplement WER-family scoring -- every number here comes from
meeteval 0.4.3 (``meeteval.wer.cp_word_error_rate``,
``meeteval.wer.orc_word_error_rate``,
``meeteval.wer.time_constrained.tcp_word_error_rate``,
``meeteval.wer.time_constrained_orc_wer``), called with parameters pinned by
:class:`~meeting_minutes_agent.metrics.pins.MetricPins`.

Per the deep-check registered changes (see :mod:`.pins` docstring), the
PRIMARY confusion cost is tcpWER minus tcORC-WER at collar 5s, computed on
an IDENTICAL per-speaker stream pair. That "identical pair" requirement is
enforced BY CONSTRUCTION here: :func:`primary_confusion_cost` takes the
``(reference, hypothesis)`` stream pair exactly once and derives both terms
from that one pair -- there is no way to call it with two different stream
pairs for the two terms.

cpWER minus ORC-WER is exposed as :func:`secondary_confusion_cost`, a
LITERATURE-COMPARABLE metric only -- see its docstring for the reordering
caveat.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .pins import MetricPins, default_metric_pins
from .timestamps import PerSpeakerSegment, validate_real_timestamps

__all__ = [
    "WerResult",
    "ConfusionCostResult",
    "compute_cp_wer",
    "compute_orc_wer",
    "compute_tcp_wer",
    "compute_tcorc_wer",
    "primary_confusion_cost",
    "secondary_confusion_cost",
]


def _to_seglst(segments: Sequence[PerSpeakerSegment]):
    """Convert this repository's :class:`PerSpeakerSegment` stream into a
    ``meeteval.io.SegLST`` -- meeteval's own segment-list format. Local
    import: meeteval stays an optional, function-local dependency."""

    from meeteval.io import SegLST

    return SegLST(
        [
            {"speaker": s.speaker, "start_time": s.start, "end_time": s.end, "words": s.words}
            for s in segments
        ]
    )


@dataclass(frozen=True)
class WerResult:
    """A single WER-family number plus its full error breakdown and the
    pins it was computed with -- deliberately flat and JSON-serializable
    (meeteval's own result dataclasses nest further dataclasses/namedtuples
    that do not round-trip through ``json.dumps`` without help)."""

    metric: str  # "cpWER" | "ORC-WER" | "tcpWER" | "tcORC-WER"
    error_rate: float
    errors: int
    length: int
    insertions: int
    deletions: int
    substitutions: int
    pins_hash: str

    def to_dict(self) -> dict[str, object]:
        return {
            "metric": self.metric,
            "error_rate": self.error_rate,
            "errors": self.errors,
            "length": self.length,
            "insertions": self.insertions,
            "deletions": self.deletions,
            "substitutions": self.substitutions,
            "pins_hash": self.pins_hash,
        }


def _summarize(metric: str, raw, pins: MetricPins) -> WerResult:
    return WerResult(
        metric=metric,
        error_rate=raw.error_rate,
        errors=raw.errors,
        length=raw.length,
        insertions=raw.insertions,
        deletions=raw.deletions,
        substitutions=raw.substitutions,
        pins_hash=pins.content_hash(),
    )


def compute_cp_wer(
    reference: Sequence[PerSpeakerSegment],
    hypothesis: Sequence[PerSpeakerSegment],
    *,
    pins: MetricPins | None = None,
) -> WerResult:
    """cpWER (concatenated-minimum-permutation WER) -- literature-comparable,
    NOT time-constrained. No timestamp validation: cpWER does not use
    timing to constrain the alignment."""

    import meeteval.wer as mw

    pins = pins or default_metric_pins()
    raw = mw.cp_word_error_rate(
        reference=_to_seglst(reference),
        hypothesis=_to_seglst(hypothesis),
        reference_sort=pins.reference_sort,
        hypothesis_sort=pins.hypothesis_sort,
    )
    return _summarize("cpWER", raw, pins)


def compute_orc_wer(
    reference: Sequence[PerSpeakerSegment],
    hypothesis: Sequence[PerSpeakerSegment],
    *,
    pins: MetricPins | None = None,
) -> WerResult:
    """ORC-WER (optimal reference combination WER) -- literature-comparable,
    NOT time-constrained. CAVEAT (see :func:`secondary_confusion_cost`):
    system-side utterance reordering inflates ORC-WER relative to cpWER,
    which shrinks the cpWER-ORC-WER difference. No timestamp validation:
    ORC-WER does not use timing to constrain the alignment."""

    import meeteval.wer as mw

    pins = pins or default_metric_pins()
    raw = mw.orc_word_error_rate(
        reference=_to_seglst(reference),
        hypothesis=_to_seglst(hypothesis),
        reference_sort=pins.reference_sort,
        hypothesis_sort=pins.hypothesis_sort,
    )
    return _summarize("ORC-WER", raw, pins)


def compute_tcp_wer(
    reference: Sequence[PerSpeakerSegment],
    hypothesis: Sequence[PerSpeakerSegment],
    *,
    pins: MetricPins | None = None,
) -> WerResult:
    """tcpWER (time-constrained cpWER) at ``pins.collar_seconds``.
    Anti-gaming: both streams must pass :func:`validate_real_timestamps`
    first -- a hard error, not a warning, if either fails."""

    import meeteval.wer as mw

    pins = pins or default_metric_pins()
    validate_real_timestamps(reference, label="reference")
    validate_real_timestamps(hypothesis, label="hypothesis")
    raw = mw.time_constrained.tcp_word_error_rate(
        reference=_to_seglst(reference),
        hypothesis=_to_seglst(hypothesis),
        collar=pins.collar_seconds,
        reference_pseudo_word_level_timing=pins.reference_pseudo_word_level_timing,
        hypothesis_pseudo_word_level_timing=pins.hypothesis_pseudo_word_level_timing,
        reference_sort=pins.reference_sort,
        hypothesis_sort=pins.hypothesis_sort,
    )
    return _summarize("tcpWER", raw, pins)


def compute_tcorc_wer(
    reference: Sequence[PerSpeakerSegment],
    hypothesis: Sequence[PerSpeakerSegment],
    *,
    pins: MetricPins | None = None,
) -> WerResult:
    """tcORC-WER (time-constrained ORC-WER) at ``pins.collar_seconds``.
    Anti-gaming: both streams must pass :func:`validate_real_timestamps`
    first -- a hard error, not a warning, if either fails."""

    import meeteval.wer as mw

    pins = pins or default_metric_pins()
    validate_real_timestamps(reference, label="reference")
    validate_real_timestamps(hypothesis, label="hypothesis")
    raw = mw.time_constrained_orc_wer(
        reference=_to_seglst(reference),
        hypothesis=_to_seglst(hypothesis),
        collar=pins.collar_seconds,
        reference_pseudo_word_level_timing=pins.reference_pseudo_word_level_timing,
        hypothesis_pseudo_word_level_timing=pins.hypothesis_pseudo_word_level_timing,
        reference_sort=pins.reference_sort,
        hypothesis_sort=pins.hypothesis_sort,
    )
    return _summarize("tcORC-WER", raw, pins)


@dataclass(frozen=True)
class ConfusionCostResult:
    """Both terms of a confusion-cost difference (``minuend - subtrahend``)
    plus the difference itself, all derived from ONE stream pair passed to
    ONE function. ``minuend``/``subtrahend`` are named generically because
    this same shape carries either the primary pair (tcpWER, tcORC-WER) or
    the secondary pair (cpWER, ORC-WER) -- see :attr:`minuend`'s ``metric``
    field for which."""

    minuend: WerResult
    subtrahend: WerResult

    @property
    def confusion_cost(self) -> float:
        return self.minuend.error_rate - self.subtrahend.error_rate

    def to_dict(self) -> dict[str, object]:
        return {
            "minuend": self.minuend.to_dict(),
            "subtrahend": self.subtrahend.to_dict(),
            "confusion_cost": self.confusion_cost,
        }


def primary_confusion_cost(
    reference: Sequence[PerSpeakerSegment],
    hypothesis: Sequence[PerSpeakerSegment],
    *,
    pins: MetricPins | None = None,
) -> ConfusionCostResult:
    """PRIMARY confusion cost: tcpWER - tcORC-WER at collar 5s (deep-check
    registered pin), computed on the SAME ``(reference, hypothesis)`` stream
    pair for both terms -- the pair is taken once, by this function's
    signature, so the two terms can never silently drift onto different
    inputs. Both streams pass the anti-gaming timestamp check (via
    :func:`compute_tcp_wer` / :func:`compute_tcorc_wer`) before either term
    is computed.

    Interpretation: tcpWER charges both content errors AND wrong-speaker
    assignment; tcORC-WER charges content errors alone (it is allowed to
    reassign each reference utterance to whichever hypothesis stream fits
    best). The gap between them isolates the speaker-attribution/confusion
    component of the error.
    """

    pins = pins or default_metric_pins()
    tcp = compute_tcp_wer(reference, hypothesis, pins=pins)
    tcorc = compute_tcorc_wer(reference, hypothesis, pins=pins)
    return ConfusionCostResult(minuend=tcp, subtrahend=tcorc)


def secondary_confusion_cost(
    reference: Sequence[PerSpeakerSegment],
    hypothesis: Sequence[PerSpeakerSegment],
    *,
    pins: MetricPins | None = None,
) -> ConfusionCostResult:
    """SECONDARY, literature-comparable confusion cost: cpWER - ORC-WER
    (no time constraint), computed on the same stream pair for both terms.

    CAVEAT (deep-check registered, binding): system-side utterance
    reordering inflates ORC-WER (ORC-WER is free to reassign each reference
    utterance to its best-fitting hypothesis stream, but is NOT free to
    reorder within a stream the way tcORC-WER's time constraint implicitly
    discourages) -- this shrinks the cpWER-ORC-WER difference relative to
    the time-constrained primary. Do not treat this secondary number as
    interchangeable with the primary; report it only for comparison against
    prior literature that used cpWER/ORC-WER without a time constraint.
    """

    pins = pins or default_metric_pins()
    cp = compute_cp_wer(reference, hypothesis, pins=pins)
    orc = compute_orc_wer(reference, hypothesis, pins=pins)
    return ConfusionCostResult(minuend=cp, subtrahend=orc)
