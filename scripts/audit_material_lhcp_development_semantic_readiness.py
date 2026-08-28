#!/usr/bin/env python3
"""Fail-closed readiness audit for the LHCP semantic embedding flight."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402
from run_material_new_surface_embedding import sha256_file  # noqa: E402


def audit(
    runtime_path: Path,
    preregistration: Path,
    supply_root: Path,
    pass0_root: Path,
    model: Path,
    server_binary: Path,
    output_root: Path,
) -> dict[str, Any]:
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    expected_hash = config_hash({key: value for key, value in runtime.items() if key != "content_hash"})
    add("runtime_content_hash", runtime.get("content_hash") == expected_hash, expected_hash)
    bindings = {
        "preregistration_sha256": preregistration,
        "supply_receipt_sha256": supply_root / "receipt.json",
        "selected_candidates_sha256": supply_root / "selected-candidates.json",
        "derangement_sha256": supply_root / "derangement.json",
        "queries_sha256": supply_root / "queries.jsonl",
        "pass0_index_sha256": pass0_root / "index.jsonl",
        "pass0_receipt_sha256": pass0_root / "receipt.json",
        "model_sha256": model,
        "server_binary_sha256": server_binary,
        "runner_sha256": ROOT / "scripts/run_material_lhcp_development_semantic_gate.py",
        "helper_runner_sha256": ROOT / runtime["inputs"]["helper_runner_path"],
        "reader_sha256": ROOT / runtime["inputs"]["reader_path"],
        "trace_validator_sha256": ROOT / runtime["inputs"]["trace_validator_path"],
        "generic_trace_validator_sha256": ROOT / runtime["inputs"]["generic_trace_validator_path"],
        "readiness_auditor_sha256": Path(__file__).resolve(),
    }
    for field, path in bindings.items():
        exists = path.is_file()
        actual = sha256_file(path) if exists else None
        add(field, exists and actual == runtime["inputs"][field], {"exists": exists, "actual_sha256": actual})
    supply_receipt = json.loads((supply_root / "receipt.json").read_text(encoding="utf-8"))
    candidates = json.loads((supply_root / "selected-candidates.json").read_text(encoding="utf-8"))["candidates"]
    queries = (supply_root / "queries.jsonl").read_text(encoding="utf-8").splitlines()
    add(
        "supply_verdict",
        supply_receipt.get("verdict") == "LHCP_DEVELOPMENT_QUERY_SUPPLY_FROZEN"
        and supply_receipt.get("reference_reads") == 0
        and supply_receipt.get("confirmation_access") == 0,
        supply_receipt.get("verdict"),
    )
    add("candidate_count", len(candidates) == int(runtime["embedding"]["keys"]), len(candidates))
    add("query_count", len(queries) == int(runtime["embedding"]["queries"]), len(queries))
    expected_calls = (
        (int(runtime["embedding"]["keys"]) + int(runtime["embedding"]["batch_size"]) - 1)
        // int(runtime["embedding"]["batch_size"])
        + (int(runtime["embedding"]["queries"]) + int(runtime["embedding"]["batch_size"]) - 1)
        // int(runtime["embedding"]["batch_size"])
    )
    add("embedding_call_budget", expected_calls == int(runtime["embedding"]["maximum_calls"]), expected_calls)
    add("model_size", model.is_file() and model.stat().st_size == 639150592, model.stat().st_size if model.exists() else None)
    add("server_executable", server_binary.is_file() and os.access(server_binary, os.X_OK), str(server_binary))
    add("output_root_absent", not output_root.exists(), str(output_root))
    disk_parent = output_root.parent
    disk_parent.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(disk_parent).free
    add("external_free_space", free_bytes >= 5 * 1024**3, free_bytes)
    add("cuda_visible", shutil.which("nvidia-smi") is not None, shutil.which("nvidia-smi"))
    errors = [check["name"] for check in checks if not check["passed"]]
    return {
        "schema": "material-lhcp-development-semantic-readiness-v1",
        "experiment_id": runtime["experiment_id"],
        "checks": checks,
        "checks_passed": len(checks) - len(errors),
        "checks_total": len(checks),
        "errors": errors,
        "reference_access": "NONE",
        "confirmation_access": "NONE",
        "verdict": "LHCP_DEVELOPMENT_SEMANTIC_READY" if not errors else "LHCP_DEVELOPMENT_SEMANTIC_NOT_READY",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--supply-root", required=True, type=Path)
    parser.add_argument("--pass0-root", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--server-binary", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error(f"output exists: {args.out}")
    result = audit(
        args.runtime,
        args.preregistration,
        args.supply_root,
        args.pass0_root,
        args.model,
        args.server_binary,
        args.output_root,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "checks": f"{result['checks_passed']}/{result['checks_total']}", "errors": result["errors"]}, indent=2))
    return 0 if not result["errors"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
