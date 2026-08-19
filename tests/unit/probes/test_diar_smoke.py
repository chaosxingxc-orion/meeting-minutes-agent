"""Tests for :mod:`meeting_minutes_agent.probes.diar_smoke`: audio path
resolution, arm-config loading, the wall-clock/GPU-hour budget guard, and
the best-effort GPU-utilization snapshot."""

from __future__ import annotations

import json

import pytest

from meeting_minutes_agent.probes.diar_smoke import (
    ALL_ARMS,
    ARM_A,
    ARM_B,
    ARM_C,
    DEFAULT_AMI_AUDIO_ROOT_RELATIVE,
    GPU_HOUR_CEILING,
    REGISTERED_MEETINGS,
    REQUIRED_ARMS,
    WALL_HOUR_CEILING,
    ArmConfigError,
    SmokeBudget,
    SmokeBudgetExceeded,
    estimate_gpu_seconds,
    load_arm_configs,
    meeting_audio_relpath,
    query_gpu_utilization_snapshot,
    require_meeting_audio_path,
    resolve_meeting_audio_path,
)


class TestRegisteredRoster:
    def test_six_registered_meetings(self):
        assert len(REGISTERED_MEETINGS) == 6
        assert REGISTERED_MEETINGS == (
            "ES2011a", "ES2011b", "IS1008b", "IS1008d", "TS3004b", "TS3004d",
        )

    def test_required_arms_is_a_and_b(self):
        assert REQUIRED_ARMS == (ARM_A, ARM_B)
        assert ARM_C not in REQUIRED_ARMS
        assert set(ALL_ARMS) == {ARM_A, ARM_B, ARM_C}

    def test_ceilings_match_prereg(self):
        assert GPU_HOUR_CEILING == 1.0
        assert WALL_HOUR_CEILING == 2.0


class TestAudioPathResolution:
    def test_meeting_audio_relpath_matches_pattr_manifest_convention(self):
        assert (
            meeting_audio_relpath("ES2011a")
            == "datasets/ami/amicorpus/ES2011a/audio/ES2011a.Mix-Headset.wav"
        )

    def test_custom_audio_root(self):
        assert (
            meeting_audio_relpath("ES2011a", ami_audio_root_relative="custom/root")
            == "custom/root/ES2011a/audio/ES2011a.Mix-Headset.wav"
        )

    def test_resolve_does_not_require_the_file_to_exist(self, tmp_path):
        path = resolve_meeting_audio_path("ES2011a", data_dir=tmp_path)
        assert path == tmp_path / DEFAULT_AMI_AUDIO_ROOT_RELATIVE / "ES2011a" / "audio" / "ES2011a.Mix-Headset.wav"
        assert not path.exists()

    def test_require_raises_when_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="ES2011a"):
            require_meeting_audio_path("ES2011a", data_dir=tmp_path)

    def test_require_returns_path_when_present(self, tmp_path):
        expected = resolve_meeting_audio_path("ES2011a", data_dir=tmp_path)
        expected.parent.mkdir(parents=True)
        expected.write_bytes(b"RIFF")
        assert require_meeting_audio_path("ES2011a", data_dir=tmp_path) == expected


class TestLoadArmConfigs:
    def _write(self, tmp_path, document):
        path = tmp_path / "arm-config.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def _arm_document(self, tool_name="t"):
        return {
            "tool_name": tool_name,
            "tool_version": "1.0",
            "checkpoint_sha256": "a" * 64,
            "command_template": ["t", "{audio_path}", "{rttm_path}"],
        }

    def test_loads_required_arms(self, tmp_path):
        path = self._write(tmp_path, {"A": self._arm_document("nemo"), "B": self._arm_document("nemo-speech")})
        configs = load_arm_configs(path)
        assert set(configs) == {"A", "B"}
        assert configs["A"].tool_name == "nemo"
        assert configs["B"].tool_name == "nemo-speech"

    def test_loads_optional_contingent_arm_c(self, tmp_path):
        path = self._write(
            tmp_path,
            {"A": self._arm_document(), "B": self._arm_document(), "C": self._arm_document("v1")},
        )
        configs = load_arm_configs(path)
        assert set(configs) == {"A", "B", "C"}

    def test_missing_required_arm_raises(self, tmp_path):
        path = self._write(tmp_path, {"A": self._arm_document()})
        with pytest.raises(ArmConfigError, match="missing required"):
            load_arm_configs(path)

    def test_unknown_arm_key_raises(self, tmp_path):
        path = self._write(tmp_path, {"A": self._arm_document(), "B": self._arm_document(), "Z": self._arm_document()})
        with pytest.raises(ArmConfigError, match="unknown"):
            load_arm_configs(path)

    def test_non_object_document_raises(self, tmp_path):
        path = self._write(tmp_path, ["A", "B"])
        with pytest.raises(ArmConfigError, match="JSON object"):
            load_arm_configs(path)


