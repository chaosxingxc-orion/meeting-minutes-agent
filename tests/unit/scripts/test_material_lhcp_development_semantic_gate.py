"""Offline tests for the LHCP development semantic gate."""

from __future__ import annotations

from pathlib import Path

import read_material_lhcp_development_semantic_gate as reader
import validate_material_lhcp_development_semantic_trace as validator
from meeting_minutes_agent.state.material_trace import (
    candidate_keyset_sha256,
    canonical_json,
    row_content_sha256,
    sha256_text,
)


def _candidate(candidate_id: str, meeting_id: str, score: float) -> dict[str, object]:
    prompt = f"evidence {candidate_id}"
    key = f"key {candidate_id}"
    return {
        "rank": 0,
        "candidate_id": candidate_id,
        "meeting_id": meeting_id,
        "key_text": key,
        "key_sha256": sha256_text(key),
        "score": score,
        "value": {"prompt_text": prompt, "prompt_sha256": sha256_text(prompt)},
    }


def _row(turn_id: str, top_score: float, deranged_score: float) -> dict[str, object]:
    correct = [_candidate("c1", "m1", top_score), _candidate("c2", "m1", top_score - 0.1)]
    wrong = [_candidate("w1", "m2", deranged_score), _candidate("w2", "m2", deranged_score - 0.1)]
    for rank, candidate in enumerate(correct, 1):
        candidate["rank"] = rank
    for rank, candidate in enumerate(wrong, 1):
        candidate["rank"] = rank
    transcript = f"transcript {turn_id}"
    query = f"query {turn_id}"
    context = {"predicted_speaker_id": "speaker_1", "prior_context_text": "", "prior_topic_keywords": []}
    row: dict[str, object] = {
        "schema": "material-new-surface-dispatch-trace-row-v1",
        "experiment_id": "E-MATERIAL-LHCP-DEVELOPMENT-SEMANTIC-GATE",
        "trace_run_id": "test",
        "recorded_utc": "2026-08-28T00:00:00+00:00",
        "split": "development",
        "item_id": "m1",
        "meeting_id": "m1",
        "turn_id": turn_id,
        "audio_role": "transport_slice",
        "audio_sha256": "a",
        "audio_duration_ms": 1000,
        "pass0": {
            "request_id": turn_id,
            "request_artifact": {"relative_path": "request", "sha256": "a", "bytes": 1},
            "response_artifact": {"relative_path": "response", "sha256": "b", "bytes": 1},
            "transcript_text": transcript,
            "transcript_sha256": sha256_text(transcript),
        },
        "runtime_context": {**context, "context_sha256": sha256_text(canonical_json(context))},
        "retrieval": {
            "query_text": query,
            "query_sha256": sha256_text(query),
            "keyset_sha256": candidate_keyset_sha256(correct),
            "score_dtype": "float32",
            "candidates": correct,
        },
        "decision": {
            "top1_candidate_id": "c1",
            "top1_score": top_score,
            "top2_candidate_id": "c2",
            "top2_score": top_score - 0.1,
            "selector_gap": 0.1,
            "threshold": 0.0,
            "dispatch": True,
            "selected_value": correct[0]["value"],
        },
        "deranged_control": {
            "meeting_id": "m2",
            "keyset_sha256": candidate_keyset_sha256(wrong),
            "candidates": wrong,
            "candidate_id": "w1",
            "score": deranged_score,
            "selected_value": wrong[0]["value"],
        },
        "artifact_bindings": {"row_sha256": ""},
    }
    row["artifact_bindings"]["row_sha256"] = row_content_sha256(row)
    return row


def test_reader_selects_lowest_passing_threshold() -> None:
    rows = [_row("t0", 0.9, 0.5), _row("t1", 0.8, 0.6)]
    runtime = {
        "experiment_id": "E-MATERIAL-LHCP-DEVELOPMENT-SEMANTIC-GATE",
        "embedding": {"queries": 2},
        "gate": {
            "threshold_grid": [0.0, 0.05],
            "minimum_attribution_precision": 0.7,
            "minimum_coverage": 0.2,
            "minimum_represented_meetings": 1,
            "minimum_median_correct_minus_deranged": 0.01,
        },
    }
    result = reader.read_gate(runtime, rows, {"verdict": "TRACE_COMPLETE", "rows": 2})
    assert result["verdict"] == "LHCP_DEVELOPMENT_SEMANTIC_SIGNAL_PRESENT"
    assert result["selected_threshold"] == 0.0
    assert result["grid"][0]["totals"]["attribution_precision"] == 1.0


def test_validator_fails_closed_when_artifacts_are_missing(tmp_path: Path) -> None:
    runtime = {"embedding": {"queries": 2}}
    result = validator.validate_lhcp_trace(runtime, tmp_path)
    assert result["verdict"] == "TRACE_INVALID"
    assert "missing artifacts" in result["errors"][0]
