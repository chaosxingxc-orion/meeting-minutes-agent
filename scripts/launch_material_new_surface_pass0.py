#!/usr/bin/env python3
"""Run the frozen new-surface development Pass0 with exact wire capture."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import urllib.request
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget  # noqa: E402
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig  # noqa: E402
from meeting_minutes_agent.heads.transcribe_attribute import build_transcribe_only_request  # noqa: E402
from meeting_minutes_agent.runreceipt import config_hash, write_run_receipt  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_runtime(path: Path) -> dict[str, Any]:
    runtime = json.loads(path.read_text(encoding="utf-8"))
    if runtime.get("schema") != "material-new-surface-pass0-runtime-v1":
        raise ValueError("runtime schema mismatch")
    expected = config_hash({key: value for key, value in runtime.items() if key != "content_hash"})
    if runtime.get("content_hash") != expected:
        raise ValueError("runtime content hash mismatch")
    return runtime


def write_bytes_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


class WireCapturePost:
    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        self.request_path: Path | None = None
        self.response_path: Path | None = None

    def bind(self, request_path: Path, response_path: Path) -> None:
        self.request_path = request_path
        self.response_path = response_path

    def __call__(self, url: str, body: bytes) -> bytes:
        if self.request_path is None or self.response_path is None:
            raise RuntimeError("wire capture paths are not bound")
        write_bytes_exclusive(self.request_path, body)
        request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            raw = response.read()
        write_bytes_exclusive(self.response_path, raw)
        return raw


def verify_bindings(
    runtime_path: Path,
    runtime: dict[str, Any],
    cohort: Path,
    admission: Path,
    trace_schema: Path,
    dataset_root: Path,
    reader: Path,
    preregistration: Path,
    *,
    verify_large_model: bool,
) -> None:
    expected = runtime["inputs"]
    checks = {
        "cohort_sha256": cohort,
        "admission_config_sha256": admission,
        "trace_schema_sha256": trace_schema,
        "runner_sha256": Path(__file__).resolve(),
        "reader_sha256": reader,
        "preregistration_sha256": preregistration,
    }
    for field, path in checks.items():
        if sha256_file(path) != expected[field]:
            raise ValueError(f"{field} mismatch")
    for clip in runtime["clips"]:
        path = dataset_root / clip["audio_relative"]
        if sha256_file(path) != clip["audio_sha256"]:
            raise ValueError(f"audio hash mismatch: {clip['turn_id']}")
    model = runtime["model"]
    local_files = (
        (Path(model["mmproj_path"]), model["mmproj_sha256"], "mmproj"),
        (Path(model["server_binary"]), model["server_sha256"], "server binary"),
    )
    for path, expected_sha, label in local_files:
        if sha256_file(path) != expected_sha:
            raise ValueError(f"{label} hash mismatch")
    model_path = Path(model["model_path"])
    if not model_path.is_file():
        raise ValueError("model file is absent")
    if verify_large_model and sha256_file(model_path) != model["model_sha256"]:
        raise ValueError("model hash mismatch")
    if sha256_file(runtime_path) == "":
        raise AssertionError("unreachable")


def load_valid_prefix(index_path: Path, runtime: dict[str, Any], output_root: Path) -> list[dict[str, Any]]:
    if not index_path.exists():
        return []
    rows = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
    if len(rows) > len(runtime["clips"]):
        raise ValueError("existing index exceeds runtime")
    for position, row in enumerate(rows):
        clip = runtime["clips"][position]
        if (row.get("position"), row.get("request_id"), row.get("turn_id")) != (
            position, clip["request_id"], clip["turn_id"]
        ):
            raise ValueError("existing index is not an exact runtime prefix")
        for field in ("request_artifact", "response_artifact"):
            binding = row[field]
            path = output_root / binding["relative_path"]
            if not path.is_file() or path.stat().st_size != binding["bytes"] or sha256_file(path) != binding["sha256"]:
                raise ValueError(f"existing {field} drift at position {position}")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--admission-config", required=True, type=Path)
    parser.add_argument("--trace-schema", required=True, type=Path)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--reader", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-large-model-rehash", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args(argv)
    runtime = load_runtime(args.runtime)
    summary = {"calls": runtime["budget"]["calls"], "audio_seconds": runtime["budget"]["audio_seconds"], "output_root": str(args.output_root)}
    if args.summary_only:
        print(json.dumps(summary, indent=2))
        return 0
    verify_bindings(
        args.runtime, runtime, args.cohort, args.admission_config, args.trace_schema,
        args.dataset_root, args.reader, args.preregistration,
        verify_large_model=not args.skip_large_model_rehash,
    )
    if args.output_root.exists() and not args.resume:
        parser.error("output root exists; use --resume only for an exact validated prefix")
    args.output_root.mkdir(parents=True, exist_ok=True)
    runtime_copy = args.output_root / "runtime.json"
    if not runtime_copy.exists():
        shutil.copyfile(args.runtime, runtime_copy)
    elif sha256_file(runtime_copy) != sha256_file(args.runtime):
        raise ValueError("output runtime copy drift")
    index_path = args.output_root / "index.jsonl"
    rows = load_valid_prefix(index_path, runtime, args.output_root)
    completed = len(rows)
    remaining_clips = runtime["clips"][completed:]
    remaining_seconds = sum(float(clip["duration_s"]) for clip in remaining_clips)
    if remaining_clips:
        budget = CallBudget(BudgetLimits(max_calls=len(remaining_clips), max_audio_seconds=remaining_seconds))
        transport_config = runtime["transport"]
        capture = WireCapturePost(float(transport_config["timeout_seconds"]))
        transport = LlamaServerTransport(
            TransportConfig(
                base_url=runtime["model"]["base_url"],
                slots=int(runtime["model"]["slots"]),
                max_retries=int(transport_config["max_retries"]),
                timeout_seconds=float(transport_config["timeout_seconds"]),
                max_audio_seconds_per_request=float(transport_config["max_audio_seconds_per_request"]),
            ),
            budget,
            post=capture,
        )
        head = build_transcribe_only_request(decoding_params=dict(runtime["decoding"]))
        for clip in remaining_clips:
            request_rel = f"requests/{clip['request_id']}.json"
            response_rel = f"responses/{clip['request_id']}.json"
            request_path = args.output_root / request_rel
            response_path = args.output_root / response_rel
            if request_path.exists() or response_path.exists():
                raise ValueError(f"orphan wire artifact before request: {clip['request_id']}")
            capture.bind(request_path, response_path)
            response = transport.request(
                **head.to_transport_kwargs(
                    request_id=clip["request_id"],
                    audio_path=args.dataset_root / clip["audio_relative"],
                    audio_seconds=float(clip["duration_s"]),
                )
            )
            row = {
                "schema": "material-new-surface-pass0-index-row-v1",
                "position": clip["position"],
                "item_id": clip["item_id"],
                "meeting_id": clip["meeting_id"],
                "turn_id": clip["turn_id"],
                "audio_role": clip["audio_role"],
                "audio_sha256": clip["audio_sha256"],
                "audio_duration_ms": round(float(clip["duration_s"]) * 1000),
                "request_id": clip["request_id"],
                "request_artifact": {"relative_path": request_rel, "sha256": sha256_file(request_path), "bytes": request_path.stat().st_size},
                "response_artifact": {"relative_path": response_rel, "sha256": sha256_file(response_path), "bytes": response_path.stat().st_size},
                "transcript_text": response.text,
                "transcript_sha256": hashlib.sha256(response.text.encode("utf-8")).hexdigest(),
                "usage": dict(response.usage),
                "attempts": [attempt.as_json() for attempt in response.attempts],
                "recorded_utc": datetime.now(timezone.utc).isoformat(),
            }
            append_jsonl(index_path, row)
            rows.append(row)
            print(f"{len(rows)}/{len(runtime['clips'])} {clip['turn_id']}", flush=True)
    if len(rows) != len(runtime["clips"]):
        raise ValueError("Pass0 index is incomplete")
    receipt_path = args.output_root / "receipt.json"
    if receipt_path.exists():
        raise ValueError("receipt already exists")
    ledger = [attempt for row in rows for attempt in row["attempts"]]
    write_run_receipt(
        receipt_path,
        {
            "experiment_id": runtime["experiment_id"],
            "runtime_sha256": sha256_file(args.runtime),
            "server_identity": runtime["model"],
            "request_ledger": ledger,
            "artifact_index_sha256": sha256_file(index_path),
            "budget_totals": {
                "calls_used": len(rows),
                "audio_seconds_used": sum(float(clip["duration_s"]) for clip in runtime["clips"]),
                **runtime["budget"],
            },
        },
        repo_root=ROOT,
        run_id="e-material-new-surface-development-pass0-v1",
    )
    print(json.dumps({**summary, "index_sha256": sha256_file(index_path), "receipt_sha256": sha256_file(receipt_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
