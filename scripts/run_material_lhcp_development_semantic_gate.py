#!/usr/bin/env python3
"""Run the frozen LHCP development material-embedding flight."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402
from meeting_minutes_agent.state.material_trace import (  # noqa: E402
    append_trace_row,
    candidate_keyset_sha256,
    canonical_json,
    row_content_sha256,
    sha256_text,
)
from run_material_new_surface_embedding import (  # noqa: E402
    append_jsonl,
    embed_batches,
    save_vector,
    scored_candidates,
    sha256_file,
    wait_for_server,
)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _verify_bindings(runtime: dict[str, Any], paths: dict[str, Path]) -> None:
    for field, path in paths.items():
        if sha256_file(path) != runtime["inputs"][field]:
            raise ValueError(f"{field} mismatch")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--supply-root", required=True, type=Path)
    parser.add_argument("--pass0-root", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--server-binary", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18764)
    args = parser.parse_args(argv)
    if args.output_root.exists():
        parser.error(f"output root exists: {args.output_root}")
    runtime = json.loads(args.runtime.read_text(encoding="utf-8"))
    expected_content_hash = config_hash({key: value for key, value in runtime.items() if key != "content_hash"})
    if runtime.get("content_hash") != expected_content_hash:
        raise ValueError("runtime content hash mismatch")
    _verify_bindings(runtime, {
        "runner_sha256": Path(__file__).resolve(),
        "helper_runner_sha256": ROOT / runtime["inputs"]["helper_runner_path"],
        "reader_sha256": ROOT / runtime["inputs"]["reader_path"],
        "trace_validator_sha256": ROOT / runtime["inputs"]["trace_validator_path"],
        "generic_trace_validator_sha256": ROOT / runtime["inputs"]["generic_trace_validator_path"],
        "supply_receipt_sha256": args.supply_root / "receipt.json",
        "selected_candidates_sha256": args.supply_root / "selected-candidates.json",
        "derangement_sha256": args.supply_root / "derangement.json",
        "queries_sha256": args.supply_root / "queries.jsonl",
        "pass0_index_sha256": args.pass0_root / "index.jsonl",
        "pass0_receipt_sha256": args.pass0_root / "receipt.json",
        "model_sha256": args.model,
        "server_binary_sha256": args.server_binary,
    })

    candidate_document = json.loads((args.supply_root / "selected-candidates.json").read_text(encoding="utf-8"))
    candidates = list(candidate_document["candidates"])
    queries = _load_jsonl(args.supply_root / "queries.jsonl")
    pass0_rows = _load_jsonl(args.pass0_root / "index.jsonl")
    mapping = json.loads((args.supply_root / "derangement.json").read_text(encoding="utf-8"))["mapping"]
    expected = runtime["embedding"]
    if len(candidates) != int(expected["keys"]) or len(queries) != int(expected["queries"]):
        raise ValueError("supply inventory drift")
    if len(pass0_rows) != len(queries):
        raise ValueError("Pass0/query count drift")
    by_meeting = {
        meeting_id: sorted(
            [row for row in candidates if str(row["meeting_id"]) == meeting_id],
            key=lambda row: int(row["selection_index"]),
        )
        for meeting_id in sorted({str(row["meeting_id"]) for row in candidates})
    }
    width = int(runtime["construction"]["key_width"])
    if len(by_meeting) != 25 or any(len(rows) != width for rows in by_meeting.values()):
        raise ValueError("candidate width drift")
    if set(mapping) != set(by_meeting) or sorted(mapping.values()) != sorted(by_meeting) or any(k == v for k, v in mapping.items()):
        raise ValueError("derangement drift")
    for position, (query, pass0) in enumerate(zip(queries, pass0_rows, strict=True)):
        fields = ("position", "meeting_id", "slice_index", "turn_id", "audio_sha256", "transcript_sha256", "transcript_text")
        if any(query[field] != pass0[field] for field in fields) or int(query["position"]) != position:
            raise ValueError(f"query/Pass0 binding drift at {position}")

    args.output_root.mkdir(parents=True)
    candidate_copy = args.output_root / "selected-candidates.json"
    query_copy = args.output_root / "queries.jsonl"
    derangement_copy = args.output_root / "derangement.json"
    shutil.copyfile(args.supply_root / "selected-candidates.json", candidate_copy)
    shutil.copyfile(args.supply_root / "queries.jsonl", query_copy)
    shutil.copyfile(args.supply_root / "derangement.json", derangement_copy)

    server_log = args.output_root / "server.log"
    url = f"http://127.0.0.1:{args.port}"
    with server_log.open("xb") as log:
        process = subprocess.Popen([
            str(args.server_binary), "--model", str(args.model), "--embedding", "--pooling", "last",
            "--n-gpu-layers", "99", "--ctx-size", "8192", "--host", "127.0.0.1", "--port", str(args.port),
        ], stdout=log, stderr=subprocess.STDOUT)
        try:
            wait_for_server(url, process)
            ordered_candidates = [row for meeting_id in sorted(by_meeting) for row in by_meeting[meeting_id]]
            key_vectors = embed_batches(
                url,
                [str(row["key_text"]) for row in ordered_candidates],
                "keys",
                int(expected["batch_size"]),
                args.output_root,
            )
            query_vectors = embed_batches(
                url,
                [str(row["query_text"]) for row in queries],
                "queries",
                int(expected["batch_size"]),
                args.output_root,
            )
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    if key_vectors.shape != (int(expected["keys"]), int(expected["dimension_expected"])):
        raise ValueError(f"key vector shape mismatch: {key_vectors.shape}")
    if query_vectors.shape != (int(expected["queries"]), int(expected["dimension_expected"])):
        raise ValueError(f"query vector shape mismatch: {query_vectors.shape}")

    key_vectors_by_meeting = {
        meeting_id: key_vectors[index * width : (index + 1) * width]
        for index, meeting_id in enumerate(sorted(by_meeting))
    }
    pass0_by_turn = {str(row["turn_id"]): row for row in pass0_rows}
    trace_path = args.output_root / "trace.jsonl"
    candidate_binding = {
        "relative_path": "selected-candidates.json",
        "sha256": sha256_file(candidate_copy),
        "bytes": candidate_copy.stat().st_size,
    }
    query_supply_binding = {
        "relative_path": "queries.jsonl",
        "sha256": sha256_file(query_copy),
        "bytes": query_copy.stat().st_size,
    }
    pass0_relative = Path(os.path.relpath(args.pass0_root, args.output_root)).as_posix()
    for position, (query, query_vector, pass0) in enumerate(zip(queries, query_vectors, pass0_rows, strict=True)):
        meeting_id = str(query["meeting_id"])
        control_id = str(mapping[meeting_id])
        correct, correct_vectors = scored_candidates(by_meeting[meeting_id], key_vectors_by_meeting[meeting_id], query_vector)
        control, control_vectors = scored_candidates(by_meeting[control_id], key_vectors_by_meeting[control_id], query_vector)
        query_rel = f"vectors/query-{position:03d}.npz"
        correct_rel = f"vectors/correct-{position:03d}.npz"
        control_rel = f"vectors/deranged-{position:03d}.npz"
        prior_turn_id = query["runtime_context"]["prior_turn_id"]
        prior_text = str(pass0_by_turn[prior_turn_id]["transcript_text"]) if prior_turn_id else ""
        predicted_speaker_id = ",".join(query["runtime_context"]["speaker_labels"])
        context_core = {
            "predicted_speaker_id": predicted_speaker_id,
            "prior_context_text": prior_text,
            "prior_topic_keywords": query["runtime_context"]["prior_topic_keywords"],
        }
        threshold = float(runtime["trace_threshold"])
        row = {
            "schema": "material-new-surface-dispatch-trace-row-v1",
            "experiment_id": runtime["experiment_id"],
            "trace_run_id": runtime["trace_run_id"],
            "recorded_utc": datetime.now(timezone.utc).isoformat(),
            "split": "development",
            "item_id": meeting_id,
            "meeting_id": meeting_id,
            "turn_id": str(query["turn_id"]),
            "audio_role": "transport_slice",
            "audio_sha256": str(pass0["audio_sha256"]),
            "audio_duration_ms": int(pass0["audio_duration_ms"]),
            "pass0": {
                "request_id": pass0["request_id"],
                "request_artifact": {**pass0["request_artifact"], "relative_path": f"{pass0_relative}/{pass0['request_artifact']['relative_path']}"},
                "response_artifact": {**pass0["response_artifact"], "relative_path": f"{pass0_relative}/{pass0['response_artifact']['relative_path']}"},
                "transcript_text": pass0["transcript_text"],
                "transcript_sha256": pass0["transcript_sha256"],
            },
            "runtime_context": {
                **context_core,
                "speaker_labels": query["runtime_context"]["speaker_labels"],
                "prior_turn_id": prior_turn_id,
                "prior_transcript_sha256": query["runtime_context"]["prior_transcript_sha256"],
                "potentially_truncated": bool(query["potentially_truncated"]),
                "context_sha256": sha256_text(canonical_json(context_core)),
            },
            "retrieval": {
                "query_instruction": runtime["construction"]["query_instruction"],
                "query_text": query["query_text"],
                "query_sha256": query["query_sha256"],
                "keyset_sha256": candidate_keyset_sha256(correct),
                "embedding_model_id": runtime["embedding"]["model_id"],
                "embedding_model_sha256": runtime["inputs"]["model_sha256"],
                "embedding_server_sha256": runtime["inputs"]["server_binary_sha256"],
                "score_dtype": "float32",
                "candidates": correct,
            },
            "decision": {
                "top1_candidate_id": correct[0]["candidate_id"],
                "top1_score": correct[0]["score"],
                "top2_candidate_id": correct[1]["candidate_id"],
                "top2_score": correct[1]["score"],
                "selector_gap": correct[0]["score"] - correct[1]["score"],
                "threshold": threshold,
                "dispatch": correct[0]["score"] - correct[1]["score"] >= threshold,
                "selected_value": correct[0]["value"],
            },
            "deranged_control": {
                "policy": runtime["construction"]["deranged_control"],
                "meeting_id": control_id,
                "keyset_sha256": candidate_keyset_sha256(control),
                "candidates": control,
                "candidate_id": control[0]["candidate_id"],
                "score": control[0]["score"],
                "selected_value": control[0]["value"],
            },
            "artifact_bindings": {
                "candidate_snapshot": candidate_binding,
                "query_supply": query_supply_binding,
                "query_vector_sidecar": save_vector(args.output_root / query_rel, "query", query_vector, query_rel),
                "correct_key_vector_sidecar": save_vector(args.output_root / correct_rel, "keys", correct_vectors, correct_rel),
                "deranged_key_vector_sidecar": save_vector(args.output_root / control_rel, "keys", control_vectors, control_rel),
                "row_sha256": "",
            },
        }
        row["artifact_bindings"]["row_sha256"] = row_content_sha256(row)
        append_trace_row(trace_path, row)
        print(f"trace {position + 1}/{len(queries)} {query['turn_id']}", flush=True)

    embedding_index = args.output_root / "embedding-index.jsonl"
    batch_rows = _load_jsonl(embedding_index)
    receipt = {
        "schema": "material-lhcp-development-semantic-gate-receipt-v1",
        "experiment_id": runtime["experiment_id"],
        "runtime_sha256": sha256_file(args.runtime),
        "reference_reads": 0,
        "confirmation_access": 0,
        "omni_correction_calls": 0,
        "embedding_calls": len(batch_rows),
        "embeddings": len(candidates) + len(queries),
        "dimension": int(query_vectors.shape[1]),
        "trace_rows": len(queries),
        "trace_sha256": sha256_file(trace_path),
        "embedding_index_sha256": sha256_file(embedding_index),
        "server_log_sha256": sha256_file(server_log),
        "copied_supply": {
            "selected_candidates_sha256": sha256_file(candidate_copy),
            "queries_sha256": sha256_file(query_copy),
            "derangement_sha256": sha256_file(derangement_copy),
        },
    }
    (args.output_root / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
