#!/usr/bin/env python3
"""Reference-blind admission audit for the material new-surface pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SEALED_FIELDS = frozenset({"reference_text", "answer_text"})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_metadata(path: Path, allowed_fields: set[str]) -> list[dict[str, Any]]:
    """Project discovery-safe fields without touching sealed field values."""

    projected: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        row = json.loads(line)
        missing_sealed = SEALED_FIELDS.difference(row)
        if missing_sealed:
            raise ValueError(f"metadata line {line_number} missing sealed fields")
        projected.append({field: row.get(field) for field in allowed_fields if field in row})
    return projected


def load_fincall_mapping(root: Path) -> dict[str, dict[str, str | int]]:
    mapping: dict[str, dict[str, str | int]] = {}
    for year in (2019, 2020, 2021):
        path = root / "fincall" / f"transcripts_{year}.json"
        rows = load_json(path)
        for call_id, row in rows.items():
            mapping[str(call_id)] = {
                "year": year,
                "mp3_id": str(row.get("mp3_id")),
                "ppt_id": str(row.get("ppt_id")),
            }
    return mapping


def split_rows(rows: list[dict[str, Any]], salt: str, development: int, confirmation: int) -> list[dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda row: hashlib.sha256(f"{salt}:{row['item_id']}".encode()).hexdigest(),
    )
    for index, row in enumerate(ordered):
        if index < development:
            row["split"] = "development"
        elif index < development + confirmation:
            row["split"] = "confirmation"
        else:
            row["split"] = "reserve"
        row["split_order_sha256"] = hashlib.sha256(
            f"{salt}:{row['item_id']}".encode()
        ).hexdigest()
    return ordered


def audit(config: dict[str, Any], root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    errors: list[str] = []
    hash_checks: list[dict[str, Any]] = []
    for relative, expected in config["source_pins"]["files"].items():
        path = root / relative
        actual = sha256_file(path) if path.exists() else None
        passed = actual == expected
        hash_checks.append({"path": relative, "expected_sha256": expected, "actual_sha256": actual, "passed": passed})
        if not passed:
            errors.append(f"source hash mismatch: {relative}")

    allowed = set(config["reference_firewall"]["discovery_allowed_fields"])
    metadata = load_metadata(root / "source-metadata" / "metadata.jsonl", allowed)
    public_mapping = {
        str(row["item_id"]): row
        for row in load_json(root / "source-metadata" / "selection_manifest.json")["public_item_mapping"]
    }
    quality = load_json(root / "source-metadata" / "QUALITY_REPORT.json")
    fincall = load_fincall_mapping(root)
    if quality.get("status") != "pass" or not quality.get("human_validation", {}).get("all_core_items_pass_all_gates"):
        errors.append("Core-100 human quality report is not passing")

    excluded = {str(row["item_id"]) for row in config["known_exposure_exclusions"]}
    scoped_years = {
        int(name.removeprefix("ppt_").removesuffix(".zip"))
        for name in config["source_pins"]["material_archives"]
    }
    admitted: list[dict[str, Any]] = []
    rejection_counts: dict[str, int] = {}

    def reject(reason: str) -> None:
        rejection_counts[reason] = rejection_counts.get(reason, 0) + 1

    for row in metadata:
        item_id = str(row.get("item_id"))
        call_id = str(row.get("call_id"))
        if item_id in excluded:
            reject("known_reference_exposure")
            continue
        mapped = fincall.get(call_id)
        if mapped is None:
            reject("missing_fincall_join")
            continue
        if int(mapped["year"]) not in scoped_years:
            reject("outside_frozen_year_scope")
            continue
        public = public_mapping.get(item_id)
        if public is None or str(public.get("call_id")) != call_id:
            reject("public_mapping_mismatch")
            continue
        if row.get("authentic_audio") is not True or row.get("same_speaker_within_item") is not True:
            reject("audio_or_speaker_gate_failed")
            continue
        if int(row.get("human_quality_gates_passed", 0)) != int(config["admission"]["required_human_quality_gates"]):
            reject("human_quality_gate_failed")
            continue

        audio_bindings: dict[str, dict[str, Any]] = {}
        audio_ok = True
        for role in config["admission"]["required_audio_roles"]:
            short_role = role.removesuffix("_audio")
            path = root / "audio" / f"{item_id}_{short_role}.wav"
            expected = str(row.get(f"{role}_sha256"))
            actual = sha256_file(path) if path.exists() else None
            audio_bindings[role] = {
                "relative_path": str(path.relative_to(root)).replace("\\", "/"),
                "sha256": actual,
                "duration_s": row.get(f"{short_role}_duration_s"),
            }
            if actual != expected:
                audio_ok = False
        if not audio_ok:
            reject("audio_missing_or_hash_mismatch")
            continue

        slide_path = root / "materials" / str(mapped["year"]) / f"{mapped['ppt_id']}.pdf"
        if not slide_path.exists() or slide_path.read_bytes()[:4] != b"%PDF":
            reject("same_call_slide_missing_or_invalid")
            continue
        admitted.append(
            {
                "item_id": item_id,
                "call_id": call_id,
                "exchange_index": row.get("exchange_index"),
                "year": mapped["year"],
                "mp3_id": mapped["mp3_id"],
                "ppt_id": mapped["ppt_id"],
                "slide": {
                    "relative_path": str(slide_path.relative_to(root)).replace("\\", "/"),
                    "sha256": sha256_file(slide_path),
                    "bytes": slide_path.stat().st_size,
                },
                "audio": audio_bindings,
                "selection_tranche": row.get("selection_tranche"),
                "boundary_repaired": row.get("boundary_repaired"),
            }
        )

    if len({row["call_id"] for row in admitted}) != len(admitted):
        errors.append("admitted call IDs are not unique")
    minimum = int(config["admission"]["minimum_admitted_items"])
    if len(admitted) < minimum:
        errors.append(f"admitted items below minimum: {len(admitted)} < {minimum}")

    frozen = split_rows(
        admitted,
        str(config["split"]["salt"]),
        int(config["split"]["development_items"]),
        int(config["split"]["confirmation_items"]),
    ) if not errors else []
    cohort = {
        "schema": "material-new-surface-frozen-cohort-v1",
        "experiment_id": config["experiment_id"],
        "surface": config["surface"]["name"],
        "reference_firewall": "reference_text and answer_text were not projected into this artifact",
        "items": frozen,
    }
    counts = {split: sum(row.get("split") == split for row in frozen) for split in ("development", "confirmation", "reserve")}
    verdict = {
        "schema": "material-new-surface-admission-verdict-v1",
        "experiment_id": config["experiment_id"],
        "hash_checks": hash_checks,
        "source_counts": {
            "metadata_items": len(metadata),
            "scoped_pre_exclusion": sum(
                str(row.get("call_id")) in fincall and int(fincall[str(row.get("call_id"))]["year"]) in scoped_years
                for row in metadata
            ),
            "admitted": len(admitted),
            "split": counts,
            "rejections": rejection_counts,
        },
        "reference_contact": 0,
        "model_contact": {"pass0": 0, "embedding": 0, "omni": 0},
        "errors": errors,
        "verdict": "NEW_SURFACE_COHORT_FROZEN" if not errors else "ADMISSION_INCOMPLETE",
    }
    return cohort, verdict


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--cohort-out", required=True, type=Path)
    parser.add_argument("--verdict-out", required=True, type=Path)
    args = parser.parse_args()
    for output in (args.cohort_out, args.verdict_out):
        if output.exists():
            raise ValueError(f"output exists: {output}")
    cohort, verdict = audit(load_json(args.config), args.dataset_root)
    config_sha256 = sha256_file(args.config)
    cohort["config_sha256"] = config_sha256
    verdict["config_sha256"] = config_sha256
    cohort_payload = json.dumps(cohort, indent=2, sort_keys=True) + "\n"
    verdict["cohort_sha256"] = hashlib.sha256(cohort_payload.encode("utf-8")).hexdigest() if not verdict["errors"] else None
    args.verdict_out.parent.mkdir(parents=True, exist_ok=True)
    args.verdict_out.write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    if verdict["verdict"] == "NEW_SURFACE_COHORT_FROZEN":
        args.cohort_out.parent.mkdir(parents=True, exist_ok=True)
        args.cohort_out.write_text(cohort_payload, encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": verdict["verdict"], "counts": verdict["source_counts"], "errors": verdict["errors"]}, indent=2))
    return 0 if verdict["verdict"] == "NEW_SURFACE_COHORT_FROZEN" else 3


if __name__ == "__main__":
    raise SystemExit(main())
