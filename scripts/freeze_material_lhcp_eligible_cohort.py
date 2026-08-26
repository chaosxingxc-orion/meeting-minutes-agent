#!/usr/bin/env python3
"""Freeze the pre-model material-compatible LHCP cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SPLIT_ORDER = {"dev_2020": 0, "dev_2022": 1, "test_2020": 2, "test_2022": 3}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cohort_role(split: str) -> str:
    if split.startswith("dev_"):
        return "development"
    if split.startswith("test_"):
        return "confirmation"
    raise ValueError(f"unexpected split: {split}")


def build(
    config: dict[str, Any], admission: dict[str, Any], supply: dict[str, Any], validation: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    errors: list[str] = []
    if supply.get("verdict") != "LHCP_ZERO_MODEL_MATERIAL_SUPPLY_INSUFFICIENT":
        errors.append("unexpected source supply verdict")
    if validation.get("validation") != "TRACE_COMPLETE" or validation.get("errors"):
        errors.append("source supply trace is not complete")
    admission_by_id = {str(row["audio_path"]): row for row in admission.get("items", [])}
    supply_by_id = {str(row["audio_path"]): row for row in supply.get("meetings", [])}
    if set(admission_by_id) != set(supply_by_id):
        errors.append("admission and supply identities differ")
    expected_exclusions = set(config["eligibility"]["excluded_audio_paths"])
    actual_exclusions = {audio_path for audio_path, row in supply_by_id.items() if not row.get("passed")}
    if actual_exclusions != expected_exclusions:
        errors.append(f"mechanical exclusions differ: {sorted(actual_exclusions)}")

    items = []
    exclusions = []
    for audio_path in sorted(
        admission_by_id,
        key=lambda value: (
            SPLIT_ORDER[str(admission_by_id[value]["split"])],
            int(admission_by_id[value]["contribution_friendly_id"]),
        ),
    ):
        admitted = admission_by_id[audio_path]
        eligibility = supply_by_id[audio_path]
        if audio_path in actual_exclusions:
            exclusions.append(
                {
                    "audio_path": audio_path,
                    "split": admitted["split"],
                    "reason": "pre_model_material_parser_incompatible",
                    "failure_reasons": eligibility["failure_reasons"],
                    "candidate_count": eligibility["candidate_count"],
                    "visible_characters": eligibility["visible_characters"],
                }
            )
            continue
        items.append(
            {
                **admitted,
                "cohort_role": cohort_role(str(admitted["split"])),
                "eligibility": {
                    "policy": "pre_model_material_readability_and_supply_v1",
                    "readable_documents": eligibility["readable_documents"],
                    "visible_characters": eligibility["visible_characters"],
                    "candidate_count": eligibility["candidate_count"],
                },
            }
        )

    role_counts = {
        role: sum(row["cohort_role"] == role for row in items)
        for role in ("development", "confirmation")
    }
    split_counts = {
        split: sum(row["split"] == split for row in items)
        for split in SPLIT_ORDER
    }
    expected_counts = config["passing_gates"]
    actual_counts = {
        "eligible_meetings": len(items),
        "development_meetings": role_counts["development"],
        "confirmation_meetings": role_counts["confirmation"],
        "excluded_meetings": len(exclusions),
    }
    for field, expected in expected_counts.items():
        if actual_counts[field] != int(expected):
            errors.append(f"count differs for {field}: {actual_counts[field]} != {expected}")
    if len({row["audio_path"] for row in items}) != len(items):
        errors.append("eligible audio paths are not unique")
    if any(not row["eligibility"]["candidate_count"] >= int(config["eligibility"]["minimum_candidates"]) for row in items):
        errors.append("eligible cohort contains a candidate-gate failure")

    cohort = {
        "schema": "material-lhcp-eligible-cohort-v1",
        "experiment_id": config["experiment_id"],
        "evidence_tier": config["evidence_tier"],
        "claim_boundary": "70 pre-model material-compatible talks; not the complete 72-talk release",
        "reference_reads": 0,
        "model_contact": {"pass0": 0, "embedding": 0, "omni": 0},
        "counts": {**actual_counts, "splits": split_counts},
        "exclusions": exclusions,
        "items": items,
    }
    verdict = {
        "schema": "material-lhcp-eligible-cohort-verdict-v1",
        "experiment_id": config["experiment_id"],
        "counts": cohort["counts"],
        "excluded_audio_paths": [row["audio_path"] for row in exclusions],
        "reference_reads": 0,
        "model_contact": {"pass0": 0, "embedding": 0, "omni": 0},
        "errors": errors,
        "verdict": "LHCP_70_TALK_ELIGIBLE_COHORT_FROZEN" if not errors else "LHCP_ELIGIBLE_COHORT_INCOMPLETE",
    }
    return cohort, verdict


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--admission-manifest", required=True, type=Path)
    parser.add_argument("--supply-verdict", required=True, type=Path)
    parser.add_argument("--supply-validation", required=True, type=Path)
    parser.add_argument("--cohort-out", required=True, type=Path)
    parser.add_argument("--verdict-out", required=True, type=Path)
    args = parser.parse_args()
    for output in (args.cohort_out, args.verdict_out):
        if output.exists():
            raise ValueError(f"output exists: {output}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    source_paths = {
        "admission_manifest_sha256": args.admission_manifest,
        "supply_verdict_sha256": args.supply_verdict,
        "supply_validation_sha256": args.supply_validation,
        "cohort_builder_sha256": Path(__file__).resolve(),
    }
    for field, path in source_paths.items():
        if sha256_file(path) != config["inputs"][field]:
            raise ValueError(f"input hash mismatch: {field}")
    cohort, verdict = build(
        config,
        json.loads(args.admission_manifest.read_text(encoding="utf-8")),
        json.loads(args.supply_verdict.read_text(encoding="utf-8")),
        json.loads(args.supply_validation.read_text(encoding="utf-8")),
    )
    config_sha256 = sha256_file(args.config)
    cohort["config_sha256"] = config_sha256
    cohort_payload = json.dumps(cohort, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    verdict["config_sha256"] = config_sha256
    verdict["cohort_sha256"] = hashlib.sha256(cohort_payload.encode("utf-8")).hexdigest()
    args.cohort_out.parent.mkdir(parents=True, exist_ok=True)
    args.cohort_out.write_text(cohort_payload, encoding="utf-8", newline="\n")
    args.verdict_out.parent.mkdir(parents=True, exist_ok=True)
    args.verdict_out.write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"verdict": verdict["verdict"], "counts": verdict["counts"], "errors": verdict["errors"]}, indent=2))
    return 0 if not verdict["errors"] else 3


if __name__ == "__main__":
    raise SystemExit(main())

