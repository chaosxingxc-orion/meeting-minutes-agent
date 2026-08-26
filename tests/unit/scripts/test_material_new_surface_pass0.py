"""Offline tests for the frozen new-surface Pass0 flight and reader."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest

import launch_material_new_surface_pass0 as launcher
import read_material_new_surface_pass0 as reader
import build_material_new_surface_snapshot as snapshot
import run_material_new_surface_embedding as embedding
import read_material_new_surface_development_gate as gate_reader
import build_material_new_surface_confirmation_snapshot as confirmation_snapshot
import read_material_new_surface_confirmation_gate as confirmation_reader

from meeting_minutes_agent.heads.transcribe_attribute import TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE
from meeting_minutes_agent.runreceipt import config_hash


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write(path: Path, payload: bytes) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {"relative_path": path.name, "sha256": _sha(payload), "bytes": len(payload)}


def _runtime(audio: bytes) -> dict[str, object]:
    runtime: dict[str, object] = {
        "schema": "material-new-surface-pass0-runtime-v1",
        "experiment_id": "E-MATERIAL-NEW-SURFACE-PASS0",
        "decoding": {"temperature": 0, "seed": 0, "max_tokens": 512},
        "clips": [
            {
                "position": 0,
                "item_id": "ECV-0002",
                "meeting_id": "m1",
                "audio_role": "reference_audio",
                "turn_id": "ECV-0002-reference",
                "request_id": "emns-ecv-0002-reference-pass0-v1",
                "audio_sha256": _sha(audio),
                "duration_s": 1.0,
            }
        ],
    }
    runtime["content_hash"] = config_hash(runtime)
    return runtime


def _flight(tmp_path: Path) -> tuple[Path, Path]:
    audio = b"RIFF-test-audio"
    runtime = _runtime(audio)
    runtime_path = tmp_path / "frozen-runtime.json"
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
    output_root = tmp_path / "flight"
    output_root.mkdir()
    (output_root / "runtime.json").write_bytes(runtime_path.read_bytes())

    request = {
        "messages": [
            {"role": "system", "content": TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE},
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {"data": base64.b64encode(audio).decode("ascii"), "format": "wav"},
                    }
                ],
            },
        ],
        **runtime["decoding"],
    }
    response = {"choices": [{"message": {"content": "hello world"}}], "usage": {"completion_tokens": 2}}
    request_raw = json.dumps(request).encode("utf-8")
    response_raw = json.dumps(response).encode("utf-8")
    request_binding = _write(output_root / "request.json", request_raw)
    response_binding = _write(output_root / "response.json", response_raw)
    row = {
        "schema": "material-new-surface-pass0-index-row-v1",
        "position": 0,
        "request_id": runtime["clips"][0]["request_id"],
        "turn_id": runtime["clips"][0]["turn_id"],
        "audio_sha256": _sha(audio),
        "request_artifact": request_binding,
        "response_artifact": response_binding,
        "transcript_text": "hello world",
        "transcript_sha256": _sha(b"hello world"),
        "usage": {"completion_tokens": 2},
        "attempts": [{"request_id": runtime["clips"][0]["request_id"], "outcome": "ok", "retry_of": None}],
    }
    index_path = output_root / "index.jsonl"
    index_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    receipt_config = {
        "experiment_id": runtime["experiment_id"],
        "runtime_sha256": reader.sha256_file(runtime_path),
        "artifact_index_sha256": reader.sha256_file(index_path),
        "budget_totals": {"calls_used": 1},
    }
    receipt = {"config": receipt_config, "config_hash": config_hash(receipt_config)}
    (output_root / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    return runtime_path, output_root


def test_reference_blind_reader_accepts_complete_exact_wire_trace(tmp_path: Path) -> None:
    runtime_path, output_root = _flight(tmp_path)
    result = reader.read_flight(runtime_path, output_root)
    assert result["verdict"] == "PASS0_TRACE_COMPLETE"
    assert result["reference_access"] == "NONE"
    assert result["calls_completed"] == 1
    assert result["nonempty_outputs"] == 1


def test_reader_rejects_text_injected_next_to_audio(tmp_path: Path) -> None:
    runtime_path, output_root = _flight(tmp_path)
    request_path = output_root / "request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["messages"][1]["content"].insert(0, {"type": "text", "text": "gold hint"})
    payload = json.dumps(request).encode("utf-8")
    request_path.write_bytes(payload)
    index_path = output_root / "index.jsonl"
    row = json.loads(index_path.read_text(encoding="utf-8"))
    row["request_artifact"].update(sha256=_sha(payload), bytes=len(payload))
    index_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    receipt_path = output_root / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["config"]["artifact_index_sha256"] = reader.sha256_file(index_path)
    receipt["config_hash"] = config_hash(receipt["config"])
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="audio-only"):
        reader.read_flight(runtime_path, output_root)


def test_wire_capture_writes_exact_body_and_response_exclusively(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"ok":true}'

    monkeypatch.setattr(launcher.urllib.request, "urlopen", lambda request, timeout: Response())
    capture = launcher.WireCapturePost(1.0)
    request_path = tmp_path / "request.json"
    response_path = tmp_path / "response.json"
    capture.bind(request_path, response_path)
    assert capture("http://example.invalid", b'{"a":1}') == b'{"ok":true}'
    assert request_path.read_bytes() == b'{"a":1}'
    assert response_path.read_bytes() == b'{"ok":true}'
    with pytest.raises(FileExistsError):
        capture("http://example.invalid", b'{"a":2}')


def test_valid_prefix_rejects_orphan_or_hash_drift(tmp_path: Path) -> None:
    audio = b"audio"
    runtime = _runtime(audio)
    output_root = tmp_path / "flight"
    output_root.mkdir()
    request = _write(output_root / "request.json", b"request")
    response = _write(output_root / "response.json", b"response")
    row = {
        "position": 0,
        "request_id": runtime["clips"][0]["request_id"],
        "turn_id": runtime["clips"][0]["turn_id"],
        "request_artifact": request,
        "response_artifact": response,
    }
    index = output_root / "index.jsonl"
    index.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert len(launcher.load_valid_prefix(index, runtime, output_root)) == 1
    (output_root / "response.json").write_bytes(b"drift")
    with pytest.raises(ValueError, match="response_artifact drift"):
        launcher.load_valid_prefix(index, runtime, output_root)


def test_snapshot_selects_fixed_width_without_reference_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Page:
        def extract_text(self):
            return "ALPHA1 BETA2 GAMMA3 DELTA4 EPSILON5 ZETA6 ETA7 THETA8 IOTA9 KAPPA10"

    class Document:
        pages = [Page()]

    monkeypatch.setattr(snapshot, "PdfReader", lambda path: Document())
    audio_root = tmp_path / "dataset"
    material = audio_root / "materials" / "slide.pdf"
    material.parent.mkdir(parents=True)
    material.write_bytes(b"%PDF-fake")
    binding = {"relative_path": "materials/slide.pdf", "sha256": snapshot.sha256_file(material), "bytes": material.stat().st_size}
    cohort = {
        "items": [
            {"item_id": f"ECV-{index:04d}", "call_id": str(1000 + index), "split": "development", "slide": binding}
            for index in range(2, 22)
        ]
    }
    config = {"construction": {"key_width": 8, "source_excerpt_radius_characters": 20, "key_selection_salt": "salt"}}
    meetings, pages, candidates, selected = snapshot.build(config, cohort, audio_root)
    assert len(meetings) == 20
    assert len(pages) == 20
    assert len(selected) == 160
    assert all("reference" not in json.dumps(row).casefold() for row in selected)
    assert len({row["candidate_id"] for row in selected}) == 160


def test_embedding_queries_use_only_earlier_pass0_within_item() -> None:
    rows = [
        {"item_id": "ECV-0002", "transcript_text": "Alpha alpha revenue"},
        {"item_id": "ECV-0002", "transcript_text": "Beta margin"},
        {"item_id": "ECV-0003", "transcript_text": "Gamma outlook"},
    ]
    queries = embedding.build_queries(rows, 2, "Instruct: test\nQuery: ")
    assert queries[0]["prior_context_text"] == ""
    assert queries[1]["prior_context_text"] == "Alpha alpha revenue"
    assert queries[1]["prior_topic_keywords"] == ["alpha", "revenue"]
    assert queries[2]["prior_context_text"] == ""


def test_derangement_is_cyclic_and_has_no_fixed_points() -> None:
    wrong = embedding.derangement(["3", "1", "2"])
    assert wrong == {"1": "2", "2": "3", "3": "1"}
    assert all(key != value for key, value in wrong.items())


def test_development_reader_selects_lowest_passing_threshold() -> None:
    rows = []
    for index in range(40):
        rows.append({
            "meeting_id": str(index % 20),
            "decision": {"selector_gap": 0.02, "top1_score": 0.8},
            "deranged_control": {"score": 0.7},
        })
    runtime = {
        "experiment_id": "E-MATERIAL-NEW-SURFACE-RUNTIME-GATE",
        "gate": {
            "threshold_grid": [0.0, 0.01, 0.03],
            "minimum_attribution_precision": 0.7,
            "minimum_coverage": 0.2,
            "minimum_represented_meetings": 15,
            "minimum_median_correct_minus_deranged": 0.01,
        },
    }
    monkeypatch_rows = rows
    original = gate_reader.validate_trace_row
    try:
        gate_reader.validate_trace_row = lambda row: []
        result = gate_reader.read_gate(runtime, monkeypatch_rows, {"verdict": "TRACE_COMPLETE", "rows": 40})
    finally:
        gate_reader.validate_trace_row = original
    assert result["verdict"] == "DEVELOPMENT_SIGNAL_PRESENT"
    assert result["selected_threshold"] == 0.0


def test_confirmation_snapshot_processes_two_frozen_twenty_item_tranches(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_build(config, cohort, dataset_root):
        calls.append([item["item_id"] for item in cohort["items"]])
        return ([{"meeting": len(calls)}], [], [], [])

    monkeypatch.setattr(confirmation_snapshot.base, "build", fake_build)
    cohort = {
        "items": [
            {"item_id": f"ECV-{index:04d}", "split": "confirmation"}
            for index in range(40)
        ]
    }
    meetings, pages, candidates, selected = confirmation_snapshot.build_confirmation({}, cohort, Path("unused"))
    assert [len(call) for call in calls] == [20, 20]
    assert len(meetings) == 2
    assert pages == candidates == selected == []


def test_confirmation_reader_applies_frozen_threshold_and_distributed_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = []
    for meeting in range(40):
        for turn in range(2):
            rows.append({
                "meeting_id": str(meeting),
                "decision": {"selector_gap": 0.01, "top1_score": 0.8},
                "deranged_control": {"score": 0.7 if meeting < 30 or turn == 0 else 0.9},
            })
    runtime = {
        "experiment_id": "E-MATERIAL-NEW-SURFACE-CONFIRMATION",
        "inputs": {"development_read_sha256": "a" * 64},
        "confirmation_threshold": 0.0,
        "gate": {
            "minimum_attribution_precision": 0.7,
            "minimum_coverage": 0.2,
            "per_meeting_precision_floor": 0.5,
            "minimum_meetings_over_precision_floor": 24,
            "minimum_median_correct_minus_deranged": 0.01,
        },
    }
    monkeypatch.setattr(confirmation_reader, "validate_trace_row", lambda row: [])
    result = confirmation_reader.read_gate(runtime, rows, {"verdict": "TRACE_COMPLETE", "rows": 80})
    assert result["verdict"] == "CONFIRMATION_SIGNAL_PRESENT"
    assert result["totals"]["attribution_precision"] == 0.875
    assert result["totals"]["meetings_over_precision_floor"] == 40
