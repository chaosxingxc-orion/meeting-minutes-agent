"""Per-speaker segment type and the anti-gaming timestamp validator.

Time-constrained WER metrics (tcpWER, tcORC-WER) are only meaningful if the
hypothesis carries REAL per-segment timestamps. A hypothesis stream that
fakes timestamps (all zero, all identical, or out of order) can make a
time-constrained metric look arbitrarily good without the system actually
producing usable timing information. :func:`validate_real_timestamps` is a
hard gate (raises, never warns) run before any time-constrained computation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class PerSpeakerSegment:
    """One speaker-attributed, timed segment of a transcript stream --
    the common input shape for every WER-family wrapper in :mod:`.wer`."""

    speaker: str
    start: float
    end: float
    words: str


class TimestampValidationError(ValueError):
    """Raised by :func:`validate_real_timestamps` when a segment stream
    fails the anti-gaming check. This is a hard error, never a warning --
    a caller must fix the upstream timing before a time-constrained metric
    is computed on this stream."""


def validate_real_timestamps(
    segments: Sequence[PerSpeakerSegment],
    *,
    label: str = "stream",
) -> None:
    """Refuse (raise :class:`TimestampValidationError`) unless ``segments``
    carries real per-segment timestamps. Checks, in order:

    1. non-empty -- an empty stream has nothing to time-constrain against.
    2. not all-zero -- ``start == end == 0`` for every segment is the
       textbook "timestamps never populated" signature.
    3. not all-equal -- every segment sharing one identical (start, end)
       pair means the timestamps were stamped once and copied, not derived
       per segment.
    4. no inverted segment -- ``end < start`` on any segment.
    5. monotonic per speaker -- within each speaker's own sub-stream (the
       order the segments for that speaker appear in ``segments``), start
       times must be non-decreasing. This is checked per speaker rather
       than globally because two speakers' segments may legitimately
       interleave; a per-speaker stream going backwards in time cannot.
    """

    if not segments:
        raise TimestampValidationError(f"{label}: empty segment stream has no timestamps to validate")

    starts = [s.start for s in segments]
    ends = [s.end for s in segments]

    if all(s == 0 for s in starts) and all(e == 0 for e in ends):
        raise TimestampValidationError(
            f"{label}: all {len(segments)} segment(s) have start == end == 0 "
            "-- timestamps look unpopulated, refusing time-constrained scoring"
        )

    distinct_pairs = {(s.start, s.end) for s in segments}
    if len(segments) > 1 and len(distinct_pairs) == 1:
        (only_pair,) = distinct_pairs
        raise TimestampValidationError(
            f"{label}: all {len(segments)} segment(s) share the identical timestamp pair "
            f"{only_pair} -- timestamps look stamped-once-and-copied, refusing time-constrained scoring"
        )

    for i, s in enumerate(segments):
        if s.end < s.start:
            raise TimestampValidationError(
                f"{label}: segment {i} (speaker {s.speaker!r}) has end ({s.end}) < start ({s.start})"
            )

    by_speaker: dict[str, list[float]] = {}
    for s in segments:
        by_speaker.setdefault(s.speaker, []).append(s.start)
    for speaker, speaker_starts in by_speaker.items():
        for a, b in zip(speaker_starts, speaker_starts[1:]):
            if b < a:
                raise TimestampValidationError(
                    f"{label}: speaker {speaker!r} stream is non-monotonic in start time "
                    f"({a} then {b}) -- refusing time-constrained scoring"
                )
