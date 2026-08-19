"""Tests for ``scripts/run_precomp.py``.

This engineering mission ONLY import-verifies and wiring-tests this script
(task scope: "MACHINERY ONLY -- no diar runs, no core contact, no
downloads") -- every diar contact goes through a FAKE ``run_subprocess``
and every frozen-core contact goes through a FAKE transport ``post``
(the same injection seams ``tests/unit/scripts/test_launch_diar_smoke.py``
and ``tests/unit/scripts/test_launch_pattr_smoke.py`` already use), never a
real tool binary, a real GPU, or a real network call."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import run_precomp as launcher
import soundfile as sf

from meeting_minutes_agent.chunking.diarization import ToolDiarizationConfig
from meeting_minutes_agent.chunking.rttm import write_rttm_text
from meeting_minutes_agent.chunking.slicer import TurnSpan
from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget
from meeting_minutes_agent.client.receipts import FlightReceipt, ModelFileRef, ServerIdentity
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig
from meeting_minutes_agent.corpora.nxt.corpus import NxtCorpus
from meeting_minutes_agent.corpora.roles import HeldOutLeakageError
from meeting_minutes_agent.precomp.budget import PrecompBudget, WaveCeilings
from meeting_minutes_agent.probes.diar_smoke import ArmConfigError

_NITE_XMLNS = 'xmlns:nite="http://nite.sourceforge.net/"'
_XML_HEADER = '<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>\n'


# ---------------------------------------------------------------------------
# import-verification
# ---------------------------------------------------------------------------


def test_module_imports_cleanly_without_side_effects():
    assert hasattr(launcher, "main")
    assert hasattr(launcher, "run_wave")
    assert hasattr(launcher, "build_transport")


def test_help_does_not_run_a_wave(capsys):
    with pytest.raises(SystemExit) as excinfo:
        launcher.main(["--help"])
    assert excinfo.value.code == 0


# ---------------------------------------------------------------------------
# --summary-only: safe to run right now, no diar/server contact
# ---------------------------------------------------------------------------


class TestSummaryOnly:
    def test_wave_1_reports_the_registered_dev18_roster_and_ceilings(self, capsys):
        rc = launcher.main(["--wave", "1", "--data-dir", "unused", "--summary-only"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["n_meetings"] == 18
        assert payload["ceilings"]["max_encode_calls"] == 900
        assert payload["ceilings"]["max_cutting_wall_hours"] == 2.0

    def test_wave_2_reports_a_nonempty_roster_and_its_own_ceilings(self, capsys):
        rc = launcher.main(["--wave", "2", "--data-dir", "unused", "--summary-only"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["n_meetings"] > 0
        assert payload["ceilings"]["max_encode_calls"] == 4500
        assert payload["ceilings"]["max_cutting_wall_hours"] is None

    def test_meetings_override_is_still_passed_through_the_exposure_gate(self, capsys):
        rc = launcher.main(["--wave", "1", "--data-dir", "unused", "--meetings", "ES2011a", "--summary-only"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["meetings"] == ["ES2011a"]

    def test_an_eval_16_meetings_override_is_refused(self):
        with pytest.raises(HeldOutLeakageError):
            launcher.main(["--wave", "1", "--data-dir", "unused", "--meetings", "ES2004a", "--summary-only"])

    def test_unknown_wave_is_rejected_by_argparse(self):
        with pytest.raises(SystemExit):
            launcher.main(["--wave", "3", "--data-dir", "unused", "--summary-only"])


# ---------------------------------------------------------------------------
# required-args gate for a real wave
# ---------------------------------------------------------------------------


def test_missing_required_args_without_summary_only_errors_cleanly():
    with pytest.raises(SystemExit) as excinfo:
        launcher.main(["--wave", "1", "--data-dir", "unused"])
    assert excinfo.value.code != 0


# ---------------------------------------------------------------------------
# load_arm_b_config
# ---------------------------------------------------------------------------


class TestLoadArmBConfig:
    def test_loads_the_b_entry(self, tmp_path):
        path = tmp_path / "arm-config.json"
        path.write_text(
            json.dumps({"B": {"tool_name": "nemo-speech.cpp-cuda-q8_0", "tool_version": "1.0.0", "checkpoint_sha256": "0" * 64, "command_template": ["nemo-speech", "{audio_path}"]}}),
            encoding="utf-8",
        )
        cfg = launcher.load_arm_b_config(path)
        assert isinstance(cfg, ToolDiarizationConfig)
        assert cfg.tool_name == "nemo-speech.cpp-cuda-q8_0"

    def test_missing_b_key_raises(self, tmp_path):
        path = tmp_path / "arm-config.json"
        path.write_text(json.dumps({"A": {}}), encoding="utf-8")
        with pytest.raises(ArmConfigError):
            launcher.load_arm_b_config(path)

    def test_non_object_document_raises(self, tmp_path):
        path = tmp_path / "arm-config.json"
        path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
        with pytest.raises(ArmConfigError):
            launcher.load_arm_b_config(path)


# ---------------------------------------------------------------------------
# default_out_dir
# ---------------------------------------------------------------------------


def test_default_out_dir_names_the_conventional_docs_checks_path():
    out_dir = launcher.default_out_dir(1)
    assert out_dir.name == "2026-08-19-precomp-wave1"
    assert out_dir.parent.name == "checks"


# ---------------------------------------------------------------------------
# run_wave: real per-meeting wiring, fake diar subprocess + fake transport
# ---------------------------------------------------------------------------


def _write_nxt(root: Path, meeting_id: str) -> None:
    def write(subdir: str, name: str, content: str) -> None:
        path = root / subdir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_XML_HEADER + content, encoding="utf-8")

    write(
        "words",
        f"{meeting_id}.A.words.xml",
        f"""<nite:root nite:id="{meeting_id}.A.words" {_NITE_XMLNS}>
   <w nite:id="{meeting_id}.A.words0" starttime="0.0" endtime="1.8">Hello</w>
