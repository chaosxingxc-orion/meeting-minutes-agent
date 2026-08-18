"""Tests for ``scripts/launch_pattr_smoke.py``.

This engineering mission ONLY import-verifies and wiring-tests this script
(mission scope: "the flight mission runs it; you only import-verify it") --
every request in these tests goes through a FAKE ``post`` callable
(:class:`~meeting_minutes_agent.client.transport.LlamaServerTransport`'s own
injection seam), never a real ``llama-server`` process or network call, per
this repository's zero-model-contact test-suite policy."""

from __future__ import annotations

import json
from pathlib import Path

import launch_pattr_smoke as launcher
import pytest

from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget
from meeting_minutes_agent.client.receipts import FlightReceipt, ModelFileRef, ServerIdentity
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig
from meeting_minutes_agent.probes.pattr import ARM_A_TURN, PattrManifest


def _small_manifest_document() -> dict:
    return {
        "schema_version": "1.0.0",
        "created_utc": "2026-08-18T00:00:00+00:00",
        "purpose": "test",
        "seed": 1,
        "candidate_pool": ["MTG1"],
        "selected_meetings": ["MTG1"],
        "selection_rule": "test",
        "n_meetings_requested": 1,
        "slicer": {
            "mode": "turn_aware", "turn_provenance": "oracle-turn", "allow_oracle_turns": True,
            "nominal_s": 90.0, "min_s": 60.0, "max_s": 120.0, "snap_s": 3.0, "max_slices_per_meeting": 1,
        },
        "ami_annotations_root_relative": "datasets/ami/annotations/manual_1.6.2",
        "ami_audio_root_relative": "datasets/ami/amicorpus",
        "ami_role_registry_hash": "deadbeef",
        "slice_output_dir_relative": "derived/meeting-minutes/pattr-smoke/slices",
        "turn_clip_output_dir_relative": "derived/meeting-minutes/pattr-smoke/turn-clips",
        "meetings": {
            "MTG1": {
                "role": "asr-eval",
                "audio_relpath": "datasets/ami/amicorpus/MTG1/audio/MTG1.Mix-Headset.wav",
                "audio_sha256": "aaaa",
                "meeting_duration_s": 200.0,
                "n_turns_total": 2,
                "slice_plan": {
                    "meeting_id": "MTG1", "mode": "turn_aware", "turn_provenance": "oracle-turn",
                    "sample_rate": 16000, "channels": 1,
                    "entries": [
                        {
                            "index": 0, "start": 0.0, "end": 90.0, "filename": "MTG1-slice0000.wav",
                            "sha256": "s0", "vad_snap_applied": False, "encoder_chunk_count": 3,
                            "turns": [
                                {"speaker": "A", "absolute_start": 0.0, "absolute_end": 40.0, "slice_offset_start": 0.0, "slice_offset_end": 40.0},
                                {"speaker": "B", "absolute_start": 40.0, "absolute_end": 90.0, "slice_offset_start": 40.0, "slice_offset_end": 90.0},
                            ],
                        }
                    ],
                    "content_hash": "planhash1",
                },
                "turn_clips": [
                    {"turn_index": 0, "slice_index": 0, "speaker": "A", "absolute_start": 0.0, "absolute_end": 40.0, "duration_s": 40.0, "filename": "MTG1-turn0000.wav", "sha256": "t0"},
                    {"turn_index": 1, "slice_index": 0, "speaker": "B", "absolute_start": 40.0, "absolute_end": 90.0, "duration_s": 50.0, "filename": "MTG1-turn0001.wav", "sha256": "t1"},
                ],
                "covered_duration_s": 90.0,
                "n_slices": 1,
                "n_turn_clips": 2,
            }
        },
        "totals": {"n_meetings": 1, "n_slices": 1, "n_turn_clips": 2, "slice_audio_seconds": 90.0, "turn_clip_audio_seconds": 90.0},
    }


