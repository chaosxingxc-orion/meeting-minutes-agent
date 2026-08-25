#!/usr/bin/env python3
"""Fit and confirm the construction-isolated material semantic runtime gate."""

from __future__ import annotations

import argparse
from collections import Counter, deque
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

from meeting_minutes_agent.state.material_retrieval import word_tokens  # noqa: E402


KEY_WIDTH = 8
KEY_SELECTION_SALT = "material-runtime-gate-ci-2026-08-25-v1"
MINIMUM_QUERY_CONTENT_TOKENS = 3
PRIOR_TURN_WINDOW = 20
MAX_PRIOR_KEYWORDS = 8
MINIMUM_KEYWORD_EVIDENCE = 2
EXCERPT_RADIUS = 240
QUERY_INSTRUCTION = "Instruct: Identify the meeting-specific official material candidate most relevant to this runtime speech context.\nQuery: "
KEY_PREFIX = "Official material candidate: "
BATCH_SIZE = 16


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def compact(text: str) -> str:
    return " ".join(text.split())


def page_lookup(path: Path) -> dict[tuple[str, int], str]:
    return {
        (str(row["file_id"]), int(row["page"])): str(row["text"])
        for row in load_jsonl(path)
    }


def source_excerpt(text: str, surface: str) -> str:
    collapsed = compact(text)
    position = collapsed.casefold().find(surface.casefold())
    if position < 0:
        return collapsed[: EXCERPT_RADIUS * 2]
    start = max(0, position - EXCERPT_RADIUS)
    end = min(len(collapsed), position + len(surface) + EXCERPT_RADIUS)
    return collapsed[start:end]


def select_keys(candidate_path: Path, pages_path: Path) -> list[dict[str, object]]:
    candidates = load_json(candidate_path)["candidates"]
    pages = page_lookup(pages_path)
    by_meeting: dict[str, list[dict[str, object]]] = {}
    for row in candidates:  # type: ignore[assignment]
        by_meeting.setdefault(str(row["file_id"]), []).append(row)
    keys = []
    for file_id in sorted(by_meeting):
        rows = by_meeting[file_id]
        rows.sort(
            key=lambda row: (
                hashlib.sha256(f"{KEY_SELECTION_SALT}:{file_id}:{row['surface']}".encode()).hexdigest(),
                str(row["surface"]).casefold(),
            )
        )
        if len(rows) < KEY_WIDTH:
            raise ValueError(f"meeting {file_id} has fewer than {KEY_WIDTH} candidates")
        for row in rows[:KEY_WIDTH]:
            occurrence = sorted(
                row["occurrences"],
                key=lambda item: (int(item["page"]), str(item["local_name"])),
            )[0]
            page = int(occurrence["page"])
            keys.append(
                {
                    "file_id": file_id,
                    "canonical": str(row["surface"]),
                    "category": str(row["kind"]),
                    "page": page,
                    "source_span": source_excerpt(pages[(file_id, page)], str(row["surface"])),
                }
            )
    return keys


def prior_keywords(history: deque[str]) -> list[str]:
    counts: Counter[str] = Counter()
    for text in history:
        counts.update(set(word_tokens(text)))
    eligible = [(count, token) for token, count in counts.items() if count >= MINIMUM_KEYWORD_EVIDENCE]
    eligible.sort(key=lambda item: (-item[0], item[1]))
    return [token for _, token in eligible[:MAX_PRIOR_KEYWORDS]]


def build_queries(
    registration: dict[str, object],
    runtime: dict[str, object],
    response_dir: Path,
    response_hashes: dict[str, str],
) -> list[dict[str, object]]:
    split_by_id = {str(row["file_id"]): str(row["split"]) for row in registration["cohort"]}
    queries = []
    for meeting in runtime["meetings"]:
        file_id = str(meeting["file_id"])
        path = response_dir / f"{file_id}-responses.jsonl"
        if sha256_file(path) != response_hashes[file_id]:
            raise ValueError(f"Pass0 response hash mismatch: {file_id}")
        responses = {int(row["turn_index"]): row for row in load_jsonl(path)}
        expected = [int(turn["index"]) for turn in meeting["turns"]]
        if sorted(responses) != expected:
            raise ValueError(f"Pass0 turn inventory mismatch: {file_id}")
        history: deque[str] = deque(maxlen=PRIOR_TURN_WINDOW)
        for turn in meeting["turns"]:
            turn_index = int(turn["index"])
            text = str(responses[turn_index].get("text", ""))
            keywords = prior_keywords(history)
            if len(word_tokens(text)) >= MINIMUM_QUERY_CONTENT_TOKENS:
                queries.append(
                    {
                        "file_id": file_id,
                        "split": split_by_id[file_id],
                        "turn_index": turn_index,
                        "speaker_id": str(turn["speaker_id"]),
                        "text": text,
                        "keywords": keywords,
                    }
                )
            history.append(text)
    return queries