</nite:root>
""",
    )
    write(
        "segments",
        f"{meeting_id}.A.segments.xml",
        f"""<nite:root nite:id="{meeting_id}.A.segs" {_NITE_XMLNS}>
   <segment nite:id="{meeting_id}.A.seg.1" channel="0" transcriber_start="0.0" transcriber_end="1.8">
      <nite:child href="{meeting_id}.A.words.xml#id({meeting_id}.A.words0)..id({meeting_id}.A.words0)"/>
   </segment>
</nite:root>
""",
    )


def _write_synth_wav(path: Path, duration_s: float = 3.0, *, sr: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(round(duration_s * sr))
    t = np.arange(n) / sr
    y = 0.2 * np.sin(2 * np.pi * 220.0 * t).astype(np.float32)
    sf.write(str(path), y, sr, subtype="PCM_16")


def _rttm_writer():
    def run(args, *, timeout):
        (rttm_path,) = [a for a in args if a.endswith(".rttm")]
        Path(rttm_path).write_text(write_rttm_text((TurnSpan(0.0, 1.8, "spk1"),), file_id="MTG"), encoding="utf-8")

        class _Completed:
            returncode = 0
            stderr = ""

        return _Completed()

    return run


def _canned_post():
    def post(url, body):
        return json.dumps(
            {"choices": [{"message": {"content": "warm"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6}}
        ).encode("utf-8")

    return post


def _tool_config() -> ToolDiarizationConfig:
    return ToolDiarizationConfig(
        tool_name="fake-nemo-speech-b", tool_version="1.0", checkpoint_sha256="b" * 64,
        command_template=("fake-diar", "{audio_path}", "--output", "{rttm_path}"),
    )


def _wave_fixture(tmp_path: Path, meeting_ids: list[str]):
    data_dir = tmp_path / "data"
    ami_audio_root = "datasets/ami/amicorpus"
    for meeting_id in meeting_ids:
        _write_nxt(data_dir / "datasets/ami/annotations/manual_1.6.2", meeting_id)
        _write_synth_wav(data_dir / ami_audio_root / meeting_id / "audio" / f"{meeting_id}.Mix-Headset.wav")

    call_budget = CallBudget(BudgetLimits(max_calls=1000, max_audio_seconds=100_000.0))
    transport = LlamaServerTransport(TransportConfig(base_url="http://x"), call_budget, post=_canned_post())
    server_identity = ServerIdentity(base_url="http://x", model_files=(ModelFileRef(path="m.gguf", sha256="a" * 64),))
    flight_receipt = FlightReceipt(server_identity, call_budget)
    return {"data_dir": data_dir, "transport": transport, "flight_receipt": flight_receipt}


class TestRunWave:
    def test_runs_every_meeting_and_writes_a_wave_summary(self, tmp_path):
        fx = _wave_fixture(tmp_path, ["MTG1", "MTG2"])
        out_dir = tmp_path / "out"
        budget = PrecompBudget(WaveCeilings(wave=1, max_diar_gpu_hours=1.0, max_encode_gpu_hours=1.0, max_cutting_wall_hours=1.0, max_encode_calls=100))

        summary = launcher.run_wave(
            wave=1,
            data_dir=fx["data_dir"],
            meetings=["MTG1", "MTG2"],
            tool_config=_tool_config(),
            transport=fx["transport"],
            out_dir=out_dir,
            derived_root=tmp_path / "derived",
            cache_dir=tmp_path / "cache",
            resume=False,
            skip_roster_check=True,
            run_subprocess=_rttm_writer(),
            budget=budget,
        )

        assert summary["n_meetings"] == 2
        assert summary["n_ok"] == 2
        assert (out_dir / "wave-summary.json").is_file()
        assert (out_dir / "receipts" / "MTG1-receipt.json").is_file()
        assert (out_dir / "receipts" / "MTG2-receipt.json").is_file()

    def test_resume_skips_an_already_ok_meeting(self, tmp_path):
        fx = _wave_fixture(tmp_path, ["MTG1"])
        out_dir = tmp_path / "out"
        (out_dir / "receipts").mkdir(parents=True)
        (out_dir / "receipts" / "MTG1-receipt.json").write_text(
            json.dumps({"schema_version": "1.0.0", "ok": True}), encoding="utf-8"
        )
        calls: list = []

        def tracking_run(args, *, timeout):
            calls.append(args)
            return _rttm_writer()(args, timeout=timeout)

        summary = launcher.run_wave(
            wave=1,
            data_dir=fx["data_dir"],
            meetings=["MTG1"],
            tool_config=_tool_config(),
            transport=fx["transport"],
            out_dir=out_dir,
            derived_root=tmp_path / "derived",
            cache_dir=tmp_path / "cache",
            resume=True,
            skip_roster_check=True,
            run_subprocess=tracking_run,
        )

        assert calls == []  # never re-contacted
        assert summary["n_meetings"] == 0

    def test_budget_stop_writes_a_partial_summary(self, tmp_path):
        fx = _wave_fixture(tmp_path, ["MTG1", "MTG2"])
        out_dir = tmp_path / "out"
        budget = PrecompBudget(WaveCeilings(wave=1, max_diar_gpu_hours=0.0, max_encode_gpu_hours=1.0, max_cutting_wall_hours=1.0, max_encode_calls=100))

        summary = launcher.run_wave(
            wave=1,
            data_dir=fx["data_dir"],
            meetings=["MTG1", "MTG2"],
            tool_config=_tool_config(),
            transport=fx["transport"],
            out_dir=out_dir,
            derived_root=tmp_path / "derived",
            cache_dir=tmp_path / "cache",
            resume=False,
            skip_roster_check=True,
            run_subprocess=_rttm_writer(),
            budget=budget,
        )

        assert summary["stopped_reason"] is not None
        assert summary["n_meetings"] == 0
        assert (out_dir / "wave-summary.json").is_file()

    def test_roster_check_refuses_a_bad_meeting_by_default(self, tmp_path):
        fx = _wave_fixture(tmp_path, ["MTG1"])
        with pytest.raises(Exception):  # UnknownMeetingError from the real registry
            launcher.run_wave(
                wave=1,
                data_dir=fx["data_dir"],
                meetings=["MTG1"],
                tool_config=_tool_config(),
                transport=fx["transport"],
                out_dir=tmp_path / "out",
                derived_root=tmp_path / "derived",
                cache_dir=tmp_path / "cache",
                resume=False,
                run_subprocess=_rttm_writer(),
            )


# ---------------------------------------------------------------------------
# ceilings_for_wave sanity (imported indirectly through main's --wave choices)
# ---------------------------------------------------------------------------


def test_wave_argument_only_accepts_registered_waves():
    with pytest.raises(SystemExit):
        launcher.main(["--wave", "0", "--data-dir", "unused", "--summary-only"])