class TestSmokeBudget:
    def test_starts_at_zero(self):
        budget = SmokeBudget()
        budget.check_before_contact()  # never raises when nothing spent
        assert budget.wall_seconds_used == 0.0
        assert budget.gpu_seconds_used == 0.0

    def test_record_accumulates(self):
        budget = SmokeBudget()
        budget.record(wall_seconds=10.0, gpu_seconds=2.0)
        budget.record(wall_seconds=5.0, gpu_seconds=1.0)
        assert budget.wall_seconds_used == pytest.approx(15.0)
        assert budget.gpu_seconds_used == pytest.approx(3.0)

    def test_wall_ceiling_breach_refuses_next_contact(self):
        budget = SmokeBudget(max_wall_seconds=100.0)
        budget.record(wall_seconds=100.0, gpu_seconds=0.0)
        with pytest.raises(SmokeBudgetExceeded, match="wall-clock"):
            budget.check_before_contact()

    def test_gpu_ceiling_breach_refuses_next_contact(self):
        budget = SmokeBudget(max_gpu_seconds=10.0)
        budget.record(wall_seconds=1.0, gpu_seconds=10.0)
        with pytest.raises(SmokeBudgetExceeded, match="GPU-hour"):
            budget.check_before_contact()

    def test_default_ceilings_come_from_the_registered_constants(self):
        budget = SmokeBudget()
        assert budget.max_wall_seconds == pytest.approx(WALL_HOUR_CEILING * 3600.0)
        assert budget.max_gpu_seconds == pytest.approx(GPU_HOUR_CEILING * 3600.0)

    def test_to_dict_is_json_safe(self):
        budget = SmokeBudget()
        budget.record(wall_seconds=1.0, gpu_seconds=0.5)
        payload = budget.to_dict()
        assert payload["wall_seconds_used"] == pytest.approx(1.0)
        assert payload["gpu_seconds_used"] == pytest.approx(0.5)


class TestGpuUtilizationSnapshot:
    def test_none_when_binary_is_absent(self):
        def run(*args, **kwargs):
            raise FileNotFoundError("nvidia-smi not found")

        assert query_gpu_utilization_snapshot(run=run) is None

    def test_none_when_timeout(self):
        import subprocess

        def run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=10)

        assert query_gpu_utilization_snapshot(run=run) is None

    def test_none_on_nonzero_return_code(self):
        class _Completed:
            returncode = 1
            stdout = ""

        assert query_gpu_utilization_snapshot(run=lambda *a, **k: _Completed()) is None

    def test_parses_a_well_formed_csv_line(self):
        class _Completed:
            returncode = 0
            stdout = "45, 2048, 1200, 62, 120.5\n"

        snapshot = query_gpu_utilization_snapshot(run=lambda *a, **k: _Completed())
        assert snapshot == {
            "utilization_gpu_pct": 45.0,
            "memory_used_mib": 2048.0,
            "clocks_sm_mhz": 1200.0,
            "temperature_c": 62.0,
            "power_draw_w": 120.5,
        }

    def test_none_on_unparsable_output(self):
        class _Completed:
            returncode = 0
            stdout = "not, a, valid, csv, line\n"

        assert query_gpu_utilization_snapshot(run=lambda *a, **k: _Completed()) is None

    def test_none_on_empty_output(self):
        class _Completed:
            returncode = 0
            stdout = ""

        assert query_gpu_utilization_snapshot(run=lambda *a, **k: _Completed()) is None


class TestEstimateGpuSeconds:
    def test_none_snapshot_yields_zero(self):
        assert estimate_gpu_seconds(100.0, None) == 0.0

    def test_scales_by_utilization_percent(self):
        snapshot = {"utilization_gpu_pct": 50.0}
        assert estimate_gpu_seconds(10.0, snapshot) == pytest.approx(5.0)

    def test_clamps_utilization_to_0_100(self):
        assert estimate_gpu_seconds(10.0, {"utilization_gpu_pct": 250.0}) == pytest.approx(10.0)
        assert estimate_gpu_seconds(10.0, {"utilization_gpu_pct": -5.0}) == pytest.approx(0.0)
