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
from meeting_minutes_agent.client.featcache import campaign_cache_dir
from meeting_minutes_agent.precomp.budget import G1_SUPPLEMENT_CEILINGS, PrecompBudget, WaveCeilings, ceilings_for_wave
from meeting_minutes_agent.precomp.receipts import build_meeting_receipt
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
# --turn-sources / --ceilings-profile: the G1 VAD-supplement extension
# (docs/readiness/2026-08-19-g1-floors-preregistration.md SS3/SS6)
# ---------------------------------------------------------------------------


class TestTurnSourcesAndCeilingsProfileFlags:
    def test_turn_sources_defaults_to_tool_and_oracle(self, capsys):
        rc = launcher.main(["--wave", "1", "--data-dir", "unused", "--summary-only"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["turn_sources"] == ["tool", "oracle"]
        assert payload["ceilings_profile"] == "wave-1"

    def test_turn_sources_vad_is_accepted(self, capsys):
        rc = launcher.main(["--wave", "1", "--data-dir", "unused", "--turn-sources", "vad", "--summary-only"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["turn_sources"] == ["vad"]

    def test_unknown_turn_source_is_rejected_by_argparse(self):
        with pytest.raises(SystemExit):
            launcher.main(["--wave", "1", "--data-dir", "unused", "--turn-sources", "bogus", "--summary-only"])

    def test_ceilings_profile_g1_supplement_overrides_the_wave_derived_default(self, capsys):
        rc = launcher.main(
            ["--wave", "1", "--data-dir", "unused", "--ceilings-profile", "g1-supplement", "--summary-only"]
        )
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["ceilings_profile"] == "g1-supplement"
        assert payload["ceilings"] == G1_SUPPLEMENT_CEILINGS.to_dict()
        assert payload["ceilings"]["max_encode_calls"] == 500
        # never wave-1's own, already-738/900-spent ceiling
        assert payload["ceilings"]["max_encode_calls"] != ceilings_for_wave(1).max_encode_calls

    def test_unknown_ceilings_profile_is_rejected_by_argparse(self):
        with pytest.raises(SystemExit):
            launcher.main(["--wave", "1", "--data-dir", "unused", "--ceilings-profile", "bogus", "--summary-only"])

    def test_meetings_roster_is_unaffected_by_ceilings_profile(self, capsys):
        # The g1-supplement ceilings profile still rides wave-1's own dev-18
        # roster (registered: "over dev-18") -- only the CEILINGS differ.
        rc = launcher.main(
            ["--wave", "1", "--data-dir", "unused", "--ceilings-profile", "g1-supplement", "--summary-only"]
        )
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["n_meetings"] == 18


class TestMissingRequiredArgs:
    def test_arm_config_required_when_tool_is_among_turn_sources(self):
        missing = launcher.missing_required_args(
            turn_sources=("tool", "oracle"), arm_config=None,
            server_url="http://x", model_path="m.gguf", model_sha256="a" * 64,
        )
        assert "--arm-config" in missing

    def test_arm_config_not_required_for_a_vad_only_invocation(self):
        missing = launcher.missing_required_args(
            turn_sources=("vad",), arm_config=None,
            server_url="http://x", model_path="m.gguf", model_sha256="a" * 64,
        )
        assert missing == []

    def test_server_url_model_path_and_sha256_are_always_required(self):
        missing = launcher.missing_required_args(
            turn_sources=("vad",), arm_config=None, server_url=None, model_path=None, model_sha256=None,
        )
        assert set(missing) == {"--server-url", "--model-path", "--model-sha256"}

    def test_vad_only_invocation_without_arm_config_passes_the_cli_gate(self):
        # main()'s own required-args check, exercised WITHOUT --arm-config,
        # for a --turn-sources vad invocation -- proves the gate itself
        # (not just the helper) never demands --arm-config here. Stops at
        # the next required arg (--server-url) rather than attempting any
        # real network/diar contact.
        with pytest.raises(SystemExit) as excinfo:
            launcher.main(["--wave", "1", "--data-dir", "unused", "--turn-sources", "vad"])
        assert excinfo.value.code != 0


class TestDefaultOutDirCeilingsProfile:
    def test_no_profile_is_unchanged_from_before(self):
        assert launcher.default_out_dir(1) == launcher.default_out_dir(1, None)
        assert launcher.default_out_dir(1).name == "2026-08-19-precomp-wave1"

    def test_g1_supplement_profile_uses_its_own_separate_directory(self):
        out_dir = launcher.default_out_dir(1, "g1-supplement")
        assert out_dir.name == launcher.G1_SUPPLEMENT_OUT_DIR_NAME
        assert out_dir != launcher.default_out_dir(1)

    def test_wave_1_and_wave_2_profile_names_are_unchanged_from_the_bare_wave_default(self):
        assert launcher.default_out_dir(1, "wave-1") == launcher.default_out_dir(1)
        assert launcher.default_out_dir(2, "wave-2") == launcher.default_out_dir(2)


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
# run_wave: the VAD-supplement turn source, its own ceilings profile, and
# resume-skip of already-receipted tool/oracle work (the G1 VAD-supplement
# extension, docs/readiness/2026-08-19-g1-floors-preregistration.md SS3/SS6)
# ---------------------------------------------------------------------------


class TestRunWaveVadSupplement:
    def test_turn_sources_vad_skips_diar_and_populates_only_vad_receipts(self, tmp_path):
        fx = _wave_fixture(tmp_path, ["MTG1", "MTG2"])
        out_dir = tmp_path / "out"
        calls: list = []

        def tracking_run_subprocess(args, *, timeout):
            calls.append(args)
            return _rttm_writer()(args, timeout=timeout)

        summary = launcher.run_wave(
            wave=1,
            data_dir=fx["data_dir"],
            meetings=["MTG1", "MTG2"],
            tool_config=None,
            transport=fx["transport"],
            out_dir=out_dir,
            derived_root=tmp_path / "derived",
            cache_dir=tmp_path / "cache",
            resume=False,
            skip_roster_check=True,
            run_subprocess=tracking_run_subprocess,
            turn_sources=("vad",),
            ceilings=G1_SUPPLEMENT_CEILINGS,
        )

        assert summary["n_ok"] == 2
        assert calls == []  # the pinned diar tool was never contacted
        for meeting_id in ("MTG1", "MTG2"):
            receipt = json.loads((out_dir / "receipts" / f"{meeting_id}-receipt.json").read_text(encoding="utf-8"))
            assert receipt["slice_plans"]["tool"] is None
            assert receipt["slice_plans"]["oracle"] is None
            assert receipt["slice_plans"]["vad"] is not None
        assert summary["budget"]["ceilings"]["max_encode_calls"] == 500

    def test_ceilings_profile_object_is_used_instead_of_the_per_wave_default(self, tmp_path):
        fx = _wave_fixture(tmp_path, ["MTG1"])
        out_dir = tmp_path / "out"

        summary = launcher.run_wave(
            wave=1,
            data_dir=fx["data_dir"],
            meetings=["MTG1"],
            tool_config=None,
            transport=fx["transport"],
            out_dir=out_dir,
            derived_root=tmp_path / "derived",
            cache_dir=tmp_path / "cache",
            resume=False,
            skip_roster_check=True,
            turn_sources=("vad",),
            ceilings=G1_SUPPLEMENT_CEILINGS,
        )

        assert summary["budget"]["ceilings"] == G1_SUPPLEMENT_CEILINGS.to_dict()
        assert summary["budget"]["ceilings"]["max_encode_calls"] != ceilings_for_wave(1).max_encode_calls

    def test_supplements_own_separate_out_dir_precharge_never_inherits_wave1_usage(self, tmp_path):
        # A prior receipt sitting under WAVE-1's own out-dir that alone
        # already exhausts wave-1's 900-call ceiling must NOT affect the
        # supplement's own, separately-out-dir'd budget (module docstring).
        fx = _wave_fixture(tmp_path, ["MTG1"])
        wave1_out_dir = tmp_path / "wave1-out"
        (wave1_out_dir / "receipts").mkdir(parents=True)
        heavy_receipt = build_meeting_receipt(
            wave=1, meeting_id="MTG0", ok=True, error=None,
            diar={"contact": None, "n_turns": 1, "wall_seconds": 1.0, "gpu_seconds_estimate": 0.0},
            slice_plans={"tool": {"n_slices": 1}, "oracle": {"n_slices": 1}},
            cutting={"tool": {"n_entries": 1}, "oracle": {"n_entries": 1}, "wall_seconds": 0.0, "workers": 8},
            encode_warm={"tool": [{}] * 738, "oracle": [], "wall_seconds": 0.0, "n_calls": 738},
            metrics={}, budget_after={}, recorded_utc="2026-08-19T00:00:00+00:00",
        )
        (wave1_out_dir / "receipts" / "MTG0-receipt.json").write_text(json.dumps(heavy_receipt), encoding="utf-8")

        supplement_out_dir = tmp_path / "g1-supplement-out"  # a SEPARATE directory
        summary = launcher.run_wave(
            wave=1,
            data_dir=fx["data_dir"],
            meetings=["MTG1"],
            tool_config=None,
            transport=fx["transport"],
            out_dir=supplement_out_dir,
            derived_root=tmp_path / "derived",
            cache_dir=tmp_path / "cache",
            resume=False,
            skip_roster_check=True,
            turn_sources=("vad",),
            ceilings=G1_SUPPLEMENT_CEILINGS,
        )

        assert summary["n_ok"] == 1
        assert summary["stopped_reason"] is None
        assert summary["budget"]["encode_calls_used"] < 500  # never precharged wave-1's 738

    def test_resume_skips_an_already_ok_supplement_receipt(self, tmp_path):
        fx = _wave_fixture(tmp_path, ["MTG1"])
        out_dir = tmp_path / "out"
        (out_dir / "receipts").mkdir(parents=True)
        vad_only_receipt = build_meeting_receipt(
            wave=1, meeting_id="MTG1", ok=True, error=None,
            diar={"contact": None, "n_turns": None, "wall_seconds": None, "gpu_seconds_estimate": None},
            slice_plans={"tool": None, "oracle": None, "vad": {"n_slices": 1}},
            cutting={"tool": None, "oracle": None, "vad": {"n_entries": 1}, "wall_seconds": 0.0, "workers": 8},
            encode_warm={"tool": [], "oracle": [], "vad": [{}], "wall_seconds": 0.0, "n_calls": 1},
            metrics={}, budget_after={}, recorded_utc="2026-08-19T00:00:00+00:00",
        )
        (out_dir / "receipts" / "MTG1-receipt.json").write_text(json.dumps(vad_only_receipt), encoding="utf-8")
        calls: list = []

        def tracking_run_subprocess(args, *, timeout):
            calls.append(args)
            return _rttm_writer()(args, timeout=timeout)

        summary = launcher.run_wave(
            wave=1,
            data_dir=fx["data_dir"],
            meetings=["MTG1"],
            tool_config=None,
            transport=fx["transport"],
            out_dir=out_dir,
            derived_root=tmp_path / "derived",
            cache_dir=tmp_path / "cache",
            resume=True,
            skip_roster_check=True,
            run_subprocess=tracking_run_subprocess,
            turn_sources=("vad",),
            ceilings=G1_SUPPLEMENT_CEILINGS,
        )

        assert calls == []
        assert summary["n_meetings"] == 0  # MTG1 skipped: its own vad-only receipt is already ok


# ---------------------------------------------------------------------------
# run_wave: native budget pre-charge from existing on-disk receipts
# ---------------------------------------------------------------------------


class TestRunWaveBudgetPrecharge:
    def _prior_receipt(self, meeting_id: str, *, diar_gpu_seconds: float) -> dict:
        return build_meeting_receipt(
            wave=1,
            meeting_id=meeting_id,
            ok=True,
            error=None,
            diar={"contact": None, "n_turns": 1, "wall_seconds": 1.0, "gpu_seconds_estimate": diar_gpu_seconds},
            slice_plans={"tool": {"n_slices": 1}, "oracle": {"n_slices": 1}},
            cutting={"tool": {"n_entries": 1}, "oracle": {"n_entries": 1}, "wall_seconds": 0.0, "workers": 8},
            encode_warm={"tool": [], "oracle": [], "wall_seconds": 0.0, "n_calls": 0},
            metrics={},
            budget_after={},
            recorded_utc="2026-08-19T00:00:00+00:00",
        )

    def test_no_prior_receipts_leaves_a_fresh_wave_1_budget_at_zero(self, tmp_path):
        fx = _wave_fixture(tmp_path, ["MTG1"])
        out_dir = tmp_path / "out"

        summary = launcher.run_wave(
            wave=1,
            data_dir=fx["data_dir"],
            meetings=["MTG1"],
            tool_config=_tool_config(),
            transport=fx["transport"],
            out_dir=out_dir,
            derived_root=tmp_path / "derived",
            cache_dir=tmp_path / "cache",
            resume=False,
            skip_roster_check=True,
            run_subprocess=_rttm_writer(),
            # budget deliberately omitted: run_wave builds + precharges its own
        )

        assert summary["n_ok"] == 1
        assert summary["stopped_reason"] is None

    def test_cumulative_usage_from_existing_receipts_is_applied_fail_closed(self, tmp_path):
        # A receipt already on disk for a DIFFERENT, previously-completed
        # meeting that alone already spent the full registered wave-1 diar
        # GPU-hour ceiling (0.5h == 1800s).
        fx = _wave_fixture(tmp_path, ["MTG1"])
        out_dir = tmp_path / "out"
        (out_dir / "receipts").mkdir(parents=True)
        (out_dir / "receipts" / "MTG0-receipt.json").write_text(
            json.dumps(self._prior_receipt("MTG0", diar_gpu_seconds=1800.0)), encoding="utf-8"
        )

        summary = launcher.run_wave(
            wave=1,
            data_dir=fx["data_dir"],
            meetings=["MTG1"],
            tool_config=_tool_config(),
            transport=fx["transport"],
            out_dir=out_dir,
            derived_root=tmp_path / "derived",
            cache_dir=tmp_path / "cache",
            resume=False,
            skip_roster_check=True,
            run_subprocess=_rttm_writer(),
            # budget omitted: precharge must re-derive the 1800s of prior diar usage
        )

        # MTG1 would exceed the wave-cumulative diar ceiling the instant it
        # started diarizing, so it never ran at all.
        assert summary["stopped_reason"] is not None
        assert summary["n_meetings"] == 0
        assert summary["budget"]["diar_gpu_seconds_used"] == 1800.0
        assert not (out_dir / "receipts" / "MTG1-receipt.json").is_file()

    def test_a_caller_supplied_budget_opts_out_of_precharge(self, tmp_path):
        # The same already-at-ceiling prior receipt as above, but this call
        # supplies its own fresh budget -- precharge must NOT run, and the
        # meeting proceeds normally.
        fx = _wave_fixture(tmp_path, ["MTG1"])
        out_dir = tmp_path / "out"
        (out_dir / "receipts").mkdir(parents=True)
        (out_dir / "receipts" / "MTG0-receipt.json").write_text(
            json.dumps(self._prior_receipt("MTG0", diar_gpu_seconds=1800.0)), encoding="utf-8"
        )
        budget = PrecompBudget(WaveCeilings(wave=1, max_diar_gpu_hours=1.0, max_encode_gpu_hours=1.0, max_cutting_wall_hours=1.0, max_encode_calls=100))

        summary = launcher.run_wave(
            wave=1,
            data_dir=fx["data_dir"],
            meetings=["MTG1"],
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

        assert summary["n_ok"] == 1
        assert summary["stopped_reason"] is None


# ---------------------------------------------------------------------------
# run_wave: native --stop-file hook
# ---------------------------------------------------------------------------


def _rttm_writer_dropping_stop_file_after(meeting_id: str, stop_file: Path):
    def run(args, *, timeout):
        (rttm_path,) = [a for a in args if a.endswith(".rttm")]
        Path(rttm_path).write_text(write_rttm_text((TurnSpan(0.0, 1.8, "spk1"),), file_id="MTG"), encoding="utf-8")
        if Path(rttm_path).name == f"{meeting_id}.rttm":
            stop_file.write_text("", encoding="utf-8")

        class _Completed:
            returncode = 0
            stderr = ""

        return _Completed()

    return run


class TestRunWaveStopFile:
    def test_no_stop_file_runs_every_meeting(self, tmp_path):
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
            stop_file=tmp_path / "does-not-exist",
        )

        assert summary["n_meetings"] == 2
        assert summary["stopped_reason"] is None

    def test_stop_file_present_before_the_first_meeting_yields_immediately(self, tmp_path):
        fx = _wave_fixture(tmp_path, ["MTG1", "MTG2"])
        out_dir = tmp_path / "out"
        stop_file = tmp_path / "PRECOMP_YIELD"
        stop_file.write_text("", encoding="utf-8")
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
            stop_file=stop_file,
        )

        assert summary["n_meetings"] == 0
        assert "stop-file" in summary["stopped_reason"]
        assert not (out_dir / "receipts" / "MTG1-receipt.json").is_file()
        assert (out_dir / "wave-summary.json").is_file()

    def test_stop_file_dropped_mid_run_is_honored_before_the_next_meeting(self, tmp_path):
        fx = _wave_fixture(tmp_path, ["MTG1", "MTG2"])
        out_dir = tmp_path / "out"
        stop_file = tmp_path / "PRECOMP_YIELD"
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
            run_subprocess=_rttm_writer_dropping_stop_file_after("MTG1", stop_file),
            budget=budget,
            stop_file=stop_file,
        )

        # MTG1 (sorted first) completed and receipted BEFORE the stop-file
        # appeared; MTG2 was never attempted once it did.
        assert summary["n_meetings"] == 1
        assert summary["n_ok"] == 1
        assert "MTG2" in summary["stopped_reason"]
        assert (out_dir / "receipts" / "MTG1-receipt.json").is_file()
        assert not (out_dir / "receipts" / "MTG2-receipt.json").is_file()

    def test_stop_file_is_never_deleted_or_modified_by_the_runner(self, tmp_path):
        # The stop file is dropped by the (simulated) operator mid-run,
        # exactly like the mid-run test above -- then, after the wave has
        # yielded because of it, its content must be exactly what the
        # operator wrote: the runner only ever reads it via ``is_file()``.
        fx = _wave_fixture(tmp_path, ["MTG1", "MTG2"])
        out_dir = tmp_path / "out"
        stop_file = tmp_path / "PRECOMP_YIELD"
        budget = PrecompBudget(WaveCeilings(wave=1, max_diar_gpu_hours=1.0, max_encode_gpu_hours=1.0, max_cutting_wall_hours=1.0, max_encode_calls=100))

        def run_subprocess(args, *, timeout):
            (rttm_path,) = [a for a in args if a.endswith(".rttm")]
            Path(rttm_path).write_text(write_rttm_text((TurnSpan(0.0, 1.8, "spk1"),), file_id="MTG"), encoding="utf-8")
            if Path(rttm_path).name == "MTG1.rttm":
                stop_file.write_text("operator note", encoding="utf-8")

            class _Completed:
                returncode = 0
                stderr = ""

            return _Completed()

        launcher.run_wave(
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
            run_subprocess=run_subprocess,
            budget=budget,
            stop_file=stop_file,
        )

        assert stop_file.is_file()
        assert stop_file.read_text(encoding="utf-8") == "operator note"


# ---------------------------------------------------------------------------
# featcache defaults: ami/q4km, matching the warm cache the server writes
# and G1 reads (docs/checks/2026-08-19-precomp-wave1/README.md's identity
# table: ``/home/chao/feat-cache/ami-q4km``)
# ---------------------------------------------------------------------------


class TestFeatcacheDefaults:
    def test_default_dataset_and_encoder_are_ami_and_q4km(self):
        assert launcher.DEFAULT_FEATCACHE_DATASET == "ami"
        assert launcher.DEFAULT_ENCODER_ID == "q4km"

    def test_default_ids_resolve_to_the_ami_q4km_cache_directory(self, tmp_path):
        directory = campaign_cache_dir(launcher.DEFAULT_FEATCACHE_DATASET, launcher.DEFAULT_ENCODER_ID, root=tmp_path)
        assert directory.name == "ami-q4km"

    def test_featcache_flags_still_accept_an_override(self, capsys):
        # --summary-only never touches the cache directory itself, but this
        # confirms --featcache-dataset/--encoder remain ordinary, overridable
        # argparse options -- only the *default* changed.
        rc = launcher.main(
            [
                "--wave", "1", "--data-dir", "unused",
                "--featcache-dataset", "some-other-dataset",
                "--encoder", "some-other-encoder",
                "--summary-only",
            ]
        )
        assert rc == 0

    def test_featcache_root_override_still_composes_with_the_default_ids(self, tmp_path):
        directory = campaign_cache_dir(
            launcher.DEFAULT_FEATCACHE_DATASET, launcher.DEFAULT_ENCODER_ID, root=tmp_path / "custom-root"
        )
        assert directory == tmp_path / "custom-root" / "ami-q4km"


# ---------------------------------------------------------------------------
# ceilings_for_wave sanity (imported indirectly through main's --wave choices)
# ---------------------------------------------------------------------------


def test_wave_argument_only_accepts_registered_waves():
    with pytest.raises(SystemExit):
        launcher.main(["--wave", "0", "--data-dir", "unused", "--summary-only"])
