#!/usr/bin/env python3
"""Validate the complete LHCP semantic-attribution trace and sidecars."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402
from meeting_minutes_agent.state.material_trace import validate_trace_row  # noqa: E402
from validate_material_new_surface_trace import (  # noqa: E402
    sha256_file,
    validate_artifact,
    validate_vector_artifact,
)


def validate_lhcp_trace(runtime: dict[str, Any], artifact_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    trace = artifact_root / "trace.jsonl"
    queries_path = artifact_root / "queries.jsonl"
    candidates_path = artifact_root / "selected-candidates.json"
    derangement_path = artifact_root / "derangement.json"
    receipt_path = artifact_root / "receipt.json"
    required = (trace, queries_path, candidates_path, derangement_path, receipt_path, artifact_root / "embedding-index.jsonl")
    missing = [path.name for path in required if not path.exists()]
    if missing:
        return {
            "schema": "material-lhcp-development-semantic-trace-validation-v1",
            "rows": 0,
            "errors": [f"missing artifacts: {','.join(missing)}"],
            "verdict": "TRACE_INVALID",
        }
    rows = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    queries = [json.loads(line) for line in queries_path.read_text(encoding="utf-8").splitlines()]
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))["candidates"]
    mapping = json.loads(derangement_path.read_text(encoding="utf-8"))["mapping"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    expected_rows = int(runtime["embedding"]["queries"])
    width = int(runtime["construction"]["key_width"])
    by_meeting = {
        meeting_id: {str(row["candidate_id"]) for row in candidates if str(row["meeting_id"]) == meeting_id}
        for meeting_id in mapping
    }
    if len(rows) != expected_rows or len(queries) != expected_rows:
        errors.append("trace/query row count differs")
    identities: set[tuple[str, str, str]] = set()
    for position, row in enumerate(rows):
        row_errors = validate_trace_row(row)
        errors.extend(f"line {position + 1}: {error}" for error in row_errors)
        identity = (str(row.get("item_id")), str(row.get("turn_id")), str(row.get("audio_role")))
        if identity in identities:
            errors.append(f"line {position + 1}: duplicate identity")
        identities.add(identity)
        if position >= len(queries):
            continue
        query = queries[position]
        meeting_id = str(query["meeting_id"])
        if (
            row.get("experiment_id") != runtime["experiment_id"]
            or row.get("trace_run_id") != runtime["trace_run_id"]
            or row.get("split") != "development"
            or row.get("item_id") != meeting_id
            or row.get("meeting_id") != meeting_id
            or row.get("turn_id") != query["turn_id"]
            or row.get("audio_role") != "transport_slice"
        ):
            errors.append(f"line {position + 1}: trace identity differs")
        if (
            row.get("pass0", {}).get("transcript_text") != query["transcript_text"]
            or row.get("pass0", {}).get("transcript_sha256") != query["transcript_sha256"]
            or row.get("retrieval", {}).get("query_text") != query["query_text"]
            or row.get("retrieval", {}).get("query_sha256") != query["query_sha256"]
        ):
            errors.append(f"line {position + 1}: query/Pass0 binding differs")
        if bool(row.get("runtime_context", {}).get("potentially_truncated")) != bool(query["potentially_truncated"]):
            errors.append(f"line {position + 1}: truncation marker differs")
        correct = row.get("retrieval", {}).get("candidates", [])
        control = row.get("deranged_control", {}).get("candidates", [])
        control_id = str(mapping[meeting_id])
        if len(correct) != width or {str(value["candidate_id"]) for value in correct} != by_meeting[meeting_id]:
            errors.append(f"line {position + 1}: correct candidate inventory differs")
        if (
            row.get("deranged_control", {}).get("meeting_id") != control_id
            or len(control) != width
            or {str(value["candidate_id"]) for value in control} != by_meeting[control_id]
        ):
            errors.append(f"line {position + 1}: deranged candidate inventory differs")
        bindings = row.get("artifact_bindings", {})
        for field, label in (("candidate_snapshot", "candidate snapshot"), ("query_supply", "query supply")):
            if field not in bindings:
                errors.append(f"line {position + 1}: missing {field}")
            else:
                errors.extend(
                    f"line {position + 1}: {error}"
                    for error in validate_artifact(artifact_root, bindings[field], label)
                )
        vector_expectations = (
            ("query_vector_sidecar", 1),
            ("correct_key_vector_sidecar", width),
            ("deranged_key_vector_sidecar", width),
        )
        for field, vector_rows in vector_expectations:
            if field not in bindings:
                errors.append(f"line {position + 1}: missing {field}")
                continue
            errors.extend(
                f"line {position + 1}: {error}"
                for error in validate_vector_artifact(
                    artifact_root,
                    bindings[field],
                    field,
                    expected_rows=vector_rows,
                    expected_dtype="float32",
                )
            )
        for field in ("request_artifact", "response_artifact"):
            errors.extend(
                f"line {position + 1}: {error}"
                for error in validate_artifact(artifact_root, row["pass0"][field], field)
            )
    batch_rows = (artifact_root / "embedding-index.jsonl").read_text(encoding="utf-8").splitlines()
    if len(batch_rows) != int(runtime["embedding"]["maximum_calls"]):
        errors.append("embedding batch count differs")
    if (
        receipt.get("trace_rows") != expected_rows
        or receipt.get("trace_sha256") != sha256_file(trace)
        or receipt.get("embedding_calls") != int(runtime["embedding"]["maximum_calls"])
        or receipt.get("embeddings") != int(runtime["embedding"]["keys"]) + expected_rows
        or receipt.get("dimension") != int(runtime["embedding"]["dimension_expected"])
    ):
        errors.append("receipt counts or trace binding differs")
    if (
        receipt.get("reference_reads") != 0
        or receipt.get("confirmation_access") != 0
        or receipt.get("omni_correction_calls") != 0
    ):
        errors.append("receipt firewall differs")
    return {
        "schema": "material-lhcp-development-semantic-trace-validation-v1",
        "trace_sha256": sha256_file(trace),
        "rows": len(rows),
        "unique_identities": len(identities),
        "embedding_calls": len(batch_rows),
        "vector_sidecars": len(list((artifact_root / "vectors").glob("*.npz"))) if (artifact_root / "vectors").exists() else 0,
        "reference_access": "NONE",
        "confirmation_access": "NONE",
        "errors": errors,
        "verdict": "TRACE_COMPLETE" if len(rows) == expected_rows and not errors else "TRACE_INVALID",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output exists: {args.output}")
    runtime = json.loads(args.runtime.read_text(encoding="utf-8"))
    expected_hash = config_hash({key: value for key, value in runtime.items() if key != "content_hash"})
    if runtime.get("content_hash") != expected_hash:
        raise ValueError("runtime content hash mismatch")
    result = validate_lhcp_trace(runtime, args.artifact_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "rows": result["rows"], "errors": result["errors"][:10]}, indent=2))
    return 0 if result["verdict"] == "TRACE_COMPLETE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
