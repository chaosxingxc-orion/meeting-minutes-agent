"""Tests for ``scripts/launch_diar_smoke.py``.

This engineering mission ONLY import-verifies and wiring-tests this script
(task scope: "no model runs, no downloads, no GPU, no installs") -- every
contact goes through a FAKE ``run_subprocess``/``query_gpu`` callable
(:class:`~meeting_minutes_agent.chunking.diarization.PinnedToolDiarization`'s
own injection seam), never a real tool binary or a real ``nvidia-smi``."""

from __future__ import annotations

import json
from pathlib import Path

import launch_diar_smoke as launcher
import pytest

from meeting_minutes_agent.chunking.diarization import ToolDiarizationConfig
from meeting_minutes_agent.chunking.rttm import write_rttm_text
from meeting_minutes_agent.chunking.slicer import TurnSpan
from meeting_minutes_agent.probes.diar_smoke import ARM_A, ARM_B, SmokeBudget, SmokeBudgetExceeded


def _config(tool_name="fake") -> ToolDiarizationConfig:
    return ToolDiarizationConfig(
        tool_name=tool_name,
        tool_version="1.0",
        checkpoint_sha256="a" * 64,
        command_template=("fake", "{audio_path}", "--output", "{rttm_path}"),
    )


class _FakeCompleted:
    def __init__(self, returncode=0, stderr=""):
        self.returncode = returncode
        self.stderr = stderr


def _write_fake_audio(data_dir: Path, meeting_id: str) -> None:
    from meeting_minutes_agent.probes.diar_smoke import resolve_meeting_audio_path

    audio_path = resolve_meeting_audio_path(meeting_id, data_dir=data_dir)
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"RIFF....WAVEfmt ")


def _success_run_subprocess(turns=(TurnSpan(0.0, 1.0, "A"),)):
    def run(args, *, timeout):
        (rttm_path,) = [a for a in args if a.endswith(".rttm")]
        Path(rttm_path).write_text(write_rttm_text(turns, file_id="MTG"), encoding="utf-8")
        return _FakeCompleted(returncode=0)

    return run


def _fake_gpu_snapshot():
    return {"utilization_gpu_pct": 10.0}


# ---------------------------------------------------------------------------
# import-verification
# ---------------------------------------------------------------------------


def test_module_imports_cleanly_without_side_effects():
    assert hasattr(launcher, "main")
    assert hasattr(launcher, "run_flight")


# ---------------------------------------------------------------------------
# run_one
# ---------------------------------------------------------------------------


class TestRunOne:
    def test_successful_contact_writes_a_receipt(self, tmp_path):
        data_dir = tmp_path / "data"
        out_dir = tmp_path / "out"
        _write_fake_audio(data_dir, "MTG1")
        budget = SmokeBudget()

        receipt = launcher.run_one(
            ARM_A,
            "MTG1",
            data_dir=data_dir,
            arm_configs={ARM_A: _config()},
            out_dir=out_dir,
            budget=budget,
            ami_audio_root_relative="datasets/ami/amicorpus",
            run_subprocess=_success_run_subprocess(),
            query_gpu=_fake_gpu_snapshot,
        )

        assert receipt["ok"] is True
        assert receipt["n_turns"] == 1
        assert receipt["arm"] == ARM_A
        assert receipt["meeting_id"] == "MTG1"
        assert len(receipt["contacts"]) == 1
        assert launcher.receipt_path(out_dir, ARM_A, "MTG1").is_file()
        on_disk = json.loads(launcher.receipt_path(out_dir, ARM_A, "MTG1").read_text(encoding="utf-8"))
        assert on_disk == receipt
        assert budget.wall_seconds_used >= 0.0

    def test_failed_contact_is_recorded_not_raised(self, tmp_path):
        data_dir = tmp_path / "data"
        out_dir = tmp_path / "out"
        _write_fake_audio(data_dir, "MTG1")

        def failing_run(args, *, timeout):
            return _FakeCompleted(returncode=1, stderr="boom")

        receipt = launcher.run_one(
            ARM_A, "MTG1", data_dir=data_dir, arm_configs={ARM_A: _config()}, out_dir=out_dir,
            budget=SmokeBudget(), ami_audio_root_relative="datasets/ami/amicorpus",
            run_subprocess=failing_run,
        )

        assert receipt["ok"] is False
        assert "boom" in receipt["error"]

    def test_missing_audio_raises_before_any_contact(self, tmp_path):
        data_dir = tmp_path / "data"  # no audio written
        with pytest.raises(FileNotFoundError):
            launcher.run_one(
                ARM_A, "MTG1", data_dir=data_dir, arm_configs={ARM_A: _config()}, out_dir=tmp_path / "out",
                budget=SmokeBudget(), ami_audio_root_relative="datasets/ami/amicorpus",
                run_subprocess=_success_run_subprocess(),
            )

    def test_budget_already_exceeded_raises_before_the_contact(self, tmp_path):
        data_dir = tmp_path / "data"
        _write_fake_audio(data_dir, "MTG1")
        budget = SmokeBudget(max_wall_seconds=1.0)
        budget.record(wall_seconds=1.0, gpu_seconds=0.0)

        with pytest.raises(SmokeBudgetExceeded):
            launcher.run_one(
                ARM_A, "MTG1", data_dir=data_dir, arm_configs={ARM_A: _config()}, out_dir=tmp_path / "out",
                budget=budget, ami_audio_root_relative="datasets/ami/amicorpus",
                run_subprocess=_success_run_subprocess(),
            )