def derangement(file_ids: list[str]) -> dict[str, str]:
    ordered = sorted(file_ids)
    return {file_id: ordered[(index + 1) % len(ordered)] for index, file_id in enumerate(ordered)}


def query_text(row: dict[str, object]) -> str:
    keywords = ", ".join(row["keywords"]) if row["keywords"] else "none"
    return (
        f"{QUERY_INSTRUCTION}Predicted speaker: {row['speaker_id']}\n"
        f"Prior topic keywords: {keywords}\nTranscript: {row['text']}"
    )


def key_text(row: dict[str, object]) -> str:
    return f"{KEY_PREFIX}{row['canonical']}. Context: {row['source_span']}"


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
        f"{url}/v1/embeddings", data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.load(response)
    rows = sorted(result["data"], key=lambda row: int(row["index"]))
    return [[float(value) for value in row["embedding"]] for row in rows]


def embed_all(url: str, texts: list[str]) -> tuple[list[tuple[float, ...]], int]:
    vectors = []
    calls = 0
    for start in range(0, len(texts), BATCH_SIZE):
        vectors.extend(embed_batch(url, texts[start : start + BATCH_SIZE]))
        calls += 1
    normalized = []
    for vector in vectors:
        norm = math.sqrt(sum(value * value for value in vector))
        if not norm:
            raise ValueError("zero embedding vector")
        normalized.append(tuple(value / norm for value in vector))
    return normalized, calls


def cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def score_rows(
    keys: list[dict[str, object]], queries: list[dict[str, object]], split: str, server_url: str
) -> tuple[list[dict[str, object]], dict[str, int | float]]:
    split_queries = [row for row in queries if row["split"] == split]
    file_ids = sorted({str(row["file_id"]) for row in split_queries})
    split_keys = [row for row in keys if str(row["file_id"]) in file_ids]
    wrong = derangement(file_ids)
    key_vectors, key_calls = embed_all(server_url, [key_text(row) for row in split_keys])
    query_vectors, query_calls = embed_all(server_url, [query_text(row) for row in split_queries])
    keyed = {
        file_id: [(row, key_vectors[index]) for index, row in enumerate(split_keys) if row["file_id"] == file_id]
        for file_id in file_ids
    }
    scored = []
    for query, vector in zip(split_queries, query_vectors, strict=True):
        file_id = str(query["file_id"])
        correct = sorted(
            [(row, cosine(vector, key_vector)) for row, key_vector in keyed[file_id]],
            key=lambda item: (item[1], str(item[0]["canonical"]).casefold()), reverse=True,
        )
        control = sorted(
            [(row, cosine(vector, key_vector)) for row, key_vector in keyed[wrong[file_id]]],
            key=lambda item: (item[1], str(item[0]["canonical"]).casefold()), reverse=True,
        )
        scored.append(
            {
                "file_id": file_id,
                "turn_index": query["turn_index"],
                "speaker_id": query["speaker_id"],
                "correct_top1": correct[0][1],
                "correct_top2": correct[1][1],
                "selector_gap": correct[0][1] - correct[1][1],
                "deranged_file_id": wrong[file_id],
                "deranged_top1": control[0][1],
                "correct_minus_deranged": correct[0][1] - control[0][1],
                "attribution_win": correct[0][1] > control[0][1],
            }
        )
    return scored, {
        "embedding_calls": key_calls + query_calls,
        "embeddings": len(split_keys) + len(split_queries),
        "embedding_dimension": len(key_vectors[0]),
    }


def summarize(rows: list[dict[str, object]], threshold: float) -> dict[str, object]:
    dispatched = [row for row in rows if float(row["selector_gap"]) >= threshold]
    wins = sum(bool(row["attribution_win"]) for row in dispatched)
    deltas = [float(row["correct_minus_deranged"]) for row in dispatched]
    return {
        "eligible_turns": len(rows),
        "dispatched_turns": len(dispatched),
        "dispatch_coverage": len(dispatched) / len(rows) if rows else 0.0,
        "attribution_wins": wins,
        "attribution_precision": wins / len(dispatched) if dispatched else 0.0,
        "median_correct_minus_deranged_cosine": median(deltas) if deltas else 0.0,
    }


