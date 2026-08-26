#!/usr/bin/env python3
"""Reference-blind structural reader for the new-surface Pass0 flight."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.heads.transcribe_attribute import (  # noqa: E402
    TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE,
)
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _artifact(root: Path, binding: dict[str, Any]) -> bytes:
    path = root / binding["relative_path"]
    payload = path.read_bytes()
    if len(payload) != binding["bytes"] or sha256_bytes(payload) != binding["sha256"]:
        raise ValueError(f"artifact binding mismatch: {binding['relative_path']}")
    return payload


def _validate_request(raw: bytes, runtime: dict[str, Any], clip: dict[str, Any]) -> None:
    request = json.loads(raw.decode("utf-8"))
    if set(request) != {"messages", *runtime["decoding"]}:
        raise ValueError(f"unexpected request fields: {clip['request_id']}")
    for key, value in runtime["decoding"].items():
        if request.get(key) != value:
            raise ValueError(f"decoding drift: {clip['request_id']} {key}")
    messages = request.get("messages")
    if not isinstance(messages, list) or len(messages) != 2:
        raise ValueError(f"message shape drift: {clip['request_id']}")
    if messages[0] != {"role": "system", "content": TRANSCRIBE_ONLY_SYSTEM_INSTRUCTION_TEMPLATE}:
        raise ValueError(f"system prompt drift: {clip['request_id']}")
    content = messages[1].get("content") if messages[1].get("role") == "user" else None
    if not isinstance(content, list) or len(content) != 1 or content[0].get("type") != "input_audio":
        raise ValueError(f"request was not audio-only: {clip['request_id']}")
    audio = content[0].get("input_audio")
    if not isinstance(audio, dict) or set(audio) != {"data", "format"} or audio["format"] != "wav":
        raise ValueError(f"audio envelope drift: {clip['request_id']}")
    try:
        decoded = base64.b64decode(audio["data"], validate=True)
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid audio base64: {clip['request_id']}") from error
    if sha256_bytes(decoded) != clip["audio_sha256"]:
        raise ValueError(f"wire audio hash mismatch: {clip['request_id']}")


def _validate_response(raw: bytes, row: dict[str, Any]) -> tuple[str, dict[str, int]]:
    response = json.loads(raw.decode("utf-8"))
    try:
        text = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(f"response shape drift: {row['request_id']}") from error
    if not isinstance(text, str) or text != row["transcript_text"]:
        raise ValueError(f"response transcript mismatch: {row['request_id']}")
    if sha256_bytes(text.encode("utf-8")) != row["transcript_sha256"]:
        raise ValueError(f"transcript hash mismatch: {row['request_id']}")
    usage = {
        str(key): int(value)
        for key, value in dict(response.get("usage", {})).items()
        if not isinstance(value, dict)
    }
    if usage != row["usage"]:
        raise ValueError(f"usage mismatch: {row['request_id']}")
    return text, usage


def read_flight(runtime_path: Path, output_root: Path) -> dict[str, Any]:
    runtime = _load_json(runtime_path)
    if runtime.get("schema") != "material-new-surface-pass0-runtime-v1":
        raise ValueError("runtime schema mismatch")
    without_hash = {key: value for key, value in runtime.items() if key != "content_hash"}
    if runtime.get("content_hash") != config_hash(without_hash):
        raise ValueError("runtime content hash mismatch")
    if sha256_file(output_root / "runtime.json") != sha256_file(runtime_path):
        raise ValueError("runtime copy mismatch")

    index_path = output_root / "index.jsonl"
    index_raw = index_path.read_bytes()
    if index_raw and not index_raw.endswith(b"\n"):
        raise ValueError("index is not newline-terminated")
    rows = [json.loads(line) for line in index_raw.decode("utf-8").splitlines()]
    if len(rows) != len(runtime["clips"]):
        raise ValueError(f"expected {len(runtime['clips'])} rows, got {len(rows)}")

    request_bytes = 0
    response_bytes = 0
    empty_outputs = 0
    usage_totals: dict[str, int] = {}
    seen: set[str] = set()
    for position, (clip, row) in enumerate(zip(runtime["clips"], rows, strict=True)):
        expected_identity = (position, clip["request_id"], clip["turn_id"], clip["audio_sha256"])
        actual_identity = (row.get("position"), row.get("request_id"), row.get("turn_id"), row.get("audio_sha256"))
        if actual_identity != expected_identity or row.get("schema") != "material-new-surface-pass0-index-row-v1":
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
        request_raw = _artifact(output_root, row["request_artifact"])
        response_raw = _artifact(output_root, row["response_artifact"])
        request_bytes += len(request_raw)
        response_bytes += len(response_raw)
        _validate_request(request_raw, runtime, clip)
        text, usage = _validate_response(response_raw, row)
        empty_outputs += int(not text.strip())
        for key, value in usage.items():
            usage_totals[key] = usage_totals.get(key, 0) + value

    receipt = _load_json(output_root / "receipt.json")
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
        "schema": "material-new-surface-pass0-structural-read-v1",
        "experiment_id": runtime["experiment_id"],
        "verdict": "PASS0_TRACE_COMPLETE",
        "reference_access": "NONE",
        "calls_expected": len(runtime["clips"]),
        "calls_completed": len(rows),
        "empty_outputs": empty_outputs,
        "nonempty_outputs": len(rows) - empty_outputs,
        "request_bytes": request_bytes,
        "response_bytes": response_bytes,
        "usage_totals": dict(sorted(usage_totals.items())),
        "runtime_sha256": sha256_file(runtime_path),
        "index_sha256": sha256_file(index_path),
        "receipt_sha256": sha256_file(output_root / "receipt.json"),
    }


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = read_flight(args.runtime, args.output_root)
    if args.output is not None:
        write_json_exclusive(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
