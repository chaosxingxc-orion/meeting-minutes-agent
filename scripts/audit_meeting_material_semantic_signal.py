#!/usr/bin/env python3
"""Encode-only semantic Q-K-V audit for official meeting-material routing."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.state.external_identity_retrieval import contains_identity  # noqa: E402
from meeting_minutes_agent.state.material_retrieval import (  # noqa: E402
    select_balanced_keys,
    word_tokens,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def embed_batch(url: str, texts: list[str]) -> list[list[float]]:
    payload = json.dumps(
        {"input": texts, "model": "qwen3-embedding-0.6b", "encoding_format": "float"}
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{url}/v1/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.load(response)
    rows = sorted(result["data"], key=lambda row: int(row["index"]))
    return [[float(value) for value in row["embedding"]] for row in rows]


def embed_all(url: str, texts: list[str], batch_size: int) -> tuple[list[list[float]], int]:
    vectors: list[list[float]] = []
    calls = 0
    for start in range(0, len(texts), batch_size):
        vectors.extend(embed_batch(url, texts[start : start + batch_size]))
        calls += 1
    if len(vectors) != len(texts):
        raise RuntimeError("embedding response count mismatch")
    return vectors, calls


def normalized(vector: list[float]) -> tuple[float, ...]:
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        raise ValueError("zero embedding vector")
    return tuple(value / norm for value in vector)


def cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimension mismatch")
    return sum(a * b for a, b in zip(left, right, strict=True))


def summarize(rows: list[dict[str, object]]) -> dict[str, float | int]:
    dispatched = [row for row in rows if bool(row["dispatched"])]
    wins = sum(float(row["correct_score"]) > float(row["deranged_score"]) for row in dispatched)
    ties = sum(float(row["correct_score"]) == float(row["deranged_score"]) for row in dispatched)
    deltas = [float(row["correct_score"]) - float(row["deranged_score"]) for row in dispatched]
    return {
        "eligible_turns": len(rows),
        "dispatched_turns": len(dispatched),
        "correct_wins": wins,
        "ties": ties,
        "deranged_wins": len(dispatched) - wins - ties,
        "dispatch_coverage": len(dispatched) / len(rows) if rows else 0.0,
        "attribution_precision": wins / len(dispatched) if dispatched else 0.0,
        "median_correct_minus_deranged": median(deltas) if deltas else 0.0,
    }


def build_queries(
    config: dict[str, object],
    candidates: dict[str, object],
    runtime: dict[str, object],
    response_dir: Path,
) -> tuple[tuple[object, ...], list[dict[str, object]], dict[str, str]]:
    keys = select_balanced_keys(
        candidates["meetings"],
        width=int(config["balanced_key_width"]),
        salt=str(config["selection_salt"]),
    )
    file_ids = sorted({key.file_id for key in keys})
    deranged = {
        file_id: file_ids[(position + 1) % len(file_ids)]
        for position, file_id in enumerate(file_ids)
    }
    keys_by_id = {file_id: [key for key in keys if key.file_id == file_id] for file_id in file_ids}
    runtime_by_id = {str(row["file_id"]): row for row in runtime["meetings"]}
    queries = []
    for file_id in file_ids:
        response_path = response_dir / f"{file_id}-responses.jsonl"
        if sha256_file(response_path) != str(config["pass0_sha256"][file_id]):
            raise ValueError(f"Pass0 response hash mismatch: {file_id}")
        responses = {int(row["turn_index"]): row for row in json_rows(response_path)}
        compared = keys_by_id[file_id] + keys_by_id[deranged[file_id]]
        aliases = tuple(alias for key in compared for alias in key.aliases)
        for turn in runtime_by_id[file_id]["turns"]:
            turn_index = int(turn["index"])
            text = str(responses[turn_index].get("text", ""))
            if contains_identity(text, aliases):
                continue
            if len(word_tokens(text)) < int(config["minimum_query_content_tokens"]):
                continue
            queries.append(
                {
                    "file_id": file_id,
                    "deranged_file_id": deranged[file_id],
                    "turn_index": turn_index,
                    "speaker_id": str(turn["speaker_id"]),
                    "text": text,
                }
            )
    return keys, queries, deranged


def audit(
    config: dict[str, object],
    candidates: dict[str, object],
    runtime: dict[str, object],
    response_dir: Path,
    server_url: str,
) -> dict[str, object]:
    keys, queries, deranged = build_queries(config, candidates, runtime, response_dir)
    if len(queries) != int(config["gates"]["expected_eligible_turns"]):
        raise ValueError(f"eligible query count drift: {len(queries)}")
    key_texts = [f"{config['key_prefix']}{key.canonical}. {key.source_span}" for key in keys]
    query_texts = [f"{config['query_instruction']}{row['text']}" for row in queries]
    started = time.monotonic()
    key_vectors, key_calls = embed_all(server_url, key_texts, int(config["batch_size"]))
    query_vectors, query_calls = embed_all(server_url, query_texts, int(config["batch_size"]))
    elapsed = time.monotonic() - started
    normalized_keys = [normalized(vector) for vector in key_vectors]
    normalized_queries = [normalized(vector) for vector in query_vectors]
    keys_by_id = {
        file_id: [(key, normalized_keys[index]) for index, key in enumerate(keys) if key.file_id == file_id]
        for file_id in deranged
    }
    scored_rows = []
    examples = []
    minimum_gap = float(config["dispatch_minimum_top_gap"])
    for query, query_vector in zip(queries, normalized_queries, strict=True):
        file_id = str(query["file_id"])
        wrong_id = str(query["deranged_file_id"])
        correct_scored = [(key, cosine(query_vector, vector)) for key, vector in keys_by_id[file_id]]
        wrong_scored = [(key, cosine(query_vector, vector)) for key, vector in keys_by_id[wrong_id]]
        correct_key, correct_score = max(correct_scored, key=lambda item: (item[1], item[0].canonical.casefold()))
        wrong_key, wrong_score = max(wrong_scored, key=lambda item: (item[1], item[0].canonical.casefold()))
        combined = sorted(correct_scored + wrong_scored, key=lambda item: item[1], reverse=True)
        top_gap = combined[0][1] - combined[1][1]
        row = {
            "file_id": file_id,
            "deranged_file_id": wrong_id,
            "turn_index": int(query["turn_index"]),
            "speaker_id": str(query["speaker_id"]),
            "correct_key": correct_key.canonical,
            "correct_page": correct_key.page,
            "correct_score": correct_score,
            "deranged_key": wrong_key.canonical,
            "deranged_page": wrong_key.page,
            "deranged_score": wrong_score,
            "top_gap": top_gap,
            "dispatched": top_gap >= minimum_gap,
        }
        scored_rows.append(row)
        if row["dispatched"] and len(examples) < 30:
            examples.append({**row, "query_excerpt": str(query["text"])[:160]})
    totals = summarize(scored_rows)
    meetings = [
        {"file_id": file_id, "deranged_file_id": deranged[file_id], **summarize([row for row in scored_rows if row["file_id"] == file_id])}
        for file_id in sorted(deranged)
    ]
    gates_config = config["gates"]
    meetings_over_floor = sum(
        float(row["attribution_precision"]) >= float(gates_config["per_meeting_precision_floor"])
        for row in meetings
    )
    precision_gain = float(totals["attribution_precision"]) - float(gates_config["lexical_attribution_precision"])
    gates = {
        "expected_eligible_turns": int(totals["eligible_turns"]) == int(gates_config["expected_eligible_turns"]),
        "minimum_meetings": len(meetings) >= int(gates_config["minimum_meetings"]),
        "minimum_dispatch_coverage": float(totals["dispatch_coverage"]) >= float(gates_config["minimum_dispatch_coverage"]),
        "minimum_attribution_precision": float(totals["attribution_precision"]) >= float(gates_config["minimum_attribution_precision"]),
        "minimum_distributed_meetings": meetings_over_floor >= int(gates_config["minimum_meetings_over_precision_floor"]),
        "minimum_median_delta": float(totals["median_correct_minus_deranged"]) >= float(gates_config["minimum_median_correct_minus_deranged"]),
        "minimum_gain_over_lexical": precision_gain >= float(gates_config["minimum_precision_gain_over_lexical"]),
        "no_reference_audio_or_omni_contact": True,
    }
    return {
        "schema": "meeting-material-semantic-retrieval-signal-read-v1",
        "experiment_id": config["experiment_id"],
        "verdict": "SEMANTIC-RETRIEVAL-SIGNAL-PRESENT" if all(gates.values()) else "SEMANTIC-RETRIEVAL-SIGNAL-INSUFFICIENT",
        "totals": totals,
        "meetings": meetings,
        "meetings_over_precision_floor": meetings_over_floor,
        "precision_gain_over_lexical": precision_gain,
        "embedding_calls": key_calls + query_calls,
        "embeddings": len(keys) + len(queries),
        "embedding_seconds": elapsed,
        "embedding_dimension": len(normalized_keys[0]),
        "gates": gates,
        "selected_keys": [
            {"file_id": key.file_id, "canonical": key.canonical, "category": key.category, "page": key.page, "source_span": key.source_span}
            for key in keys
        ],
        "examples": examples,
        "claim_boundary": config["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--candidate-registry", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--material-pages", required=True, type=Path)
    parser.add_argument("--response-dir", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--server-binary", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18762)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; refusing a second semantic read")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    for label, path in (
        ("runtime_sha256", args.runtime),
        ("candidate_registry_sha256", args.candidate_registry),
        ("material_pages_sha256", args.material_pages),
        ("model_sha256", args.model),
        ("server_binary_sha256", args.server_binary),
    ):
        if sha256_file(path) != str(config[label]):
            parser.error(f"{label} mismatch")
    server_url = f"http://127.0.0.1:{args.port}"
    with tempfile.TemporaryDirectory(prefix="material-semantic-") as temporary:
        log_path = Path(temporary) / "server.log"
        with log_path.open("wb") as log:
            process = subprocess.Popen(
                [
                    str(args.server_binary), "--model", str(args.model), "--embedding",
                    "--pooling", "last", "--n-gpu-layers", "99", "--ctx-size", "8192",
                    "--host", "127.0.0.1", "--port", str(args.port),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                wait_for_server(server_url, process)
                result = audit(
                    config,
                    json.loads(args.candidate_registry.read_text(encoding="utf-8")),
                    json.loads(args.runtime.read_text(encoding="utf-8")),
                    args.response_dir,
                    server_url,
                )
            except Exception:
                log.flush()
                print(log_path.read_text(encoding="utf-8", errors="replace"), file=sys.stderr)
                raise
            finally:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "totals": result["totals"], "meetings": result["meetings"], "precision_gain_over_lexical": result["precision_gain_over_lexical"], "gates": result["gates"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
