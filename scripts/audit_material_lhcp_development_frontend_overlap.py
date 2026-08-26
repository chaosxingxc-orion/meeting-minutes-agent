#!/usr/bin/env python3
"""Enforce the preregistered adjacent-slice zero-overlap gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit(document: dict[str, Any], *, epsilon: float = 1e-9) -> dict[str, Any]:
    overlaps: list[dict[str, Any]] = []
    for meeting in document.get("meetings", []):
        meeting_id = str(meeting["meeting_id"])
        entries = meeting["slice_manifest"]["entries"]
        for left, right in zip(entries, entries[1:]):
            overlap = float(left["end"]) - float(right["start"])
            if overlap > epsilon:
                overlaps.append(
                    {
                        "meeting_id": meeting_id,
                        "left_slice_index": int(left["index"]),
                        "left_end": float(left["end"]),
                        "right_slice_index": int(right["index"]),
                        "right_start": float(right["start"]),
                        "overlap_seconds": overlap,
                    }
                )
    affected = sorted({row["meeting_id"] for row in overlaps})
    total = sum(float(row["overlap_seconds"]) for row in overlaps)
    maximum = max((float(row["overlap_seconds"]) for row in overlaps), default=0.0)
    return {
        "schema": "material-lhcp-development-frontend-overlap-audit-v1",
        "experiment_id": document.get("experiment_id"),
        "epsilon_seconds": epsilon,
        "counts": {
            "meetings": len(document.get("meetings", [])),
            "slices": sum(len(row["slice_manifest"]["entries"]) for row in document.get("meetings", [])),
            "overlap_boundaries": len(overlaps),
            "affected_meetings": len(affected),
            "total_overlap_seconds": total,
            "maximum_overlap_seconds": maximum,
            "reference_reads": 0,
            "confirmation_reads": 0,
            "omni_calls": 0,
        },
        "affected_meeting_ids": affected,
        "overlaps": overlaps,
        "verdict": (
            "FRONTEND_SLICE_ZERO_OVERLAP_GATE_FAILED"
            if overlaps
            else "FRONTEND_SLICE_ZERO_OVERLAP_GATE_PASSED"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice-manifest", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError(f"output exists: {args.out}")
    if sha256_file(args.slice_manifest) != args.expected_sha256:
        raise ValueError("slice manifest hash mismatch")
    document = json.loads(args.slice_manifest.read_text(encoding="utf-8"))
    result = audit(document)
    result["slice_manifest_sha256"] = args.expected_sha256
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "counts": result["counts"]}, indent=2))
    return 0 if result["verdict"] == "FRONTEND_SLICE_ZERO_OVERLAP_GATE_PASSED" else 3


if __name__ == "__main__":
    raise SystemExit(main())
