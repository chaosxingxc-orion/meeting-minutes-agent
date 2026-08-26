#!/usr/bin/env python3
"""Offline readback validator for the LHCP material-supply audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate(
    config: dict[str, Any], verdict: dict[str, Any], receipt: dict[str, Any], output_root: Path
) -> dict[str, Any]:
    errors: list[str] = []
    meetings = verdict.get("meetings", [])
    documents = verdict.get("documents", [])
    split_counts = Counter(str(row.get("split")) for row in meetings)
    failed = [row for row in meetings if not row.get("passed")]
    if len(meetings) != int(config["construction"]["expected_meetings"]):
        errors.append("meeting count differs")
    if dict(sorted(split_counts.items())) != dict(sorted(config["construction"]["expected_splits"].items())):
        errors.append("split counts differ")
    if len({row.get("audio_path") for row in meetings}) != len(meetings):
        errors.append("meeting identities are not unique")
    if verdict.get("failed_meeting_ids") != [row["audio_path"] for row in failed]:
        errors.append("failed meeting identities differ")
    if int(verdict["counts"]["failed_meetings"]) != len(failed):
        errors.append("failed meeting count differs")
    if int(verdict["counts"]["documents"]) != len(documents):
        errors.append("document count differs")
    if verdict.get("reference_reads") != 0 or verdict.get("audio_downloads") != 0:
        errors.append("reference or audio firewall differs")
    if verdict.get("model_contact") != {"pass0": 0, "embedding": 0, "omni": 0}:
        errors.append("model firewall differs")
    for name, binding in receipt.get("artifacts", {}).items():
        path = output_root / name
        if not path.exists() or path.stat().st_size != int(binding["bytes"]) or sha256_file(path) != binding["sha256"]:
            errors.append(f"artifact binding mismatch: {name}")
    expected_verdict = (
        "LHCP_ZERO_MODEL_MATERIAL_SUPPLY_READY"
        if len(meetings) == int(config["passing_gates"]["meetings"]) and not failed
        else "LHCP_ZERO_MODEL_MATERIAL_SUPPLY_INSUFFICIENT"
    )
    if verdict.get("verdict") != expected_verdict or receipt.get("verdict") != expected_verdict:
        errors.append("mechanical verdict differs")
    return {
        "schema": "material-lhcp-supply-validation-v1",
        "experiment_id": config["experiment_id"],
        "counts": {
            "meetings": len(meetings),
            "documents": len(documents),
            "failed_meetings": len(failed),
            "artifacts": len(receipt.get("artifacts", {})),
        },
        "source_verdict": verdict.get("verdict"),
        "errors": errors,
        "validation": "TRACE_COMPLETE" if not errors else "TRACE_INVALID",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--verdict", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError(f"output exists: {args.out}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    verdict = json.loads(args.verdict.read_text(encoding="utf-8"))
    receipt_path = args.output_root / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    validation = validate(config, verdict, receipt, args.output_root)
    bindings = {
        "config_sha256": sha256_file(args.config),
        "supply_receipt_sha256": sha256_file(receipt_path),
    }
    for field, actual in bindings.items():
        if verdict.get(field) != actual:
            validation["errors"].append(f"verdict binding mismatch: {field}")
    validation["validation"] = "TRACE_COMPLETE" if not validation["errors"] else "TRACE_INVALID"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(validation, indent=2))
    return 0 if not validation["errors"] else 3


if __name__ == "__main__":
    raise SystemExit(main())