def per_meeting(rows: list[dict[str, object]], threshold: float) -> list[dict[str, object]]:
    return [
        {"file_id": file_id, **summarize([row for row in rows if row["file_id"] == file_id], threshold)}
        for file_id in sorted({str(row["file_id"]) for row in rows})
    ]


def verify_inputs(config: dict[str, object], args: argparse.Namespace) -> None:
    paths = {
        "registration_sha256": args.registration,
        "runtime_sha256": args.runtime,
        "candidate_pool_sha256": args.candidate_pool,
        "material_pages_sha256": args.material_pages,
        "model_sha256": args.model,
        "server_binary_sha256": args.server_binary,
        "preflight_sha256": args.preflight,
    }
    for field, path in paths.items():
        if sha256_file(path) != str(config[field]):
            raise ValueError(f"{field} mismatch")
    if sha256_file(Path(__file__).resolve()) != str(config["runner_sha256"]):
        raise ValueError("runner_sha256 mismatch")


def run_server(args: argparse.Namespace, callback: object) -> object:
    server_url = f"http://127.0.0.1:{args.port}"
    with tempfile.TemporaryDirectory(prefix="material-gate-ci-") as temporary:
        log_path = Path(temporary) / "server.log"
        with log_path.open("wb") as log:
            process = subprocess.Popen(
                [
                    str(args.server_binary), "--model", str(args.model), "--embedding", "--pooling", "last",
                    "--n-gpu-layers", "99", "--ctx-size", "8192", "--host", "127.0.0.1", "--port", str(args.port),
                ],
                stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                wait_for_server(server_url, process)
                return callback(server_url)  # type: ignore[operator]
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


def common_inputs(args: argparse.Namespace, response_hashes: dict[str, str]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    registration = load_json(args.registration)
    runtime = load_json(args.runtime)
    keys = select_keys(args.candidate_pool, args.material_pages)
    queries = build_queries(registration, runtime, args.response_dir, response_hashes)
    return keys, queries


def command_preflight(args: argparse.Namespace) -> int:
    response_hashes = load_json(args.pass0_verdict)["meetings"]
    hashes = {str(row["file_id"]): str(row["responses_sha256"]) for row in response_hashes}
    keys, queries = common_inputs(args, hashes)
    result = {
        "schema": "material-runtime-gate-ci-semantic-preflight-v1",
        "rules": {
            "key_width": KEY_WIDTH, "key_selection_salt": KEY_SELECTION_SALT,
            "minimum_query_content_tokens": MINIMUM_QUERY_CONTENT_TOKENS,
            "prior_turn_window": PRIOR_TURN_WINDOW, "max_prior_keywords": MAX_PRIOR_KEYWORDS,
            "minimum_keyword_evidence": MINIMUM_KEYWORD_EVIDENCE, "excerpt_radius": EXCERPT_RADIUS,
            "batch_size": BATCH_SIZE,
        },
        "response_sha256": hashes,
        "splits": {},
    }
    for split in ("development", "confirmation"):
        count = sum(row["split"] == split for row in queries)
        meetings = sorted({str(row["file_id"]) for row in queries if row["split"] == split})
        key_count = sum(str(row["file_id"]) in meetings for row in keys)
        result["splits"][split] = {
            "meetings": meetings,
            "keys": key_count,
            "queries": count,
            "embeddings": key_count + count,
            "maximum_embedding_calls": math.ceil(key_count / BATCH_SIZE) + math.ceil(count / BATCH_SIZE),
        }
    if args.output.exists():
        raise ValueError(f"output exists: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result["splits"], indent=2))
    return 0


def command_development(args: argparse.Namespace) -> int:
    if args.output.exists():
        raise ValueError(f"output exists: {args.output}")
    config = load_json(args.config)
    verify_inputs(config, args)
    keys, queries = common_inputs(args, config["pass0_sha256"])
    expected = int(config["expected_queries"]["development"])
    if sum(row["split"] == "development" for row in queries) != expected:
        raise ValueError("development query count drift")

    def evaluate(url: str) -> dict[str, object]:
        rows, budget = score_rows(keys, queries, "development", url)
        grid = []
        selected = None
        for threshold in config["threshold_grid"]:
            value = float(threshold)
            totals = summarize(rows, value)
            meetings = per_meeting(rows, value)
            passed = (
                float(totals["attribution_precision"]) >= float(config["gates"]["development_minimum_attribution_precision"])
                and float(totals["dispatch_coverage"]) >= float(config["gates"]["development_minimum_coverage"])
                and all(int(row["dispatched_turns"]) > 0 for row in meetings)
            )
            grid.append({"threshold": value, "passed": passed, "totals": totals, "meetings": meetings})
            if selected is None and passed:
                selected = value
        return {
            "schema": "material-runtime-gate-ci-development-read-v1",
            "experiment_id": config["experiment_id"],
            "config_sha256": sha256_file(args.config),
            "selected_threshold": selected,
            "grid": grid,
            "budget": budget,
            "verdict": "DEVELOPMENT_GATE_READY" if selected is not None else "DEVELOPMENT_GATE_FAILED",
        }

    result = run_server(args, evaluate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "selected_threshold": result["selected_threshold"]}, indent=2))
    return 0 if result["verdict"] == "DEVELOPMENT_GATE_READY" else 3


def command_confirmation(args: argparse.Namespace) -> int:
    if args.output.exists():
        raise ValueError(f"output exists: {args.output}")
    config = load_json(args.config)
    verify_inputs(config, args)
    development = load_json(args.development_read)
    if development.get("verdict") != "DEVELOPMENT_GATE_READY" or development.get("selected_threshold") is None:
        raise ValueError("development gate did not freeze a threshold")
    threshold = float(development["selected_threshold"])
    keys, queries = common_inputs(args, config["pass0_sha256"])
    expected = int(config["expected_queries"]["confirmation"])
    if sum(row["split"] == "confirmation" for row in queries) != expected:
        raise ValueError("confirmation query count drift")

    def evaluate(url: str) -> dict[str, object]:
        rows, budget = score_rows(keys, queries, "confirmation", url)
        totals = summarize(rows, threshold)
        meetings = per_meeting(rows, threshold)
        meetings_over_floor = sum(
            float(row["attribution_precision"]) >= float(config["gates"]["confirmation_per_meeting_precision_floor"])
            for row in meetings
        )
        gates = {
            "minimum_attribution_precision": float(totals["attribution_precision"]) >= float(config["gates"]["confirmation_minimum_attribution_precision"]),
            "minimum_coverage": float(totals["dispatch_coverage"]) >= float(config["gates"]["confirmation_minimum_coverage"]),
            "minimum_distributed_meetings": meetings_over_floor >= int(config["gates"]["confirmation_meetings_at_or_above_precision_floor"]),
            "minimum_median_correct_minus_deranged_cosine": float(totals["median_correct_minus_deranged_cosine"]) >= float(config["gates"]["confirmation_minimum_median_correct_minus_deranged_cosine"]),
        }
        return {
            "schema": "material-runtime-gate-ci-confirmation-read-v1",
            "experiment_id": config["experiment_id"],
            "evidence_tier": "CONSTRUCTION_ISOLATED_EXPLORATORY",
            "config_sha256": sha256_file(args.config),
            "development_read_sha256": sha256_file(args.development_read),
            "selected_threshold": threshold,
            "totals": totals,
            "meetings": meetings,
            "meetings_over_precision_floor": meetings_over_floor,
            "gates": gates,
            "budget": budget,
            "verdict": "CONSTRUCTION_ISOLATED_SIGNAL_PRESENT" if all(gates.values()) else "CONSTRUCTION_ISOLATED_SIGNAL_INSUFFICIENT",
            "claim_boundary": "Construction-isolated exploratory semantic routing only; no external generalization, WER gain, or Omni correction claim.",
        }

    result = run_server(args, evaluate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "selected_threshold": threshold, "totals": result["totals"], "meetings": result["meetings"], "gates": result["gates"]}, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    main = argparse.ArgumentParser()
    sub = main.add_subparsers(dest="command", required=True)
    for name, function in (("preflight", command_preflight), ("development", command_development), ("confirmation", command_confirmation)):
        command = sub.add_parser(name)
        command.add_argument("--registration", required=True, type=Path)
        command.add_argument("--runtime", required=True, type=Path)
        command.add_argument("--candidate-pool", required=True, type=Path)
        command.add_argument("--material-pages", required=True, type=Path)
        command.add_argument("--response-dir", required=True, type=Path)
        command.add_argument("--output", required=True, type=Path)
        if name == "preflight":
            command.add_argument("--pass0-verdict", required=True, type=Path)
        else:
            command.add_argument("--config", required=True, type=Path)
            command.add_argument("--model", required=True, type=Path)
            command.add_argument("--server-binary", required=True, type=Path)
            command.add_argument("--preflight", required=True, type=Path)
            command.add_argument("--port", type=int, default=18762)
        if name == "confirmation":
            command.add_argument("--development-read", required=True, type=Path)
        command.set_defaults(func=function)
    return main


if __name__ == "__main__":
    arguments = parser().parse_args()
    raise SystemExit(arguments.func(arguments))
