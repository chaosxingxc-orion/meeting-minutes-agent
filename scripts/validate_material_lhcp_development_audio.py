#!/usr/bin/env python3
"""Validate the frozen LHCP development-audio acquisition offline."""

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


def safe_external_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"external path escapes root: {relative}") from exc
    return path


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        return audio.getnframes() / audio.getframerate()


def validate(
    config_path: Path,
    cohort_path: Path,
    manifest_path: Path,
    receipt_path: Path,
    external_root: Path,
) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if receipt.get("verdict") != "LHCP_DEVELOPMENT_AUDIO_ACQUIRED":
        errors.append("acquisition verdict mismatch")
    if receipt.get("config_sha256") != sha256_file(config_path):
        errors.append("receipt config hash mismatch")
    if receipt.get("download_manifest_sha256") != sha256_file(manifest_path):
        errors.append("receipt manifest hash mismatch")
    if manifest.get("projected_columns") != ["audio.path", "audio.bytes"]:
        errors.append("projected column firewall mismatch")
    if manifest.get("forbidden_columns") != ["transcription"]:
        errors.append("forbidden column firewall mismatch")
    expected = {
        str(row["audio_path"])
        for row in cohort["items"]
        if row["cohort_role"] == "development"
    }
    rows = manifest.get("files", [])
    actual = [str(row.get("audio_path")) for row in rows]
    if len(expected) != 25 or len(actual) != 25 or len(set(actual)) != 25 or set(actual) != expected:
        errors.append("development audio identity closure mismatch")
    total_bytes = 0
    total_seconds = 0.0
    hashes: set[str] = set()
    for row in rows:
        try:
            path = safe_external_path(external_root, str(row["relative_path"]))
            if not path.is_file():
                raise ValueError("file missing")
            if path.stat().st_size != int(row["bytes"]):
                raise ValueError("byte count mismatch")
            digest = sha256_file(path)
            if digest != row["sha256"]:
                raise ValueError("SHA-256 mismatch")
            duration = wav_duration(path)
            if duration <= 0 or abs(duration - float(row["duration_s"])) > 0.001:
                raise ValueError("decoded duration mismatch")
            if row["split"] not in {"dev_2020", "dev_2022"}:
                raise ValueError("non-development split")
            total_bytes += path.stat().st_size
            total_seconds += duration
            hashes.add(digest)
        except (KeyError, OSError, ValueError, wave.Error) as exc:
            errors.append(f"{row.get('audio_path', '<unknown>')}: {exc}")
    transfers = manifest.get("transfers", [])
    if len(transfers) != 6 or any(str(row.get("file", "")).startswith("longform/test_") for row in transfers):
        errors.append("source-file firewall mismatch")
    counts = receipt.get("counts", {})
    expected_counts = {
        "audio_files": len(rows),
        "audio_bytes": total_bytes,
        "audio_seconds": total_seconds,
        "unique_sha256": len(hashes),
        "source_files": len(transfers),
        "remote_bytes": sum(int(row["remote_bytes"]) for row in transfers),
        "transferred_bytes": sum(int(row["transferred_bytes"]) for row in transfers),
    }
    for key, value in expected_counts.items():
        recorded = counts.get(key)
        if isinstance(value, float):
            if recorded is None or abs(float(recorded) - value) > 0.001:
                errors.append(f"receipt count mismatch: {key}")
        elif recorded != value:
            errors.append(f"receipt count mismatch: {key}")
    if receipt.get("reference_reads") != 0 or receipt.get("confirmation_audio_reads") != 0:
        errors.append("reference or confirmation firewall mismatch")
    if any(int(value) != 0 for value in receipt.get("model_contact", {}).values()):
        errors.append("model-contact firewall mismatch")
    return {
        "schema": "material-lhcp-development-audio-validation-v1",
        "experiment_id": config["experiment_id"],
        "counts": expected_counts,
        "errors": errors,
        "validation": "TRACE_COMPLETE" if not errors else "TRACE_INCOMPLETE",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--external-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError(f"output exists: {args.out}")
    result = validate(
        args.config.resolve(), args.cohort.resolve(), args.manifest.resolve(),
        args.receipt.resolve(), args.external_root.resolve()
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0 if result["validation"] == "TRACE_COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
