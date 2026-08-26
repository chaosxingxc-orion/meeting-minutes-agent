"""Tests for prospective material dispatch trace persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meeting_minutes_agent.state.material_trace import (
    append_trace_row,
    candidate_keyset_sha256,
    canonical_json,
    row_content_sha256,
    sha256_text,
    validate_trace_row,
)


_HASH = "a" * 64


def _artifact(path: str) -> dict[str, object]:
    return {"relative_path": path, "sha256": _HASH, "bytes": 1}


def _value(name: str) -> dict[str, object]:
    prompt = f"Untrusted spelling evidence: {name}"
    return {
        "canonical": name,
        "category": "term",
        "source_page": 1,
        "source_span": f"Evidence for {name}",
        "prompt_text": prompt,
        "prompt_sha256": sha256_text(prompt),
    }


def _row() -> dict[str, object]:
    transcript = "Pass zero text"
    context = {
        "predicted_speaker_id": "speaker_0",
        "prior_context_text": "",
        "prior_topic_keywords": ["revenue"],
    }
    correct_candidates = [
        {"rank": 1, "candidate_id": "c1", "meeting_id": "1641285", "key_text": "key one", "key_sha256": sha256_text("key one"), "score": 0.8, "value": _value("Alpha")},
        {"rank": 2, "candidate_id": "c2", "meeting_id": "1641285", "key_text": "key two", "key_sha256": sha256_text("key two"), "score": 0.5, "value": _value("Beta")},
    ]
    deranged_candidates = [
        {"rank": 1, "candidate_id": "d1", "meeting_id": "other", "key_text": "wrong one", "key_sha256": sha256_text("wrong one"), "score": 0.2, "value": _value("Gamma")},
        {"rank": 2, "candidate_id": "d2", "meeting_id": "other", "key_text": "wrong two", "key_sha256": sha256_text("wrong two"), "score": 0.1, "value": _value("Delta")},
    ]
    row = {
        "schema": "material-new-surface-dispatch-trace-row-v1",
        "experiment_id": "E-MATERIAL-NEW-SURFACE-RUNTIME-GATE",
        "trace_run_id": "run-1",
        "recorded_utc": "2026-08-26T00:00:00Z",
        "split": "development",
        "item_id": "ECV-0002",
        "meeting_id": "1641285",
        "turn_id": "ECV-0002-answer",
        "audio_role": "answer_audio",
        "audio_sha256": _HASH,
        "audio_duration_ms": 1000,
        "pass0": {
            "request_id": "request-1",
            "request_artifact": _artifact("requests/1.json"),
            "response_artifact": _artifact("responses/1.json"),
            "transcript_text": transcript,
            "transcript_sha256": sha256_text(transcript),
        },
        "runtime_context": {**context, "context_sha256": sha256_text(canonical_json(context))},
        "retrieval": {
            "query_instruction": "Retrieve.",
            "query_text": transcript,
            "query_sha256": sha256_text(transcript),
            "keyset_sha256": candidate_keyset_sha256(correct_candidates),
            "embedding_model_id": "model",
            "embedding_model_sha256": _HASH,
            "embedding_server_sha256": _HASH,
            "score_dtype": "float32",
            "candidates": correct_candidates,
        },
        "decision": {
            "top1_candidate_id": "c1", "top1_score": 0.8,
            "top2_candidate_id": "c2", "top2_score": 0.5,
            "selector_gap": 0.3, "threshold": 0.1, "dispatch": True,
            "selected_value": _value("Alpha"),
        },
        "deranged_control": {
            "policy": "salted wrong meeting", "meeting_id": "other", "keyset_sha256": candidate_keyset_sha256(deranged_candidates),
            "candidates": deranged_candidates,
            "candidate_id": "d1", "score": 0.2, "selected_value": _value("Gamma"),
        },
        "artifact_bindings": {
            "candidate_snapshot": _artifact("candidates.json"),
            "query_vector_sidecar": {**_artifact("vectors.npz"), "array_key": "q1", "vector_sha256": _HASH, "dimension": 2},
            "correct_key_vector_sidecar": {**_artifact("vectors.npz"), "array_key": "correct_keys", "vector_sha256": _HASH, "dimension": 2},
            "deranged_key_vector_sidecar": {**_artifact("vectors.npz"), "array_key": "deranged_keys", "vector_sha256": _HASH, "dimension": 2},
            "row_sha256": "",
        },
    }
    row["artifact_bindings"]["row_sha256"] = row_content_sha256(row)
    return row


def test_valid_trace_row_has_no_errors() -> None:
    assert validate_trace_row(_row()) == []


def test_forbidden_reference_field_fails_closed() -> None:
    row = _row()
    row["reference_text"] = "must stay sealed"
    row["artifact_bindings"]["row_sha256"] = row_content_sha256(row)
    assert any("forbidden reference fields" in error for error in validate_trace_row(row))


def test_score_drift_fails_closed() -> None:
    row = _row()
    row["decision"]["selector_gap"] = 0.1
    row["artifact_bindings"]["row_sha256"] = row_content_sha256(row)
    assert "selector gap mismatch" in validate_trace_row(row)


def test_append_is_jsonl_and_rejects_invalid_row(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    append_trace_row(path, _row())
    second = _row()
    second["turn_id"] = "ECV-0002-reference"
    second["audio_role"] = "reference_audio"
    second["artifact_bindings"]["row_sha256"] = row_content_sha256(second)
    append_trace_row(path, second)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2
    invalid = _row()
    invalid["deranged_control"]["meeting_id"] = invalid["meeting_id"]
    invalid["artifact_bindings"]["row_sha256"] = row_content_sha256(invalid)
    with pytest.raises(ValueError, match="deranged control"):
        append_trace_row(path, invalid)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_append_rejects_duplicate_identity(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    append_trace_row(path, _row())
    with pytest.raises(ValueError, match="duplicate trace identity"):
        append_trace_row(path, _row())
