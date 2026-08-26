#!/usr/bin/env python3
"""Offline validator for the frozen 70-talk LHCP eligible cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(config: dict[str, Any], cohort: dict[str, Any], verdict: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    items = cohort.get("items", [])
    exclusions = cohort.get("exclusions", [])
    role_counts = Counter(str(row.get("cohort_role")) for row in items)
    split_counts = Counter(str(row.get("split")) for row in items)
    expected_exclusions = set(config["eligibility"]["excluded_audio_paths"])
    actual_exclusions = {str(row.get("audio_path")) for row in exclusions}
    if len(items) != int(config["passing_gates"]["eligible_meetings"]):
        errors.append("eligible count differs")
    if role_counts != Counter(
        {
            "development": int(config["passing_gates"]["development_meetings"]),
            "confirmation": int(config["passing_gates"]["confirmation_meetings"]),
        }
    ):
        errors.append("role counts differ")
    expected_splits = {"dev_2020": 14, "dev_2022": 11, "test_2020": 13, "test_2022": 32}
    if dict(split_counts) != expected_splits:
        errors.append("eligible split counts differ")
    if actual_exclusions != expected_exclusions:
        errors.append("excluded identities differ")
    if set(row["audio_path"] for row in items) & actual_exclusions:
        errors.append("excluded identity remains eligible")
    if len({row["audio_path"] for row in items}) != len(items):
        errors.append("eligible identities are not unique")
    if any(row["cohort_role"] != ("development" if row["split"].startswith("dev_") else "confirmation") for row in items):
        errors.append("split-to-role mapping differs")
    if cohort.get("reference_reads") != 0 or cohort.get("model_contact") != {"pass0": 0, "embedding": 0, "omni": 0}:
        errors.append("cohort firewall differs")
    if verdict.get("reference_reads") != 0 or verdict.get("model_contact") != {"pass0": 0, "embedding": 0, "omni": 0}:
        errors.append("verdict firewall differs")
    if verdict.get("errors") or verdict.get("verdict") != "LHCP_70_TALK_ELIGIBLE_COHORT_FROZEN":
        errors.append("source verdict differs")
    return {
        "schema": "material-lhcp-eligible-cohort-validation-v1",
        "experiment_id": config["experiment_id"],
        "counts": {
            "eligible_meetings": len(items),
            "development_meetings": role_counts["development"],
            "confirmation_meetings": role_counts["confirmation"],
            "excluded_meetings": len(exclusions),
        },
        "errors": errors,
        "validation": "TRACE_COMPLETE" if not errors else "TRACE_INVALID",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--verdict", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError(f"output exists: {args.out}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    cohort = json.loads(args.cohort.read_text(encoding="utf-8"))
    verdict = json.loads(args.verdict.read_text(encoding="utf-8"))
    result = validate(config, cohort, verdict)
    if sha256_file(args.config) != cohort.get("config_sha256") or cohort.get("config_sha256") != verdict.get("config_sha256"):
        result["errors"].append("config hash binding differs")
    if sha256_file(args.cohort) != verdict.get("cohort_sha256"):
        result["errors"].append("cohort hash binding differs")
    result["validation"] = "TRACE_COMPLETE" if not result["errors"] else "TRACE_INVALID"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0 if not result["errors"] else 3


if __name__ == "__main__":
    raise SystemExit(main())

