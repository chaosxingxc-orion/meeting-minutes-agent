#!/usr/bin/env python3
"""Fail-closed readiness audit for LHCP full-pool semantic extraction."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from download_material_lhcp_development_audio import sha256_file  # noqa: E402


def audit(runtime_path: Path, supply_root: Path, model: Path, server: Path, output_root: Path) -> dict[str, Any]:
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    bindings = {
        "preregistration_sha256": ROOT / str(runtime["inputs"]["preregistration_path"]),
        "supply_receipt_sha256": supply_root / "receipt.json",
        "candidates_sha256": supply_root / "candidates.json",
        "queries_sha256": supply_root / "queries.jsonl",
        "model_sha256": model,
        "server_binary_sha256": server,
        "helper_runner_sha256": ROOT / str(runtime["inputs"]["helper_runner_path"]),
        "runner_sha256": ROOT / "scripts/run_material_lhcp_full_pool_semantic_extractor.py",
        "reader_sha256": ROOT / str(runtime["inputs"]["reader_path"]),
        "readiness_auditor_sha256": Path(__file__).resolve(),
        "oracle_receipt_sha256": Path(str(runtime["inputs"]["oracle_receipt_path"])),
        "oracle_rows_sha256": Path(str(runtime["inputs"]["oracle_rows_path"])),
    }
    for field, path in bindings.items():
        exists = path.is_file()
        actual = sha256_file(path) if exists else None
        add(field, exists and actual == runtime["inputs"][field], {"exists": exists, "actual_sha256": actual})
    supply = json.loads((supply_root / "receipt.json").read_text(encoding="utf-8"))
    add("supply_verdict", supply.get("verdict") == "LHCP_FULL_POOL_SEMANTIC_SUPPLY_FROZEN", supply.get("verdict"))
    add("supply_firewall", supply.get("reference_reads") == 0 and supply.get("confirmation_access") == 0, supply)
    add("key_count", supply.get("keys") == int(runtime["embedding"]["keys"]), supply.get("keys"))
    add("query_count", supply.get("queries") == int(runtime["embedding"]["queries"]), supply.get("queries"))
    calls = (
        (int(runtime["embedding"]["keys"]) + int(runtime["embedding"]["batch_size"]) - 1) // int(runtime["embedding"]["batch_size"])
        + (int(runtime["embedding"]["queries"]) + int(runtime["embedding"]["batch_size"]) - 1) // int(runtime["embedding"]["batch_size"])
    )
    add("embedding_call_budget", calls == int(runtime["embedding"]["maximum_calls"]), calls)
    add("model_size", model.is_file() and model.stat().st_size == 639150592, model.stat().st_size if model.exists() else None)
    add("server_executable", server.is_file() and os.access(server, os.X_OK), str(server))
    add("output_root_absent", not output_root.exists(), str(output_root))
    output_root.parent.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(output_root.parent).free
    add("external_free_space", free >= 2 * 1024**3, free)
    add("cuda_visible", shutil.which("nvidia-smi") is not None, shutil.which("nvidia-smi"))
    errors = [row["name"] for row in checks if not row["passed"]]
    return {
        "schema": "material-lhcp-full-pool-semantic-readiness-v1",
        "experiment_id": runtime["experiment_id"],
        "checks": checks,
        "checks_passed": len(checks) - len(errors),
        "checks_total": len(checks),
        "errors": errors,
        "model_contact": 0,
        "confirmation_access": 0,
        "verdict": "LHCP_FULL_POOL_SEMANTIC_READY_AWAITING_AUTHORIZATION" if not errors else "LHCP_FULL_POOL_SEMANTIC_NOT_READY",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--supply-root", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--server-binary", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error(f"output exists: {args.out}")
    result = audit(args.runtime, args.supply_root, args.model, args.server_binary, args.output_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "checks": f"{result['checks_passed']}/{result['checks_total']}", "errors": result["errors"]}, indent=2))
    return 0 if not result["errors"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
