"""Tests for :mod:`meeting_minutes_agent.metrics.diarization_error`: the
native DER/JER scorer. Every DER/JER value below is HAND-COMPUTED in the
test's own docstring/comment (never asserted against a second
implementation) -- perfect match, a single boundary shift, a label
permutation, one missed speaker, a false-alarm speaker, and an overlap
region scored under both registered conventions."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.chunking.slicer import TurnSpan
from meeting_minutes_agent.metrics.diarization_error import (
    MAX_BRUTE_FORCE_SPEAKERS,
    DiarizationScoringError,
    compute_der,
    compute_jer,
    optimal_speaker_mapping,
    pool_der_breakdowns,
    scored_intervals,
    speaker_set,
)


def _turn(speaker: str, start: float, end: float) -> TurnSpan:
    return TurnSpan(start=start, end=end, speaker=speaker)


# ---------------------------------------------------------------------------
# fixture 1: perfect match
# ---------------------------------------------------------------------------


class TestPerfectMatch:
    reference = (_turn("A", 0.0, 10.0), _turn("B", 10.0, 20.0))
    hypothesis = (_turn("A", 0.0, 10.0), _turn("B", 10.0, 20.0))

    def test_der_no_collar_with_overlap_is_zero(self):
        result = compute_der(self.reference, self.hypothesis, collar=0.0, skip_overlap=False)
        assert result.der == pytest.approx(0.0)
        assert result.missed_seconds == pytest.approx(0.0)
        assert result.false_alarm_seconds == pytest.approx(0.0)
        assert result.confusion_seconds == pytest.approx(0.0)
        assert result.total_reference_seconds == pytest.approx(20.0)

    def test_der_collar_ignoring_overlap_is_zero(self):
        result = compute_der(self.reference, self.hypothesis, collar=0.25, skip_overlap=True)
        assert result.der == pytest.approx(0.0)
        # collar excludes a window around each of the 3 reference
        # boundaries (0, 10, 20): the interior boundary at 10 loses a full
        # 0.5s (0.25s on each side, both inside reference-active time); the
        # two edge boundaries (0 and 20) each lose only their inward 0.25s
        # (the outward half falls outside any reference activity, so it
        # never counted toward total_reference_seconds anyway). Excluded:
        # 0.25 + 0.5 + 0.25 = 1.0s, so 20 - 1.0 = 19.0 remain.
        assert result.total_reference_seconds == pytest.approx(19.0)

    def test_jer_is_zero_under_both_conventions(self):
        for collar, skip_overlap in ((0.0, False), (0.25, True)):
            jer = compute_jer(self.reference, self.hypothesis, collar=collar, skip_overlap=skip_overlap)
            assert jer.jer == pytest.approx(0.0)
            assert jer.per_speaker_jer == {"A": pytest.approx(0.0), "B": pytest.approx(0.0)}

    def test_mapping_is_identity(self):
        assert optimal_speaker_mapping(self.reference, self.hypothesis) == {"A": "A", "B": "B"}


# ---------------------------------------------------------------------------
# fixture 2: a single 1s boundary shift
# ---------------------------------------------------------------------------


class TestSingleBoundaryShift:
    # reference: A [0,10), B [10,20); hypothesis boundary shifts 1s early:
    # A [0,9), B [9,20). During [9,10) the reference says A but the
    # hypothesis says B: exactly 1s of confusion, 0 missed, 0 false alarm.
    # DER = 1 / 20 = 0.05.
    reference = (_turn("A", 0.0, 10.0), _turn("B", 10.0, 20.0))
    hypothesis = (_turn("A", 0.0, 9.0), _turn("B", 9.0, 20.0))

    def test_mapping_is_identity_despite_the_shift(self):
        assert optimal_speaker_mapping(self.reference, self.hypothesis) == {"A": "A", "B": "B"}

    def test_der_no_collar_with_overlap(self):
        result = compute_der(self.reference, self.hypothesis, collar=0.0, skip_overlap=False)
        assert result.confusion_seconds == pytest.approx(1.0)
        assert result.missed_seconds == pytest.approx(0.0)
        assert result.false_alarm_seconds == pytest.approx(0.0)
        assert result.total_reference_seconds == pytest.approx(20.0)
        assert result.der == pytest.approx(1.0 / 20.0)

    def test_der_collar_ignoring_overlap(self):
        # Collar 0.25s around each reference boundary (0, 10, 20) further
        # slices the [9,10) confusion interval at 9.75: [9, 9.75) survives
        # (0.75s of confusion, not near any boundary), [9.75, 10.25) is
        # dropped by the collar around the boundary at 10. Surviving,
        # uncollared reference time: [0.25, 9) + [9, 9.75) + [10.25, 19.75)
        # = 8.75 + 0.75 + 9.5 = 19.0. DER = 0.75 / 19.0.
        result = compute_der(self.reference, self.hypothesis, collar=0.25, skip_overlap=True)
        assert result.confusion_seconds == pytest.approx(0.75)
        assert result.total_reference_seconds == pytest.approx(19.0)
        assert result.der == pytest.approx(0.75 / 19.0)


# ---------------------------------------------------------------------------
# fixture 3: label permutation (the optimal-mapping property itself)
# ---------------------------------------------------------------------------


class TestLabelPermutation:
    # Identical turns to the perfect-match fixture, but the hypothesis uses
    # entirely different speaker labels -- a naive same-label comparison
    # would show 100% mismatch; the optimal mapping must still find the
    # correspondence and score DER 0.
    reference = (_turn("A", 0.0, 10.0), _turn("B", 10.0, 20.0))
    hypothesis = (_turn("X", 0.0, 10.0), _turn("Y", 10.0, 20.0))

    def test_mapping_finds_the_permutation(self):
        assert optimal_speaker_mapping(self.reference, self.hypothesis) == {"A": "X", "B": "Y"}

    def test_der_is_zero_regardless_of_label_names(self):
        result = compute_der(self.reference, self.hypothesis)
        assert result.der == pytest.approx(0.0)

    def test_jer_is_zero_regardless_of_label_names(self):
        jer = compute_jer(self.reference, self.hypothesis)
        assert jer.jer == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# fixture 4: one missed speaker entirely
# ---------------------------------------------------------------------------


class TestOneMissedSpeaker:
    # hypothesis never produces speaker B at all: the second reference
    # half (10s) is entirely missed. DER = 10 / 20 = 0.5.
    reference = (_turn("A", 0.0, 10.0), _turn("B", 10.0, 20.0))
    hypothesis = (_turn("A", 0.0, 10.0),)

    def test_mapping_covers_only_the_matched_speaker(self):
        assert optimal_speaker_mapping(self.reference, self.hypothesis) == {"A": "A"}

    def test_der(self):
        result = compute_der(self.reference, self.hypothesis)
        assert result.missed_seconds == pytest.approx(10.0)
        assert result.false_alarm_seconds == pytest.approx(0.0)
        assert result.confusion_seconds == pytest.approx(0.0)
        assert result.der == pytest.approx(0.5)

    def test_jer(self):
        # speaker A: perfect (JER 0); speaker B: unmapped -> JER 1.0.
        # overall JER = (0 + 1) / 2 = 0.5.
        jer = compute_jer(self.reference, self.hypothesis)
        assert jer.per_speaker_jer["A"] == pytest.approx(0.0)
        assert jer.per_speaker_jer["B"] == pytest.approx(1.0)
        assert jer.jer == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# bonus: a false-alarm speaker (not in the required list, cheap to add)
# ---------------------------------------------------------------------------


class TestFalseAlarmSpeaker:
    # hypothesis hallucinates a second speaker after the reference ends:
    # 5s of pure false alarm against a 10s reference. DER = 5 / 10 = 0.5.
    reference = (_turn("A", 0.0, 10.0),)
    hypothesis = (_turn("A", 0.0, 10.0), _turn("B", 10.0, 15.0))

    def test_der(self):
        result = compute_der(self.reference, self.hypothesis)
        assert result.false_alarm_seconds == pytest.approx(5.0)
        assert result.missed_seconds == pytest.approx(0.0)
        assert result.confusion_seconds == pytest.approx(0.0)
        assert result.total_reference_seconds == pytest.approx(10.0)
        assert result.der == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# fixture 5: an overlap region, scored under BOTH registered conventions
# ---------------------------------------------------------------------------


class TestOverlapRegionBothConventions:
    # reference: A [0,10), B [5,15) -- true overlap in [5,10). The
    # hypothesis fails to reproduce the overlap: A [0,10), B [10,15) (B
    # starts 5s late, missing its first 5s entirely).
    #
    # no-collar-with-overlap: [0,5) correct; [5,10) ref has {A,B} but hyp
    # has only {A} -> 5s missed; [10,15) correct. total_ref = 5+10+5=20,
    # missed=5 -> DER = 5/20 = 0.25.
    #
    # collar=0.25, skip_overlap=True: skip_overlap drops the ENTIRE [5,10)
    # overlap interval outright (independent of collar), and the collar
    # additionally trims 0.25s around each of the 4 reference boundaries
    # (0, 5, 10, 15). What survives is [0.25,4.75) and [10.25,14.75),
    # both single-speaker and both perfectly correct -> DER = 0.
    reference = (_turn("A", 0.0, 10.0), _turn("B", 5.0, 15.0))
    hypothesis = (_turn("A", 0.0, 10.0), _turn("B", 10.0, 15.0))

    def test_no_collar_with_overlap(self):
        result = compute_der(self.reference, self.hypothesis, collar=0.0, skip_overlap=False)
        assert result.missed_seconds == pytest.approx(5.0)
        assert result.false_alarm_seconds == pytest.approx(0.0)
        assert result.confusion_seconds == pytest.approx(0.0)
        assert result.total_reference_seconds == pytest.approx(20.0)
        assert result.der == pytest.approx(0.25)

    def test_collar_ignoring_overlap(self):
        result = compute_der(self.reference, self.hypothesis, collar=0.25, skip_overlap=True)
        assert result.total_reference_seconds == pytest.approx(9.0)
        assert result.missed_seconds == pytest.approx(0.0)
        assert result.false_alarm_seconds == pytest.approx(0.0)
        assert result.confusion_seconds == pytest.approx(0.0)
        assert result.der == pytest.approx(0.0)

    def test_the_two_conventions_disagree_on_this_fixture(self):
        # The whole point of scoring both: an identical (reference,
        # hypothesis) pair produces two materially different DER numbers.
        no_collar = compute_der(self.reference, self.hypothesis, collar=0.0, skip_overlap=False)
        ignoring_overlap = compute_der(self.reference, self.hypothesis, collar=0.25, skip_overlap=True)
        assert no_collar.der != pytest.approx(ignoring_overlap.der)


# ---------------------------------------------------------------------------
# scored_intervals / speaker_set / validation
# ---------------------------------------------------------------------------


class TestValidationAndHelpers:
    def test_inverted_segment_raises(self):
        with pytest.raises(DiarizationScoringError):
            compute_der((_turn("A", 10.0, 5.0),), (_turn("A", 0.0, 5.0),))

    def test_empty_reference_or_hypothesis_yields_empty_mapping(self):
        assert optimal_speaker_mapping((), (_turn("A", 0.0, 5.0),)) == {}
        assert optimal_speaker_mapping((_turn("A", 0.0, 5.0),), ()) == {}

    def test_speaker_set_is_sorted_and_deduplicated(self):
        turns = (_turn("B", 0.0, 1.0), _turn("A", 1.0, 2.0), _turn("B", 2.0, 3.0))
        assert speaker_set(turns) == ("A", "B")

    def test_negative_collar_raises(self):
        with pytest.raises(DiarizationScoringError):
            scored_intervals((_turn("A", 0.0, 1.0),), (_turn("A", 0.0, 1.0),), collar=-1.0)

    def test_brute_force_guard_refuses_oversized_speaker_sets(self):
        big_ref = tuple(_turn(f"S{i}", float(i), float(i) + 1.0) for i in range(MAX_BRUTE_FORCE_SPEAKERS + 1))
        big_hyp = tuple(_turn(f"T{i}", float(i), float(i) + 1.0) for i in range(MAX_BRUTE_FORCE_SPEAKERS + 1))
        with pytest.raises(DiarizationScoringError):
            optimal_speaker_mapping(big_ref, big_hyp)


# ---------------------------------------------------------------------------
# pooling
# ---------------------------------------------------------------------------


class TestPoolDerBreakdowns:
    def test_pools_by_summing_components_then_dividing(self):
        # meeting 1: 5 error seconds / 20 total (0.25 DER); meeting 2:
        # 0 error seconds / 10 total (0.0 DER). A plain mean of the two DER
        # percentages would give 0.125; the correct duration-weighted pool
        # is 5 / 30 = 0.1666...
        b1 = compute_der(
            (_turn("A", 0.0, 10.0), _turn("B", 5.0, 15.0)),
            (_turn("A", 0.0, 10.0), _turn("B", 10.0, 15.0)),
        )
        b2 = compute_der((_turn("A", 0.0, 10.0),), (_turn("A", 0.0, 10.0),))
        pooled = pool_der_breakdowns([b1, b2])
        assert pooled.total_reference_seconds == pytest.approx(30.0)
        assert pooled.missed_seconds == pytest.approx(5.0)
        assert pooled.der == pytest.approx(5.0 / 30.0)
        naive_mean = (b1.der + b2.der) / 2
        assert pooled.der != pytest.approx(naive_mean)

    def test_empty_input_raises(self):
        with pytest.raises(DiarizationScoringError):
            pool_der_breakdowns([])

    def test_mismatched_conventions_raise(self):
        b1 = compute_der((_turn("A", 0.0, 10.0),), (_turn("A", 0.0, 10.0),), collar=0.0)
        b2 = compute_der((_turn("A", 0.0, 10.0),), (_turn("A", 0.0, 10.0),), collar=0.25)
        with pytest.raises(DiarizationScoringError):
            pool_der_breakdowns([b1, b2])
