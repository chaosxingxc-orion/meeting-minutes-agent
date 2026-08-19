"""Tests for :mod:`meeting_minutes_agent.chunking.diarization`: the
DiarizationBackend seam -- :class:`NxtOracleDiarization` (wraps the existing
NXT gold-turn path, tagged oracle) and :class:`PinnedToolDiarization` (the
real, subprocess-driven pinned-tool backend, DIAR-SMOKE) -- plus the two
turn-aware-slice-plan orchestration functions that thread a backend into
:mod:`.slicer` instead of the old direct-to-NXT wiring."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from meeting_minutes_agent.chunking.diarization import (
    DiarizationBackend,
    DiarizationResult,
    DiarizationToolNotPinnedError,
    NxtOracleDiarization,
    PinnedToolDiarization,
    ToolContactRecord,
    ToolDiarizationConfig,
    ToolDiarizationInvocationError,
    build_turn_aware_slice_plan_for_resolved_meeting,
    build_turn_aware_slice_plan_from_backend,
)
from meeting_minutes_agent.chunking.leakage import (
    BoundaryLeakageTier,
    BoundaryLeakageTierViolation,
    BoundaryProvenance,
    tier_of,
)
from meeting_minutes_agent.chunking.rttm import write_rttm_text
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
# PinnedToolDiarization: the real subprocess-driven pinned-tool backend
# ---------------------------------------------------------------------------


def _config(**overrides) -> ToolDiarizationConfig:
    defaults = dict(
        tool_name="fake-diarizer",
        tool_version="1.2.3",
        checkpoint_sha256="a" * 64,
        command_template=("fake-diarizer", "diarize", "{audio_path}", "--output", "{rttm_path}"),
    )
    defaults.update(overrides)
    return ToolDiarizationConfig(**defaults)


class _FakeCompleted:
    def __init__(self, returncode: int, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr


def _rttm_arg(args):
    (path,) = [a for a in args if a.endswith(".rttm")]
    return path


def _make_successful_run_subprocess(turns):
    """A fake ``run_subprocess`` that writes RTTM output for the requested
    meeting and reports success -- never touches a real binary."""

    calls = []

    def run(args, *, timeout):
        calls.append((tuple(args), timeout))
        Path(_rttm_arg(args)).write_text(write_rttm_text(turns, file_id="MTG"), encoding="utf-8")
        return _FakeCompleted(returncode=0)

    run.calls = calls
    return run


class TestPinnedToolDiarizationSuccess:
    def test_diarize_returns_turns_parsed_from_the_written_rttm(self, tmp_path):
        turns = (TurnSpan(0.0, 5.0, "A"), TurnSpan(5.0, 10.0, "B"))
        backend = PinnedToolDiarization(_config(), output_dir=tmp_path, run_subprocess=_make_successful_run_subprocess(turns))

        result = backend.diarize("M1", tmp_path / "M1.wav")

        assert isinstance(result, DiarizationResult)
        assert result.turns == turns
        assert result.provenance is BoundaryProvenance.TOOL_DIAR
        assert tier_of(result.provenance) is BoundaryLeakageTier.M0

    def test_is_a_diarization_backend(self, tmp_path):
        assert isinstance(PinnedToolDiarization(_config(), output_dir=tmp_path), DiarizationBackend)

    def test_command_template_is_substituted_with_audio_and_rttm_paths(self, tmp_path):
        run = _make_successful_run_subprocess(())
        backend = PinnedToolDiarization(_config(), output_dir=tmp_path, run_subprocess=run)

        backend.diarize("M1", tmp_path / "M1.wav")

        (args, timeout) = run.calls[0]
        assert args[0] == "fake-diarizer"
        assert str(tmp_path / "M1.wav") in args
        assert str(tmp_path / "M1.rttm") in args
        assert timeout == _config().timeout_seconds

    def test_extra_args_are_appended_and_substituted(self, tmp_path):
        run = _make_successful_run_subprocess(())
        backend = PinnedToolDiarization(
            _config(extra_args=("--meeting", "{meeting_id}")), output_dir=tmp_path, run_subprocess=run
        )

        backend.diarize("M1", tmp_path / "M1.wav")

        (args, _timeout) = run.calls[0]
        assert args[-2:] == ("--meeting", "M1")

    def test_audio_ref_none_raises_without_any_contact(self, tmp_path):
        run = _make_successful_run_subprocess(())
        backend = PinnedToolDiarization(_config(), output_dir=tmp_path, run_subprocess=run)

        with pytest.raises(ValueError, match="audio_ref"):
            backend.diarize("M1", None)
        assert run.calls == []
        assert backend.contact_log == ()


class TestPinnedToolDiarizationContactLogging:
    """Frozen-tool per-contact logging rule: EVERY contact -- success,
    non-zero exit, missing RTTM, or a raised subprocess exception -- writes
    exactly one :class:`ToolContactRecord` before/around any exception."""

    def test_successful_contact_is_logged(self, tmp_path):
        turns = (TurnSpan(0.0, 1.0, "A"),)
        cfg = _config()
        backend = PinnedToolDiarization(cfg, output_dir=tmp_path, run_subprocess=_make_successful_run_subprocess(turns))

        backend.diarize("M1", tmp_path / "M1.wav")

        assert len(backend.contact_log) == 1
        record = backend.contact_log[0]
        assert isinstance(record, ToolContactRecord)
        assert record.tool_name == cfg.tool_name
        assert record.tool_version == cfg.tool_version
        assert record.checkpoint_sha256 == cfg.checkpoint_sha256
        assert record.meeting_id == "M1"
        assert record.return_code == 0
        assert record.error is None
        assert record.wall_seconds >= 0.0
        assert record.recorded_utc

    def test_on_contact_callback_receives_the_same_record(self, tmp_path):
        received = []
        backend = PinnedToolDiarization(
            _config(), output_dir=tmp_path, run_subprocess=_make_successful_run_subprocess(()),
            on_contact=received.append,
        )

        backend.diarize("M1", tmp_path / "M1.wav")

        assert received == list(backend.contact_log)

    def test_nonzero_return_code_is_logged_then_raises(self, tmp_path):
        def run(args, *, timeout):
            return _FakeCompleted(returncode=1, stderr="boom")

        backend = PinnedToolDiarization(_config(), output_dir=tmp_path, run_subprocess=run)

        with pytest.raises(ToolDiarizationInvocationError, match="exited 1"):
            backend.diarize("M1", tmp_path / "M1.wav")

        assert len(backend.contact_log) == 1
        record = backend.contact_log[0]
        assert record.return_code == 1
        assert record.error == "boom"

    def test_missing_rttm_after_success_is_logged_then_raises(self, tmp_path):
        def run(args, *, timeout):
            return _FakeCompleted(returncode=0)  # never writes the RTTM file

        backend = PinnedToolDiarization(_config(), output_dir=tmp_path, run_subprocess=run)

        with pytest.raises(ToolDiarizationInvocationError, match="wrote no RTTM"):
            backend.diarize("M1", tmp_path / "M1.wav")

        record = backend.contact_log[0]
        assert record.return_code == 0
        assert record.error is None  # the subprocess itself "succeeded"

    def test_subprocess_launch_exception_is_logged_then_raises(self, tmp_path):
        def run(args, *, timeout):
            raise FileNotFoundError("no such binary: fake-diarizer")

        backend = PinnedToolDiarization(_config(), output_dir=tmp_path, run_subprocess=run)

        with pytest.raises(ToolDiarizationInvocationError, match="invocation failed"):
            backend.diarize("M1", tmp_path / "M1.wav")

        record = backend.contact_log[0]
        assert record.return_code is None
        assert "FileNotFoundError" in record.error

    def test_timeout_exception_is_logged_then_raises(self, tmp_path):
        def run(args, *, timeout):
            raise subprocess.TimeoutExpired(cmd="fake-diarizer", timeout=timeout)

        backend = PinnedToolDiarization(_config(timeout_seconds=5.0), output_dir=tmp_path, run_subprocess=run)

        with pytest.raises(ToolDiarizationInvocationError):
            backend.diarize("M1", tmp_path / "M1.wav")

        assert backend.contact_log[0].return_code is None

    def test_multiple_contacts_all_append_to_the_log(self, tmp_path):
        run = _make_successful_run_subprocess((TurnSpan(0.0, 1.0, "A"),))
        backend = PinnedToolDiarization(_config(), output_dir=tmp_path, run_subprocess=run)

        backend.diarize("M1", tmp_path / "M1.wav")
        backend.diarize("M2", tmp_path / "M2.wav")

        assert [r.meeting_id for r in backend.contact_log] == ["M1", "M2"]


class TestToolDiarizationConfigValidation:
    def test_bad_checkpoint_sha256_raises(self):
        with pytest.raises(ValueError, match="sha256"):
            _config(checkpoint_sha256="not-a-hash").validate()

    def test_empty_command_template_raises(self):
        with pytest.raises(ValueError, match="command_template"):
            _config(command_template=()).validate()

    def test_from_dict_round_trips_to_dict(self):
        cfg = _config(extra_args=("--offline",))
        assert ToolDiarizationConfig.from_dict(cfg.to_dict()) == cfg

    def test_from_dict_defaults_extra_args_and_timeout(self):
        raw = {
            "tool_name": "t",
            "tool_version": "1",
            "checkpoint_sha256": "b" * 64,
            "command_template": ["t", "{audio_path}", "{rttm_path}"],
        }
        cfg = ToolDiarizationConfig.from_dict(raw)
        assert cfg.extra_args == ()
        assert cfg.timeout_seconds == 3600.0


class TestDiarizationToolNotPinnedErrorStillDefined:
    """Historical exception class: no longer raised by
    :class:`PinnedToolDiarization` itself, but still exported for any
    existing importer (module docstring)."""

    def test_is_a_not_implemented_error(self):
        assert issubclass(DiarizationToolNotPinnedError, NotImplementedError)


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
