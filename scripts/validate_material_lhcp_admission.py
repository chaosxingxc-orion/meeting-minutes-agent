#!/usr/bin/env python3
"""Offline readback validator for an LHCP metadata-only admission receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(
    config: dict[str, Any], manifest: dict[str, Any], verdict: dict[str, Any]
) -> dict[str, Any]:
    errors: list[str] = []
    items = manifest.get("items", [])
    config_sha256 = str(manifest.get("config_sha256"))
    if config_sha256 != str(verdict.get("config_sha256")):
        errors.append("config hash bindings disagree")
    if manifest.get("reference_firewall") != {
        "projected_hf_columns": ["audio.path"],
        "reference_reads": 0,
        "audio_body_reads": 0,
        "material_body_reads": 0,
    }:
        errors.append("reference firewall receipt differs")

    split_counts = Counter(str(row.get("split")) for row in items)
    if dict(sorted(split_counts.items())) != dict(sorted(config["huggingface"]["expected_splits"].items())):
        errors.append("split counts differ")
    paths = [str(row.get("audio_path")) for row in items]
    contribution_keys = [
        (int(row.get("event_id")), int(row.get("contribution_friendly_id"))) for row in items
    ]
    materials = [material for row in items for material in row.get("materials", [])]
    urls = [str(material.get("download_url")) for material in materials]
    checksums = [str(material.get("checksum")) for material in materials if material.get("checksum")]
    duplicate_urls = len(urls) - len(set(urls))
    duplicate_checksums = len(checksums) - len(set(checksums))
    uncovered = sum(not row.get("materials") for row in items)
    if len(items) != int(config["passing_gates"]["hf_rows"]):
        errors.append("item count differs")
    if len(paths) != len(set(paths)):
        errors.append("audio paths are not unique")
    if len(contribution_keys) != len(set(contribution_keys)):
        errors.append("contribution bindings are not unique")
    if uncovered:
        errors.append(f"rows without material: {uncovered}")
    if duplicate_urls:
        errors.append(f"duplicate material URLs: {duplicate_urls}")
    if duplicate_checksums:
        errors.append(f"duplicate material checksums: {duplicate_checksums}")
    if manifest.get("orphans"):
        errors.append("manifest contains orphan rows")
    if manifest.get("ambiguities"):
        errors.append("manifest contains ambiguous rows")

    return {
        "schema": "material-lhcp-admission-validation-v1",
        "experiment_id": config["experiment_id"],
        "counts": {
            "items": len(items),
            "unique_audio_paths": len(set(paths)),
            "unique_contributions": len(set(contribution_keys)),
            "material_covered_rows": len(items) - uncovered,
            "material_attachments": len(materials),
            "unique_material_urls": len(set(urls)),
            "unique_material_checksums": len(set(checksums)),
            "duplicate_material_urls": duplicate_urls,
            "duplicate_material_checksums": duplicate_checksums,
        },
        "source_verdict": verdict.get("verdict"),
        "errors": errors,
        "validation": "TRACE_COMPLETE" if not errors else "TRACE_INVALID",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--verdict", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError(f"output exists: {args.out}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    manifest_payload = args.manifest.read_bytes()
    manifest = json.loads(manifest_payload)
    verdict = json.loads(args.verdict.read_text(encoding="utf-8"))
    validation = validate(config, manifest, verdict)
    if sha256_file(args.config) != manifest.get("config_sha256"):
        validation["errors"].append("config file hash mismatch")
    if sha256_bytes(manifest_payload) != verdict.get("manifest_sha256"):
        validation["errors"].append("manifest file hash mismatch")
    validation["validation"] = "TRACE_COMPLETE" if not validation["errors"] else "TRACE_INVALID"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(validation, indent=2))
    return 0 if not validation["errors"] else 3


if __name__ == "__main__":
    raise SystemExit(main())

