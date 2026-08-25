#!/usr/bin/env python3
"""Audit whether Earnings-22 still contains a reference-unread cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("output directory exists; refusing to overwrite a frozen read")

    config = load_json(args.config)
    roster_path = resolve(str(config["roster"]))
    roster = load_json(roster_path)
    roster_ids = {str(row["file_id"]) for row in roster["meetings"]}

    reads = config["completed_lexical_reads"]
    discovery_cfg = reads["discovery"]
    discovery_path = resolve(str(discovery_cfg["manifest"]))
    discovery_manifest = load_json(discovery_path)
    discovery_ids = {
        str(row["file_id"])
        for row in discovery_manifest["inputs"]
        if row.get(str(discovery_cfg["selector_field"])) == discovery_cfg["selector_value"]
    }

    reserve_cfg = reads["reserve"]
    reserve_path = resolve(str(reserve_cfg["manifest"]))
    reserve_manifest = load_json(reserve_path)
    reserve_ids = {str(row["file_id"]) for row in reserve_manifest["inputs"]}
    read_ids = discovery_ids | reserve_ids
    unread_ids = sorted(roster_ids - read_ids)

    expected_discovery = int(discovery_cfg["expected_count"])
    expected_reserve = int(reserve_cfg["expected_count"])
    minimum = int(config["minimum_reference_unread_meetings"])
    integrity_ok = (
        len(roster_ids) == int(roster["meeting_count"])
        and len(discovery_ids) == expected_discovery
        and len(reserve_ids) == expected_reserve
        and not (discovery_ids & reserve_ids)
        and read_ids <= roster_ids
    )
    admitted = integrity_ok and len(unread_ids) >= minimum
    verdict = {
        "schema": "material-semantic-admission-verdict-v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": sha256_file(args.config),
        "inputs": {
            "roster": {"path": str(roster_path.relative_to(ROOT)), "sha256": sha256_file(roster_path)},
            "discovery_manifest": {
                "path": str(discovery_path.relative_to(ROOT)),
                "sha256": sha256_file(discovery_path),
            },
            "reserve_manifest": {
                "path": str(reserve_path.relative_to(ROOT)),
                "sha256": sha256_file(reserve_path),
            },
        },
        "counts": {
            "roster": len(roster_ids),
            "discovery_lexically_read": len(discovery_ids),
            "reserve_lexically_read": len(reserve_ids),
            "read_overlap": len(discovery_ids & reserve_ids),
            "lexically_read_union": len(read_ids),
            "reference_unread": len(unread_ids),
            "minimum_required": minimum,
        },
        "integrity_ok": integrity_ok,
        "reference_unread_file_ids": unread_ids,
        "admitted": admitted,
        "verdict": "ADMISSION_READY" if admitted else "ADMISSION_FAILED_NO_REFERENCE_UNREAD_MEETINGS",
        "dependent_runtime_gate": "ADMITTED" if admitted else "NOT_RUN_PREREQUISITE_FAILED",
        "model_calls": 0,
        "reference_content_reads": 0,
        "material_downloads": 0,
    }
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "verdict.json").write_text(
        json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(verdict["counts"], indent=2, sort_keys=True))
    print(verdict["verdict"])
    return 0 if integrity_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
