#!/usr/bin/env python3
"""Run the frozen LHCP full-pool semantic extraction embedding flight."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from run_material_new_surface_embedding import (  # noqa: E402
    embed_batches,
    save_vector,
    sha256_file,
    wait_for_server,
)


def rank_candidates(candidates: list[dict[str, Any]], vectors: np.ndarray, query: np.ndarray, width: int) -> list[dict[str, Any]]:
    scores = np.asarray(vectors @ query, dtype=np.float32)
    order = sorted(range(len(candidates)), key=lambda index: (-float(scores[index]), str(candidates[index]["candidate_id"])))
    return [{
        "rank": rank,
        "candidate_id": candidates[index]["candidate_id"],
        "score": float(scores[index]),
    } for rank, index in enumerate(order[:width], 1)]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--supply-root", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--server-binary", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18765)
    args = parser.parse_args(argv)
    if args.output_root.exists():
        parser.error(f"output root exists: {args.output_root}")
    runtime = json.loads(args.runtime.read_text(encoding="utf-8"))
    bindings = {
        "preregistration_sha256": ROOT / str(runtime["inputs"]["preregistration_path"]),
        "supply_receipt_sha256": args.supply_root / "receipt.json",
        "candidates_sha256": args.supply_root / "candidates.json",
        "queries_sha256": args.supply_root / "queries.jsonl",
        "model_sha256": args.model,
        "server_binary_sha256": args.server_binary,
        "helper_runner_sha256": ROOT / str(runtime["inputs"]["helper_runner_path"]),
        "runner_sha256": Path(__file__).resolve(),
        "reader_sha256": ROOT / str(runtime["inputs"]["reader_path"]),
        "readiness_auditor_sha256": ROOT / str(runtime["inputs"]["readiness_auditor_path"]),
    }
    for field, path in bindings.items():
        if sha256_file(path) != runtime["inputs"][field]:
            raise ValueError(f"{field} mismatch")
    candidate_document = json.loads((args.supply_root / "candidates.json").read_text(encoding="utf-8"))
    if candidate_document.get("reference_reads") != 0:
        raise ValueError("candidate reference firewall failed")
    candidates = list(candidate_document["candidates"])
    queries = load_jsonl(args.supply_root / "queries.jsonl")
    if len(candidates) != int(runtime["embedding"]["keys"]) or len(queries) != int(runtime["embedding"]["queries"]):
        raise ValueError("supply count drift")
    by_meeting: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, candidate in enumerate(candidates):
        by_meeting.setdefault(str(candidate["meeting_id"]), []).append((index, candidate))
    if len(by_meeting) != 25 or any(not rows for rows in by_meeting.values()):
        raise ValueError("meeting candidate inventory drift")

    args.output_root.mkdir(parents=True)
    shutil.copyfile(args.supply_root / "candidates.json", args.output_root / "candidates.json")
    shutil.copyfile(args.supply_root / "queries.jsonl", args.output_root / "queries.jsonl")
    server_log = args.output_root / "server.log"
    url = f"http://127.0.0.1:{args.port}"
    with server_log.open("xb") as log:
        process = subprocess.Popen([
            str(args.server_binary), "--model", str(args.model), "--embedding", "--pooling", "last",
            "--n-gpu-layers", "99", "--ctx-size", "8192", "--host", "127.0.0.1", "--port", str(args.port),
        ], stdout=log, stderr=subprocess.STDOUT)
        try:
            wait_for_server(url, process)
            key_vectors = embed_batches(url, [str(row["key_text"]) for row in candidates], "keys", int(runtime["embedding"]["batch_size"]), args.output_root)
            query_vectors = embed_batches(url, [str(row["query_text"]) for row in queries], "queries", int(runtime["embedding"]["batch_size"]), args.output_root)
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    dimension = int(runtime["embedding"]["dimension_expected"])
    if key_vectors.shape != (len(candidates), dimension) or query_vectors.shape != (len(queries), dimension):
        raise ValueError("embedding matrix shape drift")
    key_sidecar = save_vector(args.output_root / "vectors/keys.npz", "keys", key_vectors, "vectors/keys.npz")
    query_sidecar = save_vector(args.output_root / "vectors/queries.npz", "queries", query_vectors, "vectors/queries.npz")
    rankings_path = args.output_root / "rankings.jsonl"
    maximum_width = max(int(value) for value in runtime["evaluation"]["widths"])
    with rankings_path.open("x", encoding="utf-8", newline="\n") as handle:
        for position, (query_row, query_vector) in enumerate(zip(queries, query_vectors, strict=True)):
            meeting_id = str(query_row["meeting_id"])
            indexed = by_meeting[meeting_id]
            indices = [index for index, _ in indexed]
            meeting_candidates = [candidate for _, candidate in indexed]
            ranking = rank_candidates(meeting_candidates, key_vectors[indices], query_vector, maximum_width)
            row = {
                "schema": "material-lhcp-full-pool-semantic-ranking-v1",
                "position": position,
                "meeting_id": meeting_id,
                "turn_id": query_row["turn_id"],
                "recorded_utc": datetime.now(timezone.utc).isoformat(),
                "ranking": ranking,
            }
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
        import os
        os.fsync(handle.fileno())
    batch_rows = load_jsonl(args.output_root / "embedding-index.jsonl")
    receipt = {
        "schema": "material-lhcp-full-pool-semantic-extractor-receipt-v1",
        "experiment_id": runtime["experiment_id"],
        "runtime_sha256": sha256_file(args.runtime),
        "reference_reads": 0,
        "confirmation_access": 0,
        "omni_calls": 0,
        "embedding_calls": len(batch_rows),
        "embeddings": len(candidates) + len(queries),
        "dimension": dimension,
        "ranking_rows": len(queries),
        "artifacts": {
            "rankings.jsonl": {"sha256": sha256_file(rankings_path), "bytes": rankings_path.stat().st_size},
            "embedding-index.jsonl": {"sha256": sha256_file(args.output_root / "embedding-index.jsonl"), "bytes": (args.output_root / "embedding-index.jsonl").stat().st_size},
            "server.log": {"sha256": sha256_file(server_log), "bytes": server_log.stat().st_size},
            "key_vectors": key_sidecar,
            "query_vectors": query_sidecar,
        },
        "verdict": "LHCP_FULL_POOL_SEMANTIC_TRACE_COMPLETE",
    }
    (args.output_root / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": receipt["verdict"], "embedding_calls": len(batch_rows), "embeddings": receipt["embeddings"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
