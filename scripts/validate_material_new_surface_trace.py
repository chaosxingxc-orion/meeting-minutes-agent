#!/usr/bin/env python3
"""Fail-closed validator for prospectively persisted material dispatch traces."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from meeting_minutes_agent.state.material_trace import validate_trace_row  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_artifact(root: Path, binding: dict[str, Any], label: str) -> list[str]:
    path = root / str(binding["relative_path"])
    if not path.exists():
        return [f"missing {label} artifact: {binding['relative_path']}"]
    errors: list[str] = []
    if path.stat().st_size != int(binding["bytes"]):
        errors.append(f"{label} byte count mismatch")
    if sha256_file(path) != binding["sha256"]:
        errors.append(f"{label} sha256 mismatch")
    return errors


def validate_vector_artifact(
    root: Path,
    binding: dict[str, Any],
    label: str,
    *,
    expected_rows: int | None,
    expected_dtype: str,
) -> list[str]:
    errors = validate_artifact(root, binding, label)
    if errors:
        return errors
    path = root / str(binding["relative_path"])
    if path.suffix != ".npz":
        return [f"{label} must be an npz sidecar"]
    import numpy as np

    with np.load(path, allow_pickle=False) as archive:
        key = str(binding["array_key"])
        if key not in archive:
            return [f"{label} array key missing: {key}"]
        array = archive[key]
    if array.ndim not in (1, 2):
        errors.append(f"{label} must contain a 1D or 2D array")
        return errors
    if int(array.shape[-1]) != int(binding["dimension"]):
        errors.append(f"{label} vector dimension mismatch")
    rows = 1 if array.ndim == 1 else int(array.shape[0])
    if expected_rows is not None and rows != expected_rows:
        errors.append(f"{label} vector row count mismatch")
    if str(array.dtype) != expected_dtype:
        errors.append(f"{label} vector dtype mismatch")
    vector_sha256 = hashlib.sha256(array.tobytes(order="C")).hexdigest()
    if vector_sha256 != binding["vector_sha256"]:
        errors.append(f"{label} vector sha256 mismatch")
    return errors


def validate_trace(trace: Path, artifact_root: Path, cohort: dict[str, Any]) -> dict[str, Any]:
    assignments = {str(row["item_id"]): str(row["split"]) for row in cohort["items"]}
    identities: set[tuple[str, str, str]] = set()
    errors: list[str] = []
    rows = 0
    by_split: dict[str, int] = {}
    for line_number, line in enumerate(trace.read_text(encoding="utf-8").splitlines(), 1):
        row = json.loads(line)
        rows += 1
        row_errors = validate_trace_row(row)
        errors.extend(f"line {line_number}: {error}" for error in row_errors)
        identity = (str(row.get("item_id")), str(row.get("turn_id")), str(row.get("audio_role")))
        if identity in identities:
            errors.append(f"line {line_number}: duplicate identity {identity}")
        identities.add(identity)
        item_id = str(row.get("item_id"))
        if assignments.get(item_id) != row.get("split") or row.get("split") == "reserve":
            errors.append(f"line {line_number}: split assignment mismatch")
        by_split[str(row.get("split"))] = by_split.get(str(row.get("split")), 0) + 1
        bindings = row.get("artifact_bindings", {})
        if "candidate_snapshot" in bindings:
            errors.extend(f"line {line_number}: {error}" for error in validate_artifact(artifact_root, bindings["candidate_snapshot"], "candidate_snapshot"))
        vector_expectations = (
            ("query_vector_sidecar", 1),
            ("correct_key_vector_sidecar", len(row.get("retrieval", {}).get("candidates", []))),
            ("deranged_key_vector_sidecar", len(row.get("deranged_control", {}).get("candidates", []))),
        )
        for field, expected_rows in vector_expectations:
            if field in bindings:
                vector_errors = validate_vector_artifact(
                    artifact_root,
                    bindings[field],
                    field,
                    expected_rows=expected_rows,
                    expected_dtype=str(row.get("retrieval", {}).get("score_dtype")),
                )
                errors.extend(f"line {line_number}: {error}" for error in vector_errors)
        for scope, field in ((row.get("pass0", {}), "request_artifact"), (row.get("pass0", {}), "response_artifact")):
            if field in scope:
                errors.extend(f"line {line_number}: {error}" for error in validate_artifact(artifact_root, scope[field], field))
    return {
        "schema": "material-new-surface-trace-validation-v1",
        "trace_sha256": sha256_file(trace),
        "rows": rows,
        "by_split": by_split,
        "unique_identities": len(identities),
        "errors": errors,
        "verdict": "TRACE_COMPLETE" if rows and not errors else "TRACE_INVALID",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError(f"output exists: {args.output}")
    result = validate_trace(args.trace, args.artifact_root, json.loads(args.cohort.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "rows": result["rows"], "errors": result["errors"][:10]}, indent=2))
    return 0 if result["verdict"] == "TRACE_COMPLETE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
