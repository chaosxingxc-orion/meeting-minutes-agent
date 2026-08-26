#!/usr/bin/env python3
"""Prebuilt structural reader for the LHCP development front-end flight."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
import wave


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


def validate_slice_document(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    meetings = document.get("meetings", [])
    if len(meetings) != 25:
        errors.append("expected 25 slice meetings")
    for meeting in meetings:
        manifest = meeting.get("slice_manifest", {})
        entries = manifest.get("entries", [])
        if manifest.get("mode") != "turn_aware" or manifest.get("turn_provenance") != "tool-diar":
            errors.append(f"slice provenance mismatch: {meeting.get('meeting_id')}")
        if not entries or [row.get("index") for row in entries] != list(range(len(entries))):
            errors.append(f"slice index mismatch: {meeting.get('meeting_id')}")
        if any(float(row["end"]) - float(row["start"]) > 120.000000001 for row in entries):
            errors.append(f"oversized slice: {meeting.get('meeting_id')}")
    return errors


def validate(config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    root = windows_to_wsl(str(config["output_root"]))
    conversion_path = root / "conversion-manifest.json"
    flight_path = root / "flight-summary.json"
    slices_path = root / "slice-manifest.json"
    errors: list[str] = []
    for path in (conversion_path, flight_path, slices_path):
        if not path.is_file():
            errors.append(f"missing external artifact: {path.name}")
    if errors:
        return {"errors": errors, "verdict": "FRONTEND_TRACE_INCOMPLETE"}
    conversion = json.loads(conversion_path.read_text(encoding="utf-8"))
    flight = json.loads(flight_path.read_text(encoding="utf-8"))
    slices = json.loads(slices_path.read_text(encoding="utf-8"))
    if len(conversion.get("files", [])) != 25:
        errors.append("conversion count mismatch")
    for row in conversion.get("files", []):
        path = root / str(row["wav_relative_path"])
        if not path.is_file() or path.stat().st_size != int(row["wav_bytes"]) or sha256_file(path) != row["wav_sha256"]:
            errors.append(f"converted WAV binding mismatch: {row.get('meeting_id')}")
            continue
        with wave.open(str(path), "rb") as audio:
            if audio.getnchannels() != 1 or audio.getframerate() != 16000 or audio.getsampwidth() != 2:
                errors.append(f"converted WAV format mismatch: {row.get('meeting_id')}")
    outcomes = flight.get("outcomes", [])
    if flight.get("contacts") != 25 or flight.get("successful_contacts") != 25 or len(outcomes) != 25:
        errors.append("flight contact closure mismatch")
    for row in outcomes:
        meeting_id = str(row.get("meeting_id"))
        rttm = root / "rttm" / f"{meeting_id}.rttm"
        receipt = root / "contact-receipts" / f"{meeting_id}.json"
        log = root / "logs" / f"{meeting_id}.log"
        if not row.get("ok") or int(row.get("turn_count", 0)) <= 0:
            errors.append(f"failed or empty RTTM: {meeting_id}")
        if not rttm.is_file() or sha256_file(rttm) != row.get("rttm_sha256"):
            errors.append(f"RTTM hash mismatch: {meeting_id}")
        if not receipt.is_file() or not log.is_file() or sha256_file(log) != row.get("log_sha256"):
            errors.append(f"contact artifact mismatch: {meeting_id}")
    errors.extend(validate_slice_document(slices))
    total_slices = 0
    total_seconds = 0.0
    for meeting in slices.get("meetings", []):
        meeting_id = str(meeting["meeting_id"])
        manifest = meeting["slice_manifest"]
        for row in manifest["entries"]:
            path = root / "slices" / meeting_id / str(row["filename"])
            if not path.is_file() or sha256_file(path) != row["sha256"]:
                errors.append(f"slice hash mismatch: {meeting_id}/{row['filename']}")
            total_slices += 1
            total_seconds += float(row["end"]) - float(row["start"])
    counts = slices.get("counts", {})
    if counts.get("slices") != total_slices or abs(float(counts.get("slice_audio_seconds", 0)) - total_seconds) > 0.001:
        errors.append("slice aggregate mismatch")
    if any(int(counts.get(key, -1)) != 0 for key in ("reference_reads", "confirmation_reads", "omni_calls")):
        errors.append("firewall count mismatch")
    return {
        "schema": "material-lhcp-development-frontend-validation-v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": sha256_file(config_path),
        "artifact_hashes": {
            "conversion_manifest_sha256": sha256_file(conversion_path),
            "flight_summary_sha256": sha256_file(flight_path),
            "slice_manifest_sha256": sha256_file(slices_path),
        },
        "counts": {
            "converted_wavs": len(conversion.get("files", [])),
            "sortformer_contacts": len(outcomes),
            "successful_rttms": sum(bool(row.get("ok")) for row in outcomes),
            "slices": total_slices,
            "slice_audio_seconds": total_seconds,
            "reference_reads": 0,
            "confirmation_reads": 0,
            "omni_calls": 0,
        },
        "errors": errors,
        "verdict": "FRONTEND_TRACE_COMPLETE" if not errors else "FRONTEND_TRACE_INCOMPLETE",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError(f"output exists: {args.out}")
    result = validate(args.config.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0 if result["verdict"] == "FRONTEND_TRACE_COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