# ---------------------------------------------------------------------------
# already_done / resume
# ---------------------------------------------------------------------------


class TestAlreadyDone:
    def test_false_when_no_receipt(self, tmp_path):
        assert launcher.already_done(tmp_path, ARM_A, "MTG1") is False

    def test_true_when_receipt_ok(self, tmp_path):
        path = launcher.receipt_path(tmp_path, ARM_A, "MTG1")
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"ok": True}), encoding="utf-8")
        assert launcher.already_done(tmp_path, ARM_A, "MTG1") is True

    def test_false_when_receipt_errored(self, tmp_path):
        path = launcher.receipt_path(tmp_path, ARM_A, "MTG1")
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"ok": False}), encoding="utf-8")
        assert launcher.already_done(tmp_path, ARM_A, "MTG1") is False

    def test_false_when_receipt_unparsable(self, tmp_path):
        path = launcher.receipt_path(tmp_path, ARM_A, "MTG1")
        path.parent.mkdir(parents=True)
        path.write_text("not json", encoding="utf-8")
        assert launcher.already_done(tmp_path, ARM_A, "MTG1") is False


# ---------------------------------------------------------------------------
# run_flight
# ---------------------------------------------------------------------------


class TestRunFlight:
    def test_runs_every_meeting_arm_pair(self, tmp_path):
        data_dir = tmp_path / "data"
        for meeting_id in ("MTG1", "MTG2"):
            _write_fake_audio(data_dir, meeting_id)
        arm_configs = {ARM_A: _config("a-tool"), ARM_B: _config("b-tool")}

        summary = launcher.run_flight(
            data_dir=data_dir,
            arm_configs=arm_configs,
            arms=[ARM_A, ARM_B],
            meetings=["MTG1", "MTG2"],
            out_dir=tmp_path / "out",
            resume=False,
            skip_registry_check=True,
            run_subprocess=_success_run_subprocess(),
            query_gpu=_fake_gpu_snapshot,
        )

        assert summary["n_ok"] == 4
        assert summary["n_error"] == 0
        assert summary["stopped_reason"] is None
        assert (tmp_path / "out" / "flight-summary.json").is_file()

    def test_resume_skips_already_ok_contacts(self, tmp_path):
        data_dir = tmp_path / "data"
        _write_fake_audio(data_dir, "MTG1")
        out_dir = tmp_path / "out"
        path = launcher.receipt_path(out_dir, ARM_A, "MTG1")
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"ok": True}), encoding="utf-8")

        run = _success_run_subprocess()
        calls_before = []

        def counting_run(args, *, timeout):
            calls_before.append(args)
            return run(args, timeout=timeout)

        summary = launcher.run_flight(
            data_dir=data_dir, arm_configs={ARM_A: _config()}, arms=[ARM_A], meetings=["MTG1"],
            out_dir=out_dir, resume=True, skip_registry_check=True, run_subprocess=counting_run,
        )

        assert calls_before == []  # never re-contacted
        assert summary["n_contacts"] == 0

    def test_budget_stop_writes_a_partial_summary(self, tmp_path):
        data_dir = tmp_path / "data"
        for meeting_id in ("MTG1", "MTG2"):
            _write_fake_audio(data_dir, meeting_id)

        summary = launcher.run_flight(
            data_dir=data_dir, arm_configs={ARM_A: _config()}, arms=[ARM_A], meetings=["MTG1", "MTG2"],
            out_dir=tmp_path / "out", resume=False, skip_registry_check=True,
            run_subprocess=_success_run_subprocess(), budget=SmokeBudget(max_wall_seconds=0.0),
        )

        assert summary["stopped_reason"] is not None
        assert summary["n_contacts"] == 0
        assert (tmp_path / "out" / "flight-summary.json").is_file()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestMainCli:
    def test_summary_only_prints_the_registered_roster(self, capsys):
        rc = launcher.main(["--data-dir", "unused", "--summary-only"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert len(payload["meetings"]) == 6
        assert payload["required_arms"] == ["A", "B"]

    def test_missing_required_args_without_summary_only_errors(self):
        with pytest.raises(SystemExit):
            launcher.main(["--data-dir", "unused"])

    def test_arm_c_without_include_flag_errors(self, tmp_path):
        with pytest.raises(SystemExit):
            launcher.main(["--data-dir", "unused", "--arms", "A", "C"])