def _write_manifest(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_small_manifest_document()), encoding="utf-8")
    return path


def _write_fake_audio(data_dir: Path, relpath: str) -> None:
    path = Path(data_dir) / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF....WAVEfmt ")


def _canned_response(text="A|hello there") -> bytes:
    return json.dumps({"choices": [{"message": {"content": text}}], "usage": {}}).encode("utf-8")


# ---------------------------------------------------------------------------
# import-verification: importing this module must never touch a network or
# execute a flight.
# ---------------------------------------------------------------------------


def test_module_imports_cleanly_without_side_effects():
    assert hasattr(launcher, "main")
    assert hasattr(launcher, "run_arm")
    assert hasattr(launcher, "build_transport_and_receipt")


def test_help_does_not_execute_a_flight(capsys):
    with pytest.raises(SystemExit) as excinfo:
        launcher.main(["--help"])
    assert excinfo.value.code == 0


# ---------------------------------------------------------------------------
# --summary-only: safe to run right now, no server required
# ---------------------------------------------------------------------------


def test_summary_only_prints_expected_counts_no_transport(tmp_path, capsys):
    manifest_path = _write_manifest(tmp_path)
    rc = launcher.main(
        ["--data-dir", str(tmp_path), "--manifest", str(manifest_path), "--arm", ARM_A_TURN, "--summary-only"]
    )
    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["A-turn"]["n_requests"] == 2
    assert printed["A-grid"]["n_requests"] == 1
    assert printed["A-free"]["n_requests"] == 1


def test_missing_flight_args_without_summary_only_errors_cleanly(tmp_path, capsys):
    manifest_path = _write_manifest(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        launcher.main(["--data-dir", str(tmp_path), "--manifest", str(manifest_path), "--arm", "A-grid"])
    assert excinfo.value.code != 0


# ---------------------------------------------------------------------------
# run_arm: real wiring, fake transport (zero model contact)
# ---------------------------------------------------------------------------


def test_run_arm_dispatches_every_request_through_the_injected_transport(tmp_path):
    manifest_path = _write_manifest(tmp_path)
    manifest = PattrManifest(raw=json.loads(manifest_path.read_text(encoding="utf-8")), source_path=manifest_path)

    for relpath in (
        "derived/meeting-minutes/pattr-smoke/turn-clips/MTG1/MTG1-turn0000.wav",
        "derived/meeting-minutes/pattr-smoke/turn-clips/MTG1/MTG1-turn0001.wav",
    ):
        _write_fake_audio(tmp_path, relpath)

    calls = []

    def fake_post(url, body):
        calls.append((url, body))
        return _canned_response()

    budget = CallBudget(BudgetLimits(max_calls=10, max_audio_seconds=1000.0))
    server_identity = ServerIdentity(base_url="http://x", model_files=(ModelFileRef(path="m.gguf", sha256="a" * 64),))
    transport = LlamaServerTransport(TransportConfig(base_url="http://x"), budget, post=fake_post)
    receipt = FlightReceipt(server_identity, budget)

    result = launcher.run_arm(ARM_A_TURN, manifest, data_dir=tmp_path, transport=transport, receipt=receipt)

    assert result is receipt
    assert len(calls) == 2  # one per turn clip
    assert len(receipt.entries) == 2
    assert budget.totals["calls_used"] == 2


def test_build_transport_and_receipt_wires_server_identity():
    transport, receipt = launcher.build_transport_and_receipt(
        base_url="http://127.0.0.1:8080",
        model_path="m.gguf",
        model_sha256="a" * 64,
        max_calls=5,
        max_audio_seconds=100.0,
        slots=4,
    )
    assert isinstance(transport, LlamaServerTransport)
    assert isinstance(receipt, FlightReceipt)
    assert receipt.server_identity.base_url == "http://127.0.0.1:8080"
    assert receipt.budget.limits.max_calls == 5
