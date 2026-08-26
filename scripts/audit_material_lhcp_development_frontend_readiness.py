#!/usr/bin/env python3
"""Zero-model readiness audit for the LHCP development front end."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def windows_to_wsl(value: str) -> Path:
    if len(value) >= 3 and value[1:3] == ":/":
        return Path(f"/mnt/{value[0].lower()}/{value[3:]}")
    return Path(value)


def audit(config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    inputs = config["inputs"]
    manifest_path = windows_to_wsl(str(inputs["audio_manifest"]))
    audio_root = windows_to_wsl(str(inputs["audio_root"]))
    locks = {
        "audio_manifest_sha256": manifest_path,
        "audio_validation_sha256": ROOT / "docs/checks/2026-08-26-material-lhcp-supply/development-audio-validation.json",
        "slicer_sha256": ROOT / "src/meeting_minutes_agent/chunking/slicer.py",
        "rttm_parser_sha256": ROOT / "src/meeting_minutes_agent/chunking/rttm.py",
        "chunking_constants_sha256": ROOT / "src/meeting_minutes_agent/chunking/constants.py",
        "runner_sha256": ROOT / "scripts/run_material_lhcp_development_frontend.py",
        "reader_sha256": ROOT / "scripts/validate_material_lhcp_development_frontend.py",
        "preregistration_sha256": ROOT / "docs/readiness/2026-08-26-material-lhcp-development-frontend-preregistration.md",
    }
    for field, path in locks.items():
        if not path.is_file() or sha256_file(path) != inputs[field]:
            errors.append(f"input lock mismatch: {field}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {"files": []}
    rows = manifest.get("files", [])
    if len(rows) != 25 or len({row.get("audio_path") for row in rows}) != 25:
        errors.append("audio roster is not 25 unique files")
    actual_seconds = 0.0
    for row in rows:
        path = (audio_root / str(row["relative_path"])).resolve()
        try:
            path.relative_to(audio_root.resolve())
        except ValueError:
            errors.append(f"audio path escape: {row.get('audio_path')}")
            continue
        if not path.is_file() or path.stat().st_size != int(row["bytes"]):
            errors.append(f"audio binding missing: {row.get('audio_path')}")
            continue
        if sha256_file(path) != row["sha256"]:
            errors.append(f"audio hash mismatch: {row.get('audio_path')}")
        actual_seconds += float(row["duration_s"])
    diarizer = config["diarizer"]
    conversion = config["conversion"]
    binary_locks = {
        "ffmpeg": (Path(str(conversion["binary"])), str(conversion["binary_sha256"])),
        "sortformer_binary": (Path(str(diarizer["binary_path"])), str(diarizer["binary_sha256"])),
        "sortformer_model": (Path(str(diarizer["model_path"])), str(diarizer["model_sha256"])),
    }
    for name, (path, digest) in binary_locks.items():
        if not path.is_file() or sha256_file(path) != digest:
            errors.append(f"binary lock mismatch: {name}")
    if int(diarizer["contacts"]) != 25:
        errors.append("Sortformer contact budget mismatch")
    if abs(float(diarizer["input_audio_seconds"]) - actual_seconds) > 0.001:
        errors.append("Sortformer audio-seconds budget mismatch")
    if config["slicing"] != {
        "mode": "turn_aware",
        "turn_provenance": "tool-diar",
        "target_seconds": 90,
        "minimum_seconds": 60,
        "maximum_seconds": 120,
        "snap_seconds": 3,
        "overlap_seconds": 0,
        "sample_rate_hz": 16000,
        "channels": 1,
        "sample_width_bytes": 2,
    }:
        errors.append("slicing lock mismatch")
    return {
        "schema": "material-lhcp-development-frontend-readiness-v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": sha256_file(config_path),
        "counts": {
            "development_wavs": len(rows),
            "input_audio_seconds": actual_seconds,
            "planned_sortformer_contacts": int(diarizer["contacts"]),
            "reference_reads": 0,
            "confirmation_reads": 0,
            "sortformer_contacts": 0,
            "omni_calls": 0,
        },
        "pass0_budget_status": "DEFERRED_UNTIL_COMPLETE_SLICE_MANIFEST",
        "errors": errors,
        "verdict": "FRONTEND_READY_AWAITING_TOOL_AUTHORIZATION" if not errors else "FRONTEND_NOT_READY",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError(f"output exists: {args.out}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    result = audit(config, args.config.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0 if result["verdict"] == "FRONTEND_READY_AWAITING_TOOL_AUTHORIZATION" else 2


if __name__ == "__main__":
    raise SystemExit(main())
