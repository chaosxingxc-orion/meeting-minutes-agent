"""Tests for :mod:`meeting_minutes_agent.chunking.diarization`: the
DiarizationBackend seam -- :class:`NxtOracleDiarization` (wraps the existing
NXT gold-turn path, tagged oracle) and :class:`PinnedToolDiarization` (an
honest not-yet-pinned stub) -- plus the two turn-aware-slice-plan
orchestration functions that thread a backend into :mod:`.slicer` instead of
the old direct-to-NXT wiring."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.chunking.diarization import (
    DiarizationBackend,
    DiarizationResult,
    DiarizationToolNotPinnedError,
    NxtOracleDiarization,
    PinnedToolDiarization,
    build_turn_aware_slice_plan_for_resolved_meeting,
    build_turn_aware_slice_plan_from_backend,
)
from meeting_minutes_agent.chunking.leakage import (
    BoundaryLeakageTier,
    BoundaryLeakageTierViolation,
    BoundaryProvenance,
    tier_of,
)
from meeting_minutes_agent.chunking.slicer import SlicePlanMode, TurnSpan
from meeting_minutes_agent.corpora.nxt.models import ResolvedMeeting, Utterance


def _utterance(id_: str, speaker: str, start: float, end: float, text: str) -> Utterance:
    return Utterance(id=id_, speaker=speaker, start=start, end=end, text=text, word_ids=())


def _resolved_meeting(meeting_id: str, transcript: tuple[Utterance, ...]) -> ResolvedMeeting:
    return ResolvedMeeting(
        meeting_id=meeting_id,
        transcript=transcript,
        dialogue_acts=(),
        minutes=None,
        evidence_links=(),
        topics=(),
        orphans=(),
    )


_TRANSCRIPT = (
    _utterance("u0", "A", 0.0, 40.0, "first turn"),
    _utterance("u1", "B", 40.0, 80.0, "second turn"),
    _utterance("u2", "A", 80.0, 120.0, "third turn"),
)


# ---------------------------------------------------------------------------
# DiarizationBackend is an ABC
# ---------------------------------------------------------------------------


def test_diarization_backend_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        DiarizationBackend()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# NxtOracleDiarization: wraps the NXT gold-turn path, tagged oracle
# ---------------------------------------------------------------------------


class TestNxtOracleDiarizationSingleMeeting:
    def test_diarize_returns_the_gold_turn_table(self):
        resolved = _resolved_meeting("M1", _TRANSCRIPT)
        backend = NxtOracleDiarization(resolved)

        result = backend.diarize("M1", audio_ref=None)

        assert isinstance(result, DiarizationResult)
        assert result.turns == (
            TurnSpan(0.0, 40.0, "A"),
            TurnSpan(40.0, 80.0, "B"),
            TurnSpan(80.0, 120.0, "A"),
        )

    def test_provenance_is_oracle_turn_tier_m1(self):
        # The M0/M1 boundary-provenance gate registration this task calls
        # out explicitly: the tag a caller downstream (build_turn_aware_
        # slice_plan's own assert_runtime_admissible gate) will see.
        resolved = _resolved_meeting("M1", _TRANSCRIPT)
        backend = NxtOracleDiarization(resolved)

        result = backend.diarize("M1")

        assert result.provenance is BoundaryProvenance.ORACLE_TURN
        assert tier_of(result.provenance) is BoundaryLeakageTier.M1

    def test_audio_ref_is_ignored(self):
        # The oracle backend is keyed on meeting_id alone -- audio_ref (a
        # real tool backend's input) has no bearing on the gold layer.
        resolved = _resolved_meeting("M1", _TRANSCRIPT)
        backend = NxtOracleDiarization(resolved)

        assert backend.diarize("M1", audio_ref="/some/path.wav") == backend.diarize("M1", audio_ref=None)

    def test_mismatched_meeting_id_raises(self):
        resolved = _resolved_meeting("M1", _TRANSCRIPT)
        backend = NxtOracleDiarization(resolved)

        with pytest.raises(KeyError, match="M1"):
            backend.diarize("M2")


class TestNxtOracleDiarizationMultiMeeting:
    def test_accepts_a_mapping_of_meeting_id_to_resolved_meeting(self):
        m1 = _resolved_meeting("M1", _TRANSCRIPT)
        m2 = _resolved_meeting("M2", (_utterance("v0", "C", 0.0, 10.0, "solo"),))
        backend = NxtOracleDiarization({"M1": m1, "M2": m2})

        assert backend.diarize("M2").turns == (TurnSpan(0.0, 10.0, "C"),)

    def test_mapping_missing_meeting_id_raises_key_error(self):
        backend = NxtOracleDiarization({})
        with pytest.raises(KeyError, match="M9"):
            backend.diarize("M9")

    def test_accepts_a_resolver_callable(self):
        registry = {"M1": _resolved_meeting("M1", _TRANSCRIPT)}
        backend = NxtOracleDiarization(lambda meeting_id: registry[meeting_id])

        assert len(backend.diarize("M1").turns) == 3


# ---------------------------------------------------------------------------
# PinnedToolDiarization: honest stub, names the not-yet-pinned ticket
# ---------------------------------------------------------------------------


class TestPinnedToolDiarization:
    def test_diarize_raises_naming_the_tool_selection_ticket(self):
        backend = PinnedToolDiarization()
        with pytest.raises(
            DiarizationToolNotPinnedError,
            match="docs/plans/2026-08-18-diarization-tool-selection.md",
        ):
            backend.diarize("M1", audio_ref="/some/meeting.wav")

    def test_is_a_diarization_backend(self):
        assert isinstance(PinnedToolDiarization(), DiarizationBackend)

    def test_error_names_the_meeting_id(self):
        backend = PinnedToolDiarization()
        with pytest.raises(DiarizationToolNotPinnedError, match="M42"):
            backend.diarize("M42", audio_ref=None)


# ---------------------------------------------------------------------------
# build_turn_aware_slice_plan_from_backend: the generic seam-threading entry
# point -- the oracle tag stays visible to the M0/M1 gate, never bypassed
# ---------------------------------------------------------------------------


class _FakeBackend(DiarizationBackend):
    def __init__(self, turns, provenance):
        self._turns = turns
        self._provenance = provenance
        self.calls: list[tuple[str, object]] = []

    def diarize(self, meeting_id, audio_ref=None):
        self.calls.append((meeting_id, audio_ref))
        return DiarizationResult(turns=self._turns, provenance=self._provenance)


class TestBuildTurnAwareSlicePlanFromBackend:
    def test_builds_a_turn_aware_plan_over_the_backends_turns(self):
        backend = _FakeBackend((TurnSpan(0.0, 100.0, "A"),), BoundaryProvenance.TOOL_DIAR)

        plan = build_turn_aware_slice_plan_from_backend(
            "m1", "/audio/m1.wav", backend=backend, total_duration_s=100.0
        )

        assert plan.mode is SlicePlanMode.TURN_AWARE
        assert plan.turn_provenance is BoundaryProvenance.TOOL_DIAR
        assert backend.calls == [("m1", "/audio/m1.wav")]

    def test_oracle_provenance_is_refused_without_allow_oracle_turns(self):
        # The gate-registration claim made explicit: an oracle-tagged
        # DiarizationResult reaching the slicer through this seam is caught
        # by the EXACT SAME assert_runtime_admissible gate as the old
        # direct-to-NXT wiring -- the seam never bypasses it.
        backend = _FakeBackend((TurnSpan(0.0, 100.0, "A"),), BoundaryProvenance.ORACLE_TURN)

        with pytest.raises(BoundaryLeakageTierViolation):
            build_turn_aware_slice_plan_from_backend("m1", None, backend=backend, total_duration_s=100.0)

    def test_oracle_provenance_is_admitted_with_explicit_opt_in(self):
        backend = _FakeBackend((TurnSpan(0.0, 100.0, "A"),), BoundaryProvenance.ORACLE_TURN)

        plan = build_turn_aware_slice_plan_from_backend(
            "m1", None, backend=backend, allow_oracle_turns=True, total_duration_s=100.0
        )

        assert plan.turn_provenance is BoundaryProvenance.ORACLE_TURN


# ---------------------------------------------------------------------------
# build_turn_aware_slice_plan_for_resolved_meeting: NXT convenience wrapper
# -- default backend is the oracle one, so old behaviour is unchanged
# ---------------------------------------------------------------------------


class TestBuildTurnAwareSlicePlanForResolvedMeeting:
    def test_default_backend_is_oracle_and_gated_the_same_way(self):
        resolved = _resolved_meeting("M1", _TRANSCRIPT)

        with pytest.raises(BoundaryLeakageTierViolation):
            build_turn_aware_slice_plan_for_resolved_meeting(resolved)

    def test_default_backend_produces_the_gold_turn_plan_when_admitted(self):
        resolved = _resolved_meeting("M1", _TRANSCRIPT)

        plan = build_turn_aware_slice_plan_for_resolved_meeting(resolved, allow_oracle_turns=True)

        assert plan.turn_provenance is BoundaryProvenance.ORACLE_TURN
        assert plan.meeting_id == "M1"
        assert plan.slices  # the 3 gold turns packed into >=1 transport slice

    def test_an_explicit_backend_overrides_the_oracle_default(self):
        resolved = _resolved_meeting("M1", _TRANSCRIPT)
        backend = _FakeBackend((TurnSpan(0.0, 90.0, "X"),), BoundaryProvenance.TOOL_DIAR)

        plan = build_turn_aware_slice_plan_for_resolved_meeting(resolved, backend=backend)

        assert plan.turn_provenance is BoundaryProvenance.TOOL_DIAR
        assert backend.calls == [("M1", None)]
