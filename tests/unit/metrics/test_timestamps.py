from __future__ import annotations

import pytest

from meeting_minutes_agent.metrics.timestamps import (
    PerSpeakerSegment,
    TimestampValidationError,
    validate_real_timestamps,
)


def _seg(speaker: str, start: float, end: float, words: str = "x") -> PerSpeakerSegment:
    return PerSpeakerSegment(speaker=speaker, start=start, end=end, words=words)


def test_real_timestamps_pass():
    segments = [
        _seg("A", 0.0, 1.0),
        _seg("B", 1.0, 2.0),
        _seg("A", 2.0, 3.0),
    ]
    validate_real_timestamps(segments)  # must not raise


def test_empty_stream_rejected():
    with pytest.raises(TimestampValidationError, match="empty"):
        validate_real_timestamps([])


def test_all_zero_timestamps_rejected():
    segments = [_seg("A", 0.0, 0.0), _seg("B", 0.0, 0.0)]
    with pytest.raises(TimestampValidationError, match="start == end == 0"):
        validate_real_timestamps(segments)


def test_all_equal_timestamps_rejected():
    segments = [_seg("A", 3.0, 4.0), _seg("B", 3.0, 4.0), _seg("A", 3.0, 4.0)]
    with pytest.raises(TimestampValidationError, match="identical timestamp pair"):
        validate_real_timestamps(segments)


def test_single_segment_never_triggers_all_equal_rejection():
    # One segment cannot violate "all segments share ONE pair" in a
    # meaningful way -- it must still be rejected only by the all-zero
    # rule if it applies, not by the all-equal rule.
    validate_real_timestamps([_seg("A", 1.0, 2.0)])  # must not raise


def test_inverted_segment_rejected():
    segments = [_seg("A", 0.0, 1.0), _seg("B", 5.0, 2.0)]
    with pytest.raises(TimestampValidationError, match="end .* < start"):
        validate_real_timestamps(segments)


def test_non_monotonic_per_speaker_stream_rejected():
    # Speaker A's own stream goes backwards in time (1.0 -> 2.0 -> 0.5),
    # even though the segments interleave with B in between.
    segments = [
        _seg("A", 1.0, 1.5),
        _seg("B", 1.2, 1.8),
        _seg("A", 2.0, 2.5),
        _seg("B", 2.2, 2.8),
        _seg("A", 0.5, 0.9),
    ]
    with pytest.raises(TimestampValidationError, match="non-monotonic"):
        validate_real_timestamps(segments)


def test_interleaved_but_per_speaker_monotonic_streams_pass():
    # Global order is not monotonic (A and B interleave with overlap) but
    # EACH speaker's own sub-stream is non-decreasing -- must pass.
    segments = [
        _seg("A", 0.0, 1.0),
        _seg("B", 0.5, 1.5),
        _seg("A", 1.2, 2.0),
    ]
    validate_real_timestamps(segments)  # must not raise


def test_error_message_carries_label():
    with pytest.raises(TimestampValidationError, match="^hypothesis:"):
        validate_real_timestamps([], label="hypothesis")
