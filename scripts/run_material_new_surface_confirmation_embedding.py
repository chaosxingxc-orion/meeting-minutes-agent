#!/usr/bin/env python3
"""Run sealed-confirmation embeddings using the frozen development primitives."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import run_material_new_surface_embedding as base  # noqa: E402
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402
from meeting_minutes_agent.state.material_trace import (  # noqa: E402
    append_trace_row,
    candidate_keyset_sha256,
    canonical_json,
    row_content_sha256,
    sha256_text,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--pass0-root", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--server-binary", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18762)
    args = parser.parse_args(argv)
    if args.output_root.exists():
        parser.error(f"output root exists: {args.output_root}")
    runtime = json.loads(args.runtime.read_text(encoding="utf-8"))
    expected_content_hash = config_hash({key: value for key, value in runtime.items() if key != "content_hash"})
    if runtime.get("content_hash") != expected_content_hash:
        raise ValueError("runtime content hash mismatch")
    bindings = {
        "runner_sha256": Path(__file__).resolve(),
        "base_runner_sha256": Path(base.__file__).resolve(),
        "reader_sha256": ROOT / runtime["inputs"]["reader_path"],
        "trace_validator_sha256": ROOT / runtime["inputs"]["trace_validator_path"],
        "pass0_index_sha256": args.pass0_root / "index.jsonl",
        "pass0_receipt_sha256": args.pass0_root / "receipt.json",
        "snapshot_receipt_sha256": args.snapshot_root / "receipt.json",
        "selected_candidates_sha256": args.snapshot_root / "selected-candidates.json",
        "model_sha256": args.model,
        "server_binary_sha256": args.server_binary,
    }
    for field, path in bindings.items():
        if base.sha256_file(path) != runtime["inputs"][field]:
            raise ValueError(f"{field} mismatch")
    pass0_rows = [json.loads(line) for line in (args.pass0_root / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(pass0_rows) != 80:
        raise ValueError("expected 80 confirmation Pass0 rows")
    selected_source = args.snapshot_root / "selected-candidates.json"
    selected_document = json.loads(selected_source.read_text(encoding="utf-8"))
    if selected_document.get("reference_reads") != 0 or selected_document.get("split") != "confirmation":
        raise ValueError("confirmation candidate snapshot firewall failed")
    candidates = selected_document["candidates"]
    by_meeting = {
        meeting_id: [row for row in candidates if str(row["meeting_id"]) == meeting_id]
        for meeting_id in sorted({str(row["meeting_id"]) for row in candidates})
    }
    if len(by_meeting) != 40 or any(len(rows) != 8 for rows in by_meeting.values()):
        raise ValueError("confirmation candidate inventory drift")
    queries = base.build_queries(
        pass0_rows,
        int(runtime["construction"]["maximum_prior_keywords"]),
        str(runtime["construction"]["query_instruction"]),
    )
    args.output_root.mkdir(parents=True)
    candidate_copy = args.output_root / "selected-candidates.json"
    shutil.copyfile(selected_source, candidate_copy)
    server_log = args.output_root / "server.log"
    url = f"http://127.0.0.1:{args.port}"
    with server_log.open("xb") as log:
        process = subprocess.Popen([
            str(args.server_binary), "--model", str(args.model), "--embedding", "--pooling", "last",
            "--n-gpu-layers", "99", "--ctx-size", "8192", "--host", "127.0.0.1", "--port", str(args.port),
        ], stdout=log, stderr=subprocess.STDOUT)
        try:
            base.wait_for_server(url, process)
            ordered_candidates = [row for meeting_id in sorted(by_meeting) for row in by_meeting[meeting_id]]
            key_vectors = base.embed_batches(
                url, [str(row["key_text"]) for row in ordered_candidates], "keys",
                int(runtime["embedding"]["batch_size"]), args.output_root,
            )
            query_vectors = base.embed_batches(
                url, [str(row["query_text"]) for row in queries], "queries",
                int(runtime["embedding"]["batch_size"]), args.output_root,
            )
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    key_vectors_by_meeting = {
        meeting_id: key_vectors[index * 8 : (index + 1) * 8]
        for index, meeting_id in enumerate(sorted(by_meeting))
    }
    wrong = base.derangement(list(by_meeting))
    trace_path = args.output_root / "trace.jsonl"
    candidate_binding = {
        "relative_path": "selected-candidates.json",
        "sha256": base.sha256_file(candidate_copy),
        "bytes": candidate_copy.stat().st_size,
    }
    pass0_relative = Path(os.path.relpath(args.pass0_root, args.output_root)).as_posix()
    for position, (query, query_vector) in enumerate(zip(queries, query_vectors, strict=True)):
        pass0 = query["pass0"]
        meeting_id = str(pass0["meeting_id"])
        control_id = wrong[meeting_id]
        correct, correct_vectors = base.scored_candidates(
            by_meeting[meeting_id], key_vectors_by_meeting[meeting_id], query_vector
        )
        control, control_vectors = base.scored_candidates(
            by_meeting[control_id], key_vectors_by_meeting[control_id], query_vector
        )
        query_rel = f"vectors/query-{position:03d}.npz"
        correct_rel = f"vectors/correct-{position:03d}.npz"
        control_rel = f"vectors/deranged-{position:03d}.npz"
        query_binding = base.save_vector(args.output_root / query_rel, "query", query_vector, query_rel)
        correct_binding = base.save_vector(args.output_root / correct_rel, "keys", correct_vectors, correct_rel)
        control_binding = base.save_vector(args.output_root / control_rel, "keys", control_vectors, control_rel)
        context = {
            "predicted_speaker_id": query["predicted_speaker_id"],
            "prior_context_text": query["prior_context_text"],
            "prior_topic_keywords": query["prior_topic_keywords"],
        }
        threshold = float(runtime["confirmation_threshold"])
        row = {
            "schema": "material-new-surface-dispatch-trace-row-v1",
            "experiment_id": "E-MATERIAL-NEW-SURFACE-RUNTIME-GATE",
            "trace_run_id": runtime["trace_run_id"],
            "recorded_utc": datetime.now(timezone.utc).isoformat(),
            "split": "confirmation",
            "item_id": pass0["item_id"],
            "meeting_id": meeting_id,
            "turn_id": pass0["turn_id"],
            "audio_role": pass0["audio_role"],
            "audio_sha256": pass0["audio_sha256"],
            "audio_duration_ms": pass0["audio_duration_ms"],
            "pass0": {
                "request_id": pass0["request_id"],
                "request_artifact": {**pass0["request_artifact"], "relative_path": f"{pass0_relative}/{pass0['request_artifact']['relative_path']}"},
                "response_artifact": {**pass0["response_artifact"], "relative_path": f"{pass0_relative}/{pass0['response_artifact']['relative_path']}"},
                "transcript_text": pass0["transcript_text"],
                "transcript_sha256": pass0["transcript_sha256"],
            },
            "runtime_context": {**context, "context_sha256": sha256_text(canonical_json(context))},
            "retrieval": {
                "query_instruction": runtime["construction"]["query_instruction"],
                "query_text": query["query_text"],
                "query_sha256": sha256_text(query["query_text"]),
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
                "policy": "ascending_call_id_next_cyclic",
                "meeting_id": control_id,
                "keyset_sha256": candidate_keyset_sha256(control),
                "candidates": control,
                "candidate_id": control[0]["candidate_id"],
                "score": control[0]["score"],
                "selected_value": control[0]["value"],
            },
            "artifact_bindings": {
                "candidate_snapshot": candidate_binding,
                "query_vector_sidecar": query_binding,
                "correct_key_vector_sidecar": correct_binding,
                "deranged_key_vector_sidecar": control_binding,
                "row_sha256": "",
            },
        }
        row["artifact_bindings"]["row_sha256"] = row_content_sha256(row)
        append_trace_row(trace_path, row)
        print(f"trace {position + 1}/80 {pass0['turn_id']}", flush=True)
    embedding_index = args.output_root / "embedding-index.jsonl"
    receipt = {
        "schema": "material-new-surface-embedding-receipt-v1",
        "experiment_id": runtime["experiment_id"],
        "runtime_sha256": base.sha256_file(args.runtime),
        "reference_reads": 0,
        "confirmation_access": 1,
        "embedding_calls": len(embedding_index.read_text(encoding="utf-8").splitlines()),
        "embeddings": len(candidates) + len(queries),
        "dimension": int(query_vectors.shape[1]),
        "trace_rows": 80,
        "trace_sha256": base.sha256_file(trace_path),
        "embedding_index_sha256": base.sha256_file(embedding_index),
        "server_log_sha256": base.sha256_file(server_log),
    }
    (args.output_root / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
