#!/usr/bin/env python3
"""Run the frozen development semantic embedding flight with complete trace."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any
import urllib.error
import urllib.request

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.state.material_retrieval import word_tokens  # noqa: E402
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402
from meeting_minutes_agent.state.material_trace import (  # noqa: E402
    append_trace_row,
    candidate_keyset_sha256,
    canonical_json,
    row_content_sha256,
    sha256_text,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_bytes_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def wait_for_server(url: str, process: subprocess.Popen[bytes], timeout: float = 180.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"embedding server exited early with code {process.returncode}")
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(1)
    raise TimeoutError("embedding server did not become healthy")


def normalize(vectors: list[list[float]]) -> np.ndarray:
    array = np.asarray(vectors, dtype=np.float32)
    if array.ndim != 2:
        raise ValueError("embedding response is not a matrix")
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("zero embedding vector")
    return np.asarray(array / norms, dtype=np.float32)


def embed_batches(url: str, texts: list[str], label: str, batch_size: int, output_root: Path) -> np.ndarray:
    vectors: list[list[float]] = []
    for batch_index, start in enumerate(range(0, len(texts), batch_size)):
        batch = texts[start : start + batch_size]
        body = json.dumps({"input": batch, "model": "qwen3-embedding-0.6b", "encoding_format": "float"}).encode("utf-8")
        request_rel = f"embedding-requests/{label}-{batch_index:03d}.json"
        response_rel = f"embedding-responses/{label}-{batch_index:03d}.json"
        request_path = output_root / request_rel
        response_path = output_root / response_rel
        write_bytes_exclusive(request_path, body)
        request = urllib.request.Request(f"{url}/v1/embeddings", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = response.read()
        write_bytes_exclusive(response_path, raw)
        parsed = json.loads(raw.decode("utf-8"))
        data = sorted(parsed["data"], key=lambda row: int(row["index"]))
        if len(data) != len(batch):
            raise ValueError(f"embedding response count mismatch: {label}-{batch_index}")
        vectors.extend([[float(value) for value in row["embedding"]] for row in data])
        append_jsonl(output_root / "embedding-index.jsonl", {
            "schema": "material-new-surface-embedding-batch-v1",
            "label": label,
            "batch_index": batch_index,
            "inputs": len(batch),
            "request_artifact": {"relative_path": request_rel, "sha256": sha256_file(request_path), "bytes": request_path.stat().st_size},
            "response_artifact": {"relative_path": response_rel, "sha256": sha256_file(response_path), "bytes": response_path.stat().st_size},
        })
    if len(vectors) != len(texts):
        raise ValueError(f"embedding inventory mismatch: {label}")
    return normalize(vectors)


def keywords(text: str, maximum: int) -> list[str]:
    counts = Counter(token for token in word_tokens(text) if len(token) >= 3)
    return [token for token, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:maximum]]


def build_queries(pass0_rows: list[dict[str, Any]], maximum_keywords: int, instruction: str) -> list[dict[str, Any]]:
    history: dict[str, str] = {}
    queries = []
    for row in pass0_rows:
        item_id = str(row["item_id"])
        prior = history.get(item_id, "")
        prior_tokens = keywords(prior, maximum_keywords) if prior else []
        speaker = f"known-single-speaker:{item_id}"
        query_text = (
            f"{instruction}Predicted speaker: {speaker}\n"
            f"Prior topic keywords: {', '.join(prior_tokens) if prior_tokens else 'none'}\n"
            f"Transcript: {row['transcript_text']}"
        )
        queries.append({"pass0": row, "predicted_speaker_id": speaker, "prior_context_text": prior, "prior_topic_keywords": prior_tokens, "query_text": query_text})
        history[item_id] = str(row["transcript_text"])
    return queries


def derangement(meeting_ids: list[str]) -> dict[str, str]:
    ordered = sorted(meeting_ids)
    return {meeting_id: ordered[(index + 1) % len(ordered)] for index, meeting_id in enumerate(ordered)}


def save_vector(path: Path, key: str, array: np.ndarray, relative_path: str) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError(f"vector sidecar exists: {path}")
    np.savez(path, **{key: np.asarray(array, dtype=np.float32)})
    with path.open("rb") as handle:
        os.fsync(handle.fileno())
    value = np.asarray(array, dtype=np.float32)
    return {
        "relative_path": relative_path,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "array_key": key,
        "vector_sha256": hashlib.sha256(value.tobytes(order="C")).hexdigest(),
        "dimension": int(value.shape[-1]),
    }


def scored_candidates(candidates: list[dict[str, Any]], key_vectors: np.ndarray, query_vector: np.ndarray) -> tuple[list[dict[str, Any]], np.ndarray]:
    scores = np.asarray(key_vectors @ query_vector, dtype=np.float32)
    order = sorted(range(len(candidates)), key=lambda index: (-float(scores[index]), str(candidates[index]["candidate_id"])))
    rows = []
    for rank, index in enumerate(order, 1):
        candidate = candidates[index]
        rows.append({
            "rank": rank,
            "candidate_id": candidate["candidate_id"],
            "meeting_id": candidate["meeting_id"],
            "key_text": candidate["key_text"],
            "key_sha256": candidate["key_sha256"],
            "score": float(scores[index]),
            "value": candidate["value"],
        })
    return rows, np.asarray(key_vectors[order], dtype=np.float32)


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
        if sha256_file(path) != runtime["inputs"][field]:
            raise ValueError(f"{field} mismatch")
    pass0_rows = [json.loads(line) for line in (args.pass0_root / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(pass0_rows) != 40:
        raise ValueError("expected 40 Pass0 rows")
    selected_source = args.snapshot_root / "selected-candidates.json"
    selected_document = json.loads(selected_source.read_text(encoding="utf-8"))
    if selected_document.get("reference_reads") != 0:
        raise ValueError("candidate snapshot reference firewall failed")
    candidates = selected_document["candidates"]
    by_meeting = {meeting_id: [row for row in candidates if str(row["meeting_id"]) == meeting_id] for meeting_id in sorted({str(row["meeting_id"]) for row in candidates})}
    if len(by_meeting) != 20 or any(len(rows) != 8 for rows in by_meeting.values()):
        raise ValueError("candidate inventory drift")
    queries = build_queries(pass0_rows, int(runtime["construction"]["maximum_prior_keywords"]), str(runtime["construction"]["query_instruction"]))
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
            wait_for_server(url, process)
            ordered_candidates = [row for meeting_id in sorted(by_meeting) for row in by_meeting[meeting_id]]
            key_vectors = embed_batches(url, [str(row["key_text"]) for row in ordered_candidates], "keys", int(runtime["embedding"]["batch_size"]), args.output_root)
            query_vectors = embed_batches(url, [str(row["query_text"]) for row in queries], "queries", int(runtime["embedding"]["batch_size"]), args.output_root)
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
    wrong = derangement(list(by_meeting))
    trace_path = args.output_root / "trace.jsonl"
    candidate_binding = {"relative_path": "selected-candidates.json", "sha256": sha256_file(candidate_copy), "bytes": candidate_copy.stat().st_size}
    pass0_relative = Path(os.path.relpath(args.pass0_root, args.output_root)).as_posix()
    for position, (query, query_vector) in enumerate(zip(queries, query_vectors, strict=True)):
        pass0 = query["pass0"]
        meeting_id = str(pass0["meeting_id"])
        control_id = wrong[meeting_id]
        correct, correct_vectors = scored_candidates(by_meeting[meeting_id], key_vectors_by_meeting[meeting_id], query_vector)
        control, control_vectors = scored_candidates(by_meeting[control_id], key_vectors_by_meeting[control_id], query_vector)
        query_rel = f"vectors/query-{position:03d}.npz"
        correct_rel = f"vectors/correct-{position:03d}.npz"
        control_rel = f"vectors/deranged-{position:03d}.npz"
        query_binding = save_vector(args.output_root / query_rel, "query", query_vector, query_rel)
        correct_binding = save_vector(args.output_root / correct_rel, "keys", correct_vectors, correct_rel)
        control_binding = save_vector(args.output_root / control_rel, "keys", control_vectors, control_rel)
        context = {
            "predicted_speaker_id": query["predicted_speaker_id"],
            "prior_context_text": query["prior_context_text"],
            "prior_topic_keywords": query["prior_topic_keywords"],
        }
        threshold = float(runtime["trace_threshold"])
        row = {
            "schema": "material-new-surface-dispatch-trace-row-v1",
            "experiment_id": "E-MATERIAL-NEW-SURFACE-RUNTIME-GATE",
            "trace_run_id": runtime["trace_run_id"],
            "recorded_utc": datetime.now(timezone.utc).isoformat(),
            "split": "development",
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
        print(f"trace {position + 1}/40 {pass0['turn_id']}", flush=True)
    embedding_index = args.output_root / "embedding-index.jsonl"
    receipt = {
        "schema": "material-new-surface-embedding-receipt-v1",
        "experiment_id": runtime["experiment_id"],
        "runtime_sha256": sha256_file(args.runtime),
        "reference_reads": 0,
        "confirmation_access": 0,
        "embedding_calls": len(embedding_index.read_text(encoding="utf-8").splitlines()),
        "embeddings": len(candidates) + len(queries),
        "dimension": int(query_vectors.shape[1]),
        "trace_rows": 40,
        "trace_sha256": sha256_file(trace_path),
        "embedding_index_sha256": sha256_file(embedding_index),
        "server_log_sha256": sha256_file(server_log),
    }
    (args.output_root / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
