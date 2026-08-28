"""Offline tests for the frozen LHCP-ASR development Pass0."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest

import launch_material_lhcp_development_pass0 as launcher
import read_material_lhcp_development_pass0 as reader
from meeting_minutes_agent.heads.transcribe_attribute import TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE
from meeting_minutes_agent.runreceipt import config_hash


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _runtime(audio: bytes) -> dict[str, object]:
    runtime: dict[str, object] = {
        "schema": "material-lhcp-development-pass0-runtime-v1",
        "experiment_id": "E-MATERIAL-LHCP-DEVELOPMENT-PASS0",
        "decoding": {"temperature": 0, "seed": 0, "max_tokens": 512},
        "clips": [{
            "position": 0, "meeting_id": "m1", "slice_index": 0,
            "turn_id": "m1-slice0000", "request_id": "lhcp-m1-slice0000-pass0-v1",
            "audio_sha256": _sha(audio), "duration_s": 1.0,
        }],
    }
    runtime["content_hash"] = config_hash(runtime)
    return runtime


def _binding(root: Path, name: str, payload: bytes) -> dict[str, object]:
    path = root / name
    path.write_bytes(payload)
    return {"relative_path": name, "sha256": _sha(payload), "bytes": len(payload)}


def _flight(tmp_path: Path) -> tuple[Path, Path]:
    audio = b"RIFF-lhcp-test"
    runtime = _runtime(audio)
    runtime_path = tmp_path / "runtime.json"
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
    root = tmp_path / "flight"
    root.mkdir()
    (root / "runtime.json").write_bytes(runtime_path.read_bytes())
    request = {
        "messages": [
            {"role": "system", "content": TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE},
            {"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": base64.b64encode(audio).decode(), "format": "wav"}}]},
        ],
        **runtime["decoding"],
    }
    response = {"choices": [{"message": {"content": "test transcript"}}], "usage": {"completion_tokens": 2}}
    row = {
        "schema": "material-lhcp-development-pass0-index-row-v1", "position": 0,
        "meeting_id": "m1", "slice_index": 0, "turn_id": "m1-slice0000",
        "request_id": "lhcp-m1-slice0000-pass0-v1", "audio_sha256": _sha(audio),
        "request_artifact": _binding(root, "request.json", json.dumps(request).encode()),
        "response_artifact": _binding(root, "response.json", json.dumps(response).encode()),
        "transcript_text": "test transcript", "transcript_sha256": _sha(b"test transcript"),
        "usage": {"completion_tokens": 2},
        "attempts": [{"request_id": "lhcp-m1-slice0000-pass0-v1", "outcome": "ok", "retry_of": None}],
    }
    index = root / "index.jsonl"
    index.write_text(json.dumps(row) + "\n", encoding="utf-8")
    config = {"experiment_id": runtime["experiment_id"], "runtime_sha256": reader.sha256_file(runtime_path),
              "artifact_index_sha256": reader.sha256_file(index), "budget_totals": {"calls_used": 1}}
    (root / "receipt.json").write_text(json.dumps({"config": config, "config_hash": config_hash(config)}), encoding="utf-8")
    return runtime_path, root


def test_lhcp_reader_accepts_complete_audio_only_trace(tmp_path: Path) -> None:
    runtime, root = _flight(tmp_path)
    result = reader.read_flight(runtime, root)
    assert result["verdict"] == "PASS0_TRACE_COMPLETE"
    assert result["meetings_completed"] == 1
    assert result["reference_access"] == "NONE"


def test_lhcp_reader_rejects_identity_drift(tmp_path: Path) -> None:
    runtime, root = _flight(tmp_path)
    index = root / "index.jsonl"
    row = json.loads(index.read_text(encoding="utf-8"))
    row["slice_index"] = 1
    index.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="identity drift"):
        reader.read_flight(runtime, root)


def test_lhcp_prefix_rejects_non_prefix_row(tmp_path: Path) -> None:
    runtime = _runtime(b"audio")
    root = tmp_path / "flight"
    root.mkdir()
    request = _binding(root, "request.json", b"request")
    response = _binding(root, "response.json", b"response")
    row = {"position": 0, "request_id": "wrong", "turn_id": "m1-slice0000", "request_artifact": request, "response_artifact": response}
    index = root / "index.jsonl"
    index.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exact runtime prefix"):
        launcher.load_valid_prefix(index, runtime, root)
