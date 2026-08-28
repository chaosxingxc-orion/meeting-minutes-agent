#!/usr/bin/env python3
"""Reference-blind structural reader for the LHCP-ASR development Pass0."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in (SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import read_material_new_surface_pass0 as base  # noqa: E402
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402


sha256_file = base.sha256_file


def read_flight(runtime_path: Path, output_root: Path) -> dict[str, Any]:
    runtime = base._load_json(runtime_path)
    if runtime.get("schema") != "material-lhcp-development-pass0-runtime-v1":
        raise ValueError("runtime schema mismatch")
    if runtime.get("content_hash") != config_hash({key: value for key, value in runtime.items() if key != "content_hash"}):
        raise ValueError("runtime content hash mismatch")
    if sha256_file(output_root / "runtime.json") != sha256_file(runtime_path):
        raise ValueError("runtime copy mismatch")

    index_path = output_root / "index.jsonl"
    raw = index_path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError("index is not newline-terminated")
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    if len(rows) != len(runtime["clips"]):
        raise ValueError(f"expected {len(runtime['clips'])} rows, got {len(rows)}")

    request_bytes = response_bytes = empty_outputs = 0
    usage_totals: dict[str, int] = {}
    meeting_counts: dict[str, int] = {}
    seen: set[str] = set()
    for position, (clip, row) in enumerate(zip(runtime["clips"], rows, strict=True)):
        expected = (position, clip["request_id"], clip["turn_id"], clip["audio_sha256"], clip["meeting_id"], clip["slice_index"])
        actual = (row.get("position"), row.get("request_id"), row.get("turn_id"), row.get("audio_sha256"), row.get("meeting_id"), row.get("slice_index"))
        if actual != expected or row.get("schema") != "material-lhcp-development-pass0-index-row-v1":
            raise ValueError(f"index identity drift at position {position}")
        if row["request_id"] in seen:
            raise ValueError(f"duplicate request id: {row['request_id']}")
        seen.add(row["request_id"])
        attempts = row.get("attempts")
        if not isinstance(attempts, list) or len(attempts) != 1:
            raise ValueError(f"attempt count drift: {row['request_id']}")
        attempt = attempts[0]
        if attempt.get("request_id") != row["request_id"] or attempt.get("outcome") != "ok" or attempt.get("retry_of") is not None:
            raise ValueError(f"attempt ledger drift: {row['request_id']}")
        request_raw = base._artifact(output_root, row["request_artifact"])
        response_raw = base._artifact(output_root, row["response_artifact"])
        request_bytes += len(request_raw)
        response_bytes += len(response_raw)
        base._validate_request(request_raw, runtime, clip)
        text, usage = base._validate_response(response_raw, row)
        empty_outputs += int(not text.strip())
        meeting_counts[clip["meeting_id"]] = meeting_counts.get(clip["meeting_id"], 0) + 1
        for key, value in usage.items():
            usage_totals[key] = usage_totals.get(key, 0) + value

    receipt = base._load_json(output_root / "receipt.json")
    if receipt.get("config_hash") != config_hash(receipt.get("config", {})):
        raise ValueError("receipt config hash mismatch")
    receipt_config = receipt["config"]
    if receipt_config.get("experiment_id") != runtime["experiment_id"]:
        raise ValueError("receipt experiment mismatch")
    if receipt_config.get("runtime_sha256") != sha256_file(runtime_path):
        raise ValueError("receipt runtime mismatch")
    if receipt_config.get("artifact_index_sha256") != sha256_file(index_path):
        raise ValueError("receipt index mismatch")
    if receipt_config.get("budget_totals", {}).get("calls_used") != len(rows):
        raise ValueError("receipt call total mismatch")

    return {
        "schema": "material-lhcp-development-pass0-structural-read-v1",
        "experiment_id": runtime["experiment_id"], "verdict": "PASS0_TRACE_COMPLETE",
        "reference_access": "NONE", "material_access": "NONE", "confirmation_access": "NONE",
        "meetings_completed": len(meeting_counts), "calls_expected": len(runtime["clips"]),
        "calls_completed": len(rows), "empty_outputs": empty_outputs,
        "nonempty_outputs": len(rows) - empty_outputs, "request_bytes": request_bytes,
        "response_bytes": response_bytes, "usage_totals": dict(sorted(usage_totals.items())),
        "runtime_sha256": sha256_file(runtime_path), "index_sha256": sha256_file(index_path),
        "receipt_sha256": sha256_file(output_root / "receipt.json"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = read_flight(args.runtime, args.output_root)
    if args.output is not None:
        base.write_json_exclusive(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
