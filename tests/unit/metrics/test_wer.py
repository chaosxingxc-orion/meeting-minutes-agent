"""meeteval-dependent tests -- gated on import availability
(`pytest.importorskip`), but meant to actually run in the WSL2 shared venv
where meeteval 0.4.3 is installed (see CLAUDE.md environment section). The
expected numbers below were confirmed by direct computation against the
installed meeteval 0.4.3 before being pinned into these assertions (not
hand-derived from meeteval's permutation-search internals, which are not
meant to be reproduced by hand) -- the accompanying comments explain, by
plain word counting, why each number is what it is.
"""

from __future__ import annotations

import pytest

pytest.importorskip("meeteval")

from meeting_minutes_agent.metrics.pins import MetricPins
from meeting_minutes_agent.metrics.timestamps import PerSpeakerSegment, TimestampValidationError
from meeting_minutes_agent.metrics.wer import (
    compute_cp_wer,
    compute_orc_wer,
    compute_tcorc_wer,
    compute_tcp_wer,
    primary_confusion_cost,
    secondary_confusion_cost,
)


def _seg(speaker: str, start: float, end: float, words: str) -> PerSpeakerSegment:
    return PerSpeakerSegment(speaker=speaker, start=start, end=end, words=words)


_PINS = MetricPins(meeteval_version="0.4.3")

# --- Fixture 1: unambiguous 2-speaker content errors only (no speaker
# confusion possible -- content alone disambiguates A from B), so cpWER ==
# ORC-WER and the confusion cost should be exactly 0.
#
# Reference: A "hello world" (2 words), B "foo bar" (2 words) -- 4 words total.
# Hypothesis: A "hello there" (1 substitution: world -> there),
#             B "foo bar baz" (1 insertion: baz).
# errors = 2, length = 4, WER = 2/4 = 0.5 (hand-countable).
_REF_CONTENT_ONLY = [
    _seg("A", 0.0, 1.0, "hello world"),
    _seg("B", 1.0, 2.0, "foo bar"),
]
_HYP_CONTENT_ONLY = [
    _seg("A", 0.0, 1.0, "hello there"),
    _seg("B", 1.0, 2.0, "foo bar baz"),
]

# --- Fixture 2: over-segmented hypothesis. Content is word-for-word
# perfect, but speaker A's two turns are split across two DIFFERENT
# hypothesis streams (X and Z) instead of one, with an extra stray
# hypothesis speaker (Z) that has no single-permutation counterpart.
#
# Reference: A "one two" (0-1s), B "three four" (1-2s), A "five six" (2-3s).
# Hypothesis: X "one two" (0-1s), Y "three four" (1-2s), Z "five six" (2-3s).
#
# ORC-WER may reassign each REFERENCE utterance independently to whichever
# hypothesis stream fits best -- A's first turn -> X, B's turn -> Y, A's
# second turn -> Z: every utterance matches exactly, so ORC-WER = 0.
# cpWER must pick ONE global speaker permutation for the whole session; A
# cannot be simultaneously mapped to both X and Z, so under the best
# 2-of-3 permutation search it takes real errors AND scores the
# unassigned hypothesis speaker as a false-alarm stream. Confirmed by
# direct meeteval 0.4.3 computation: cpWER = 4 errors / 6 words = 2/3.
_REF_OVER_SEGMENTED = [
    _seg("A", 0.0, 1.0, "one two"),
    _seg("B", 1.0, 2.0, "three four"),
    _seg("A", 2.0, 3.0, "five six"),
]
_HYP_OVER_SEGMENTED = [
    _seg("X", 0.0, 1.0, "one two"),
    _seg("Y", 1.0, 2.0, "three four"),
    _seg("Z", 2.0, 3.0, "five six"),
]


def test_compute_cp_wer_content_only_fixture():
    result = compute_cp_wer(_REF_CONTENT_ONLY, _HYP_CONTENT_ONLY, pins=_PINS)
    assert result.metric == "cpWER"
    assert (result.errors, result.length) == (2, 4)
    assert result.error_rate == pytest.approx(0.5)
    assert result.insertions == 1
    assert result.substitutions == 1
    assert result.deletions == 0
    assert result.pins_hash == _PINS.content_hash()


