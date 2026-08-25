#!/usr/bin/env python3
"""Reference-blind structural read for the material-gate Pass-0 flight."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--responses-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output exists: {args.output}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    meetings = []
    total = 0
    empty = 0
    retries = 0
    for meeting in manifest["meetings"]:
        file_id = str(meeting["file_id"])
        path = args.responses_dir / f"{file_id}-responses.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        expected = [int(turn["index"]) for turn in meeting["turns"]]
        observed = [int(row["turn_index"]) for row in rows]
        if observed != expected:
            raise ValueError(f"incomplete or reordered responses for {file_id}")
        if any(row.get("file_id") != file_id or row.get("outcome") != "ok" for row in rows):
            raise ValueError(f"invalid response identity/outcome for {file_id}")
        local_empty = sum(not str(row.get("text", "")).strip() for row in rows)
        local_retries = sum(max(0, len(row.get("attempts", [])) - 1) for row in rows)
        total += len(rows)
        empty += local_empty
        retries += local_retries
        meetings.append(
            {
                "file_id": file_id,
                "calls": len(rows),
                "empty_text": local_empty,
                "retry_attempts": local_retries,
                "responses_sha256": sha256_file(path),
            }
        )
    verdict = {
        "schema": "material-runtime-gate-ci-pass0-structural-read-v1",
        "experiment_id": manifest["experiment_id"],
        "runtime_content_hash": manifest["content_hash"],
        "calls": total,
        "expected_calls": manifest["budget"]["calls"],
        "empty_text": empty,
        "retry_attempts": retries,
        "meetings": meetings,
        "decision": "PASS0_COMPLETE" if total == manifest["budget"]["calls"] and empty == 0 else "PASS0_INVALID",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: verdict[key] for key in ("decision", "calls", "empty_text", "retry_attempts")}, indent=2))
    return 0 if verdict["decision"] == "PASS0_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
