#!/usr/bin/env python3
"""Run the frozen LHCP-ASR development Pass0 with exact-wire capture."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in (SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import launch_material_new_surface_pass0 as wire  # noqa: E402
from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget  # noqa: E402
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig  # noqa: E402
from meeting_minutes_agent.heads.transcribe_attribute import build_transcribe_only_request  # noqa: E402
from meeting_minutes_agent.runreceipt import config_hash, write_run_receipt  # noqa: E402


sha256_file = wire.sha256_file
WireCapturePost = wire.WireCapturePost
append_jsonl = wire.append_jsonl


def load_runtime(path: Path) -> dict[str, Any]:
    runtime = json.loads(path.read_text(encoding="utf-8"))
    if runtime.get("schema") != "material-lhcp-development-pass0-runtime-v1":
        raise ValueError("runtime schema mismatch")
    expected = config_hash({key: value for key, value in runtime.items() if key != "content_hash"})
    if runtime.get("content_hash") != expected:
        raise ValueError("runtime content hash mismatch")
    return runtime


def verify_bindings(
    runtime: dict[str, Any], slice_manifest: Path, source_root: Path, reader: Path,
    readiness_auditor: Path, preregistration: Path, *, verify_large_model: bool,
) -> None:
    expected = runtime["inputs"]
    checks = {
        "slice_manifest_sha256": slice_manifest,
        "runner_sha256": Path(__file__).resolve(),
        "reader_sha256": reader,
        "readiness_auditor_sha256": readiness_auditor,
        "preregistration_sha256": preregistration,
    }
    for field, path in checks.items():
        if sha256_file(path) != expected[field]:
            raise ValueError(f"{field} mismatch")
    for clip in runtime["clips"]:
        path = source_root / clip["audio_relative"]
        if not path.is_file() or sha256_file(path) != clip["audio_sha256"]:
            raise ValueError(f"audio hash mismatch: {clip['turn_id']}")
    model = runtime["model"]
    for path, expected_sha, label in (
        (Path(model["mmproj_path"]), model["mmproj_sha256"], "mmproj"),
        (Path(model["server_binary"]), model["server_sha256"], "server binary"),
    ):
        if not path.is_file() or sha256_file(path) != expected_sha:
            raise ValueError(f"{label} hash mismatch")
    model_path = Path(model["model_path"])
    if not model_path.is_file():
        raise ValueError("model file is absent")
    if verify_large_model and sha256_file(model_path) != model["model_sha256"]:
        raise ValueError("model hash mismatch")


def load_valid_prefix(index_path: Path, runtime: dict[str, Any], output_root: Path) -> list[dict[str, Any]]:
    if not index_path.exists():
        return []
    raw = index_path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("existing index is not newline-terminated")
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
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
    parser.add_argument("--slice-manifest", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--reader", required=True, type=Path)
    parser.add_argument("--readiness-auditor", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-large-model-rehash", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args(argv)
    runtime = load_runtime(args.runtime)
    summary = {"calls": runtime["budget"]["calls"], "audio_seconds": runtime["budget"]["audio_seconds"], "maximum_output_tokens": runtime["budget"]["maximum_output_tokens"], "output_root": str(args.output_root)}
    if args.summary_only:
        print(json.dumps(summary, indent=2))
        return 0
    verify_bindings(runtime, args.slice_manifest, args.source_root, args.reader, args.readiness_auditor, args.preregistration, verify_large_model=not args.skip_large_model_rehash)
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
    remaining = runtime["clips"][len(rows):]
    if remaining:
        budget = CallBudget(BudgetLimits(max_calls=len(remaining), max_audio_seconds=sum(float(c["duration_s"]) for c in remaining)))
        transport_config = runtime["transport"]
        capture = WireCapturePost(float(transport_config["timeout_seconds"]))
        transport = LlamaServerTransport(
            TransportConfig(base_url=runtime["model"]["base_url"], slots=1, max_retries=0,
                            timeout_seconds=float(transport_config["timeout_seconds"]), max_audio_seconds_per_request=120),
            budget, post=capture,
        )
        head = build_transcribe_only_request(decoding_params=dict(runtime["decoding"]))
        for clip in remaining:
            request_rel = f"requests/{clip['request_id']}.json"
            response_rel = f"responses/{clip['request_id']}.json"
            request_path = args.output_root / request_rel
            response_path = args.output_root / response_rel
            if request_path.exists() or response_path.exists():
                raise ValueError(f"orphan wire artifact before request: {clip['request_id']}")
            capture.bind(request_path, response_path)
            response = transport.request(**head.to_transport_kwargs(
                request_id=clip["request_id"], audio_path=args.source_root / clip["audio_relative"],
                audio_seconds=float(clip["duration_s"]),
            ))
            row = {
                "schema": "material-lhcp-development-pass0-index-row-v1",
                "position": clip["position"], "meeting_id": clip["meeting_id"],
                "slice_index": clip["slice_index"], "turn_id": clip["turn_id"],
                "slice_start_s": clip["slice_start_s"], "slice_end_s": clip["slice_end_s"],
                "speaker_labels": clip["speaker_labels"], "turn_count": clip["turn_count"],
                "turns_sha256": clip["turns_sha256"], "audio_sha256": clip["audio_sha256"],
                "audio_duration_ms": round(float(clip["duration_s"]) * 1000),
                "request_id": clip["request_id"],
                "request_artifact": {"relative_path": request_rel, "sha256": sha256_file(request_path), "bytes": request_path.stat().st_size},
                "response_artifact": {"relative_path": response_rel, "sha256": sha256_file(response_path), "bytes": response_path.stat().st_size},
                "transcript_text": response.text,
                "transcript_sha256": hashlib.sha256(response.text.encode("utf-8")).hexdigest(),
                "usage": dict(response.usage), "attempts": [attempt.as_json() for attempt in response.attempts],
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
    write_run_receipt(receipt_path, {
        "experiment_id": runtime["experiment_id"], "runtime_sha256": sha256_file(args.runtime),
        "server_identity": runtime["model"], "request_ledger": [a for row in rows for a in row["attempts"]],
        "artifact_index_sha256": sha256_file(index_path),
        "budget_totals": {"calls_used": len(rows), "audio_seconds_used": sum(float(c["duration_s"]) for c in runtime["clips"]), **runtime["budget"]},
    }, repo_root=ROOT, run_id="e-material-lhcp-development-pass0-v1")
    print(json.dumps({**summary, "index_sha256": sha256_file(index_path), "receipt_sha256": sha256_file(receipt_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