def test_compute_orc_wer_content_only_fixture_matches_cp_wer():
    cp = compute_cp_wer(_REF_CONTENT_ONLY, _HYP_CONTENT_ONLY, pins=_PINS)
    orc = compute_orc_wer(_REF_CONTENT_ONLY, _HYP_CONTENT_ONLY, pins=_PINS)
    assert orc.metric == "ORC-WER"
    assert orc.error_rate == pytest.approx(cp.error_rate) == pytest.approx(0.5)


def test_compute_tcp_and_tcorc_wer_content_only_fixture_matches_untimed():
    tcp = compute_tcp_wer(_REF_CONTENT_ONLY, _HYP_CONTENT_ONLY, pins=_PINS)
    tcorc = compute_tcorc_wer(_REF_CONTENT_ONLY, _HYP_CONTENT_ONLY, pins=_PINS)
    assert tcp.metric == "tcpWER"
    assert tcorc.metric == "tcORC-WER"
    assert tcp.error_rate == pytest.approx(0.5)
    assert tcorc.error_rate == pytest.approx(0.5)


def test_primary_confusion_cost_is_zero_when_speaker_identity_is_unambiguous():
    result = primary_confusion_cost(_REF_CONTENT_ONLY, _HYP_CONTENT_ONLY, pins=_PINS)
    assert result.confusion_cost == pytest.approx(0.0)
    assert result.minuend.metric == "tcpWER"
    assert result.subtrahend.metric == "tcORC-WER"


def test_secondary_confusion_cost_is_zero_when_speaker_identity_is_unambiguous():
    result = secondary_confusion_cost(_REF_CONTENT_ONLY, _HYP_CONTENT_ONLY, pins=_PINS)
    assert result.confusion_cost == pytest.approx(0.0)
    assert result.minuend.metric == "cpWER"
    assert result.subtrahend.metric == "ORC-WER"


def test_primary_confusion_cost_is_positive_on_over_segmented_hypothesis():
    result = primary_confusion_cost(_REF_OVER_SEGMENTED, _HYP_OVER_SEGMENTED, pins=_PINS)
    assert result.minuend.error_rate == pytest.approx(2 / 3)
    assert result.subtrahend.error_rate == pytest.approx(0.0)
    assert result.confusion_cost == pytest.approx(2 / 3)


def test_secondary_confusion_cost_matches_primary_on_this_fixture():
    # At collar=5s these 1-second-apart segments give the time-constrained
    # and untimed metrics the same numbers -- confirmed by direct
    # computation; the two metrics are NOT interchangeable in general (see
    # secondary_confusion_cost's docstring caveat), they simply agree here.
    primary = primary_confusion_cost(_REF_OVER_SEGMENTED, _HYP_OVER_SEGMENTED, pins=_PINS)
    secondary = secondary_confusion_cost(_REF_OVER_SEGMENTED, _HYP_OVER_SEGMENTED, pins=_PINS)
    assert secondary.confusion_cost == pytest.approx(primary.confusion_cost)


def test_primary_confusion_cost_enforces_identical_stream_pair_by_construction():
    # There is no keyword/positional way to hand the minuend and
    # subtrahend different reference/hypothesis streams -- the function
    # signature only accepts one (reference, hypothesis) pair.
    import inspect

    sig = inspect.signature(primary_confusion_cost)
    assert list(sig.parameters)[:2] == ["reference", "hypothesis"]


def test_primary_confusion_cost_rejects_all_zero_hypothesis_timestamps():
    bad_hyp = [
        _seg("A", 0.0, 0.0, "hello there"),
        _seg("B", 0.0, 0.0, "foo bar baz"),
    ]
    with pytest.raises(TimestampValidationError):
        primary_confusion_cost(_REF_CONTENT_ONLY, bad_hyp, pins=_PINS)


def test_secondary_confusion_cost_does_not_require_real_timestamps():
    # cpWER/ORC-WER are not time-constrained -- degenerate timestamps must
    # not block the secondary (literature-comparable) metric.
    bad_hyp = [
        _seg("A", 0.0, 0.0, "hello there"),
        _seg("B", 0.0, 0.0, "foo bar baz"),
    ]
    result = secondary_confusion_cost(_REF_CONTENT_ONLY, bad_hyp, pins=_PINS)
    assert result.confusion_cost == pytest.approx(0.0)


def test_default_pins_used_when_none_passed():
    result = compute_cp_wer(_REF_CONTENT_ONLY, _HYP_CONTENT_ONLY)
    assert result.pins_hash  # a real hash was stamped, not blank
