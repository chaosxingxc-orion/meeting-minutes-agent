#!/usr/bin/env python3
"""Validate the frozen LHCP overlap-safe reslice without reading references."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
import wave


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


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


def validate(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    source_root = windows_to_wsl(str(config["source_root"]))
    output_root = windows_to_wsl(str(config["output_root"]))
    manifest_path = output_root / "slice-manifest.json"
    errors: list[str] = []
    locks = {
        "source_conversion_manifest_sha256": source_root / "conversion-manifest.json",
        "source_flight_summary_sha256": source_root / "flight-summary.json",
        "source_failed_slice_manifest_sha256": source_root / "slice-manifest.json",
        "slicer_sha256": ROOT / "src/meeting_minutes_agent/chunking/slicer.py",
        "rttm_parser_sha256": ROOT / "src/meeting_minutes_agent/chunking/rttm.py",
        "chunking_constants_sha256": ROOT / "src/meeting_minutes_agent/chunking/constants.py",
        "runner_sha256": ROOT / "scripts/run_material_lhcp_slicer_overlap_fix.py",
        "validator_sha256": Path(__file__).resolve(),
        "preregistration_sha256": ROOT / "docs/readiness/2026-08-26-material-lhcp-slicer-overlap-fix-preregistration.md",
        "amendment_1_sha256": ROOT / "docs/readiness/2026-08-26-material-lhcp-slicer-overlap-fix-amendment-1.md",
    }
    for field, path in locks.items():
        if not path.is_file() or sha256_file(path) != str(config["inputs"][field]):
            errors.append(f"lock mismatch: {field}")
    if not manifest_path.is_file():
        errors.append("missing corrected slice manifest")
        manifest: dict[str, Any] = {"meetings": [], "counts": {}}
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("config_sha256") != sha256_file(config_path):
        errors.append("config hash mismatch")
    meetings = list(manifest.get("meetings", []))
    if len(meetings) != 25 or [row.get("position") for row in meetings] != list(range(25)):
        errors.append("meeting count or order mismatch")
    conversion_path = source_root / "conversion-manifest.json"
    flight_path = source_root / "flight-summary.json"
    conversion = json.loads(conversion_path.read_text(encoding="utf-8")) if conversion_path.is_file() else {"files": []}
    flight = json.loads(flight_path.read_text(encoding="utf-8")) if flight_path.is_file() else {"outcomes": []}
    converted = {str(row["meeting_id"]): row for row in conversion.get("files", [])}
    outcomes = {str(row["meeting_id"]): row for row in flight.get("outcomes", [])}
    total_slices = 0
    total_seconds = 0.0
    maximum_seconds = 0.0
    overlap_boundaries = 0
    for meeting in meetings:
        meeting_id = str(meeting.get("meeting_id"))
        source_row = converted.get(meeting_id)
        outcome = outcomes.get(meeting_id)
        if source_row is None or outcome is None:
            errors.append(f"missing source binding: {meeting_id}")
            continue
        wav_path = source_root / str(source_row["wav_relative_path"])
        rttm_path = source_root / "rttm" / f"{meeting_id}.rttm"
        if not wav_path.is_file() or sha256_file(wav_path) != source_row["wav_sha256"]:
            errors.append(f"source WAV mismatch: {meeting_id}")
        if not rttm_path.is_file() or sha256_file(rttm_path) != outcome["rttm_sha256"]:
            errors.append(f"source RTTM mismatch: {meeting_id}")
        if meeting.get("source_wav_sha256") != source_row["wav_sha256"]:
            errors.append(f"manifest WAV binding mismatch: {meeting_id}")
        if meeting.get("source_rttm_sha256") != outcome["rttm_sha256"]:
            errors.append(f"manifest RTTM binding mismatch: {meeting_id}")
        if meeting.get("planning_repeated") is not True:
            errors.append(f"planning repeat missing: {meeting_id}")
        slice_manifest = meeting.get("slice_manifest", {})
        entries = list(slice_manifest.get("entries", []))
        if not entries or [entry.get("index") for entry in entries] != list(range(len(entries))):
            errors.append(f"empty or non-contiguous slices: {meeting_id}")
        for left, right in zip(entries, entries[1:]):
            if float(left["end"]) - float(right["start"]) > 1e-9:
                overlap_boundaries += 1
                errors.append(f"adjacent slice overlap: {meeting_id}:{left['index']}->{right['index']}")
        for entry in entries:
            duration = float(entry["end"]) - float(entry["start"])
            if duration <= 0 or duration > 120.000000001:
                errors.append(f"invalid duration: {meeting_id}:{entry['index']}")
            path = output_root / "slices" / meeting_id / str(entry["filename"])
            if not path.is_file() or sha256_file(path) != entry["sha256"]:
                errors.append(f"slice hash mismatch: {meeting_id}:{entry['index']}")
            elif path.is_file():
                with wave.open(str(path), "rb") as audio:
                    if audio.getnchannels() != 1 or audio.getframerate() != 16000 or audio.getsampwidth() != 2:
                        errors.append(f"slice format mismatch: {meeting_id}:{entry['index']}")
            total_seconds += duration
            maximum_seconds = max(maximum_seconds, duration)
        total_slices += len(entries)
    counts = manifest.get("counts", {})
    if int(counts.get("new_slices", -1)) != total_slices:
        errors.append("aggregate slice count mismatch")
    if abs(float(counts.get("new_slice_audio_seconds", -1)) - total_seconds) > 1e-6:
        errors.append("aggregate slice seconds mismatch")
    if int(counts.get("old_slices", -1)) != 397:
        errors.append("old slice count binding mismatch")
    for field in ("sortformer_contacts", "reference_reads", "confirmation_reads", "pass0_calls", "embedding_calls", "omni_calls"):
        if int(counts.get(field, -1)) != 0:
            errors.append(f"forbidden contact count is nonzero: {field}")
    return {
        "schema": "material-lhcp-slicer-overlap-fix-validation-v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": sha256_file(config_path),
        "slice_manifest_sha256": sha256_file(manifest_path) if manifest_path.is_file() else None,
        "counts": {
            "meetings": len(meetings),
            "slices": total_slices,
            "slice_audio_seconds": total_seconds,
            "maximum_slice_seconds": maximum_seconds,
            "overlap_boundaries": overlap_boundaries,
            "sortformer_contacts": 0,
            "reference_reads": 0,
            "confirmation_reads": 0,
            "pass0_calls": 0,
            "embedding_calls": 0,
            "omni_calls": 0,
        },
        "errors": errors,
        "verdict": "SLICER_OVERLAP_FIX_TRACE_COMPLETE" if not errors else "SLICER_OVERLAP_FIX_VALIDATION_FAILED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = validate(args.config)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
