#!/usr/bin/env python3
"""Run the frozen LHCP development conversion, Sortformer, and slicing flight."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
import wave


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.chunking.leakage import BoundaryProvenance  # noqa: E402
from meeting_minutes_agent.chunking.rttm import parse_rttm_file  # noqa: E402
from meeting_minutes_agent.chunking.slicer import build_slice_manifest  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def windows_to_wsl(value: str) -> Path:
    if len(value) >= 3 and value[1:3] == ":/":
        return Path(f"/mnt/{value[0].lower()}/{value[3:]}")
    return Path(value)


def wav_info(path: Path) -> dict[str, int | float]:
    with wave.open(str(path), "rb") as audio:
        frames = audio.getnframes()
        rate = audio.getframerate()
        return {
            "channels": audio.getnchannels(),
            "sample_width_bytes": audio.getsampwidth(),
            "sample_rate_hz": rate,
            "frames": frames,
            "duration_s": frames / rate,
        }


def verify_code_and_tool_locks(config: dict[str, Any]) -> None:
    inputs = config["inputs"]
    locks = {
        "audio_manifest_sha256": windows_to_wsl(str(inputs["audio_manifest"])),
        "audio_validation_sha256": ROOT / "docs/checks/2026-08-26-material-lhcp-supply/development-audio-validation.json",
        "slicer_sha256": ROOT / "src/meeting_minutes_agent/chunking/slicer.py",
        "rttm_parser_sha256": ROOT / "src/meeting_minutes_agent/chunking/rttm.py",
        "chunking_constants_sha256": ROOT / "src/meeting_minutes_agent/chunking/constants.py",
        "runner_sha256": Path(__file__).resolve(),
        "reader_sha256": ROOT / "scripts/validate_material_lhcp_development_frontend.py",
        "preregistration_sha256": ROOT / "docs/readiness/2026-08-26-material-lhcp-development-frontend-preregistration.md",
    }
    for field, path in locks.items():
        if not path.is_file() or sha256_file(path) != inputs[field]:
            raise ValueError(f"frozen input lock mismatch: {field}")
    binaries = {
        Path(str(config["conversion"]["binary"])): config["conversion"]["binary_sha256"],
        Path(str(config["diarizer"]["binary_path"])): config["diarizer"]["binary_sha256"],
        Path(str(config["diarizer"]["model_path"])): config["diarizer"]["model_sha256"],
    }
    for path, digest in binaries.items():
        if not path.is_file() or sha256_file(path) != digest:
            raise ValueError(f"frozen binary lock mismatch: {path}")


def source_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    manifest_path = windows_to_wsl(str(config["inputs"]["audio_manifest"]))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = list(manifest["files"])
    if len(rows) != 25 or len({row["audio_path"] for row in rows}) != 25:
        raise ValueError("expected 25 unique development source rows")
    return rows


def validate_conversion(
    config: dict[str, Any], output_root: Path, manifest: dict[str, Any]
) -> None:
    rows = manifest.get("files", [])
    if len(rows) != 25 or [row.get("position") for row in rows] != list(range(25)):
        raise ValueError("conversion manifest count or order mismatch")
    expected = {Path(str(row["audio_path"])).stem: row for row in source_rows(config)}
    if {str(row.get("meeting_id")) for row in rows} != set(expected):
        raise ValueError("conversion manifest identity mismatch")
    for row in rows:
        meeting_id = str(row["meeting_id"])
        path = output_root / str(row["wav_relative_path"])
        if not path.is_file() or path.stat().st_size != int(row["wav_bytes"]):
            raise ValueError(f"converted WAV byte binding mismatch: {meeting_id}")
        if sha256_file(path) != row["wav_sha256"]:
            raise ValueError(f"converted WAV hash mismatch: {meeting_id}")
        info = wav_info(path)
        if info["channels"] != 1 or info["sample_rate_hz"] != 16000 or info["sample_width_bytes"] != 2:
            raise ValueError(f"converted WAV format mismatch: {meeting_id}")
        if abs(float(info["duration_s"]) - float(row["duration_s"])) > 0.001:
            raise ValueError(f"converted WAV duration mismatch: {meeting_id}")
        if row["source_sha256"] != expected[meeting_id]["sha256"]:
            raise ValueError(f"converted WAV source binding mismatch: {meeting_id}")


def prepare(config: dict[str, Any], output_root: Path) -> dict[str, Any]:
    manifest_path = output_root / "conversion-manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        validate_conversion(config, output_root, existing)
        return existing
    source_root = windows_to_wsl(str(config["inputs"]["audio_root"]))
    destination_root = output_root / "pcm16k"
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(source_rows(config), 1):
        source = (source_root / str(row["relative_path"])).resolve()
        if not source.is_file() or sha256_file(source) != row["sha256"]:
            raise ValueError(f"source audio binding mismatch: {row['audio_path']}")
        destination = destination_root / str(row["split"]) / str(row["audio_path"])
        if destination.exists():
            raise ValueError(f"unbound converted WAV exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".wav.part")
        command = [
            str(config["conversion"]["binary"]), "-nostdin", "-v", "error", "-i", str(source),
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", "-y", str(temporary),
        ]
        subprocess.run(command, check=True)
        temporary.replace(destination)
        info = wav_info(destination)
        if info["channels"] != 1 or info["sample_rate_hz"] != 16000 or info["sample_width_bytes"] != 2:
            raise ValueError(f"conversion format mismatch: {row['audio_path']}")
        if abs(float(info["duration_s"]) - float(row["duration_s"])) > 0.01:
            raise ValueError(f"conversion duration mismatch: {row['audio_path']}")
        rows.append(
            {
                "position": index - 1,
                "meeting_id": Path(str(row["audio_path"])).stem,
                "split": row["split"],
                "source_relative_path": row["relative_path"],
                "source_sha256": row["sha256"],
                "wav_relative_path": destination.relative_to(output_root).as_posix(),
                "wav_bytes": destination.stat().st_size,
                "wav_sha256": sha256_file(destination),
                **info,
            }
        )
        print(f"prepare {index:02d}/25 {row['audio_path']}", flush=True)
    result = {
        "schema": "material-lhcp-development-conversion-manifest-v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": sha256_file(args_config_path),
        "conversion": "ffmpeg mono 16 kHz PCM16",
        "files": rows,
    }
    atomic_json(manifest_path, result)
    validate_conversion(config, output_root, result)
    return result


def run_flight(config: dict[str, Any], output_root: Path, conversion: dict[str, Any]) -> dict[str, Any]:
    summary_path = output_root / "flight-summary.json"
    if summary_path.exists():
        return json.loads(summary_path.read_text(encoding="utf-8"))
    rttm_dir = output_root / "rttm"
    receipt_dir = output_root / "contact-receipts"
    log_dir = output_root / "logs"
    for directory in (rttm_dir, receipt_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)
    diarizer = config["diarizer"]
    campaign_started = time.monotonic()
    outcomes: list[dict[str, Any]] = []
    for index, row in enumerate(conversion["files"], 1):
        if time.monotonic() - campaign_started >= float(diarizer["maximum_campaign_wall_hours"]) * 3600:
            raise RuntimeError("campaign wall-time ceiling reached before next contact")
        meeting_id = str(row["meeting_id"])
        wav_path = output_root / str(row["wav_relative_path"])
        receipt_path = receipt_dir / f"{meeting_id}.json"
        rttm_path = rttm_dir / f"{meeting_id}.rttm"
        log_path = log_dir / f"{meeting_id}.log"
        if receipt_path.exists():
            prior = json.loads(receipt_path.read_text(encoding="utf-8"))
            if not prior.get("ok") or not rttm_path.is_file() or sha256_file(rttm_path) != prior.get("rttm_sha256"):
                raise ValueError(f"invalid prior contact state: {meeting_id}")
            outcomes.append(prior)
            print(f"resume {index:02d}/25 {meeting_id}", flush=True)
            continue
        if rttm_path.exists() or log_path.exists():
            raise ValueError(f"orphan contact artifact: {meeting_id}")
        command = [
            str(diarizer["binary_path"]), "diarize", str(wav_path),
            "--model", str(diarizer["model_path"]), "--format", "rttm",
            "--recording-id", meeting_id, "--output", str(rttm_path), "--force",
        ]
        began = time.monotonic()
        with log_path.open("x", encoding="utf-8") as log:
            process = subprocess.run(
                command, stdout=log, stderr=subprocess.STDOUT,
                timeout=float(diarizer["timeout_seconds_per_contact"]), check=False,
            )
        wall = time.monotonic() - began
        turns = parse_rttm_file(rttm_path) if rttm_path.is_file() else ()
        outcome = {
            "position": index - 1,
            "meeting_id": meeting_id,
            "input_wav_sha256": row["wav_sha256"],
            "binary_sha256": diarizer["binary_sha256"],
            "model_sha256": diarizer["model_sha256"],
            "command": command,
            "return_code": process.returncode,
            "wall_seconds": wall,
            "turn_count": len(turns),
            "predicted_speaker_count": len({turn.speaker for turn in turns}),
            "rttm_sha256": sha256_file(rttm_path) if rttm_path.is_file() else None,
            "log_sha256": sha256_file(log_path),
            "recorded_utc": datetime.now(timezone.utc).isoformat(),
            "ok": process.returncode == 0 and bool(turns),
        }
        atomic_json(receipt_path, outcome)
        outcomes.append(outcome)
        print(f"flight {index:02d}/25 {meeting_id} ok={outcome['ok']} wall={wall:.1f}s", flush=True)
        if not outcome["ok"]:
            raise RuntimeError(f"Sortformer contact failed: {meeting_id}")
    result = {
        "schema": "material-lhcp-development-sortformer-flight-v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": sha256_file(args_config_path),
        "contacts": len(outcomes),
        "successful_contacts": sum(bool(row["ok"]) for row in outcomes),
        "input_audio_seconds": sum(float(row["duration_s"]) for row in conversion["files"]),
        "campaign_wall_seconds": time.monotonic() - campaign_started,
        "outcomes": outcomes,
    }
    atomic_json(summary_path, result)
    return result


def freeze_slices(
    config: dict[str, Any], output_root: Path, conversion: dict[str, Any], flight: dict[str, Any]
) -> dict[str, Any]:
    manifest_path = output_root / "slice-manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    if flight.get("successful_contacts") != 25:
        raise ValueError("complete Sortformer flight required before slicing")
    outcome_by_id = {row["meeting_id"]: row for row in flight["outcomes"]}
    meetings: list[dict[str, Any]] = []
    total_slices = 0
    total_slice_seconds = 0.0
    for index, row in enumerate(conversion["files"], 1):
        meeting_id = str(row["meeting_id"])
        rttm_path = output_root / "rttm" / f"{meeting_id}.rttm"
        turns = parse_rttm_file(rttm_path)
        manifest = build_slice_manifest(
            meeting_id,
            output_root / str(row["wav_relative_path"]),
            output_root / "slices" / meeting_id,
            mode="turn_aware",
            turns=turns,
            turn_provenance=BoundaryProvenance.TOOL_DIAR,
            nominal_s=float(config["slicing"]["target_seconds"]),
            min_s=float(config["slicing"]["minimum_seconds"]),
            max_s=float(config["slicing"]["maximum_seconds"]),
            snap_s=float(config["slicing"]["snap_seconds"]),
            sample_rate=int(config["slicing"]["sample_rate_hz"]),
        )
        entries = [entry.to_dict() for entry in manifest.entries]
        if not entries or [entry["index"] for entry in entries] != list(range(len(entries))):
            raise ValueError(f"empty or non-contiguous slices: {meeting_id}")
        if any(float(entry["end"]) - float(entry["start"]) > 120.000000001 for entry in entries):
            raise ValueError(f"oversized slice: {meeting_id}")
        total_slices += len(entries)
        total_slice_seconds += sum(float(entry["end"]) - float(entry["start"]) for entry in entries)
        meetings.append(
            {
                "position": index - 1,
                "meeting_id": meeting_id,
                "source_wav_sha256": row["wav_sha256"],
                "rttm_sha256": outcome_by_id[meeting_id]["rttm_sha256"],
                "predicted_speaker_count": outcome_by_id[meeting_id]["predicted_speaker_count"],
                "slice_manifest": manifest.to_dict(),
            }
        )
        print(f"slice {index:02d}/25 {meeting_id} n={len(entries)}", flush=True)
    result = {
        "schema": "material-lhcp-development-slice-manifest-v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": sha256_file(args_config_path),
        "meetings": meetings,
        "counts": {
            "meetings": len(meetings),
            "slices": total_slices,
            "slice_audio_seconds": total_slice_seconds,
            "reference_reads": 0,
            "confirmation_reads": 0,
            "omni_calls": 0,
        },
    }
    atomic_json(manifest_path, result)
    return result


def main() -> int:
    global args_config_path
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--stage", choices=("prepare", "flight", "slice", "all"), default="all")
    args = parser.parse_args()
    args_config_path = args.config.resolve()
    config = json.loads(args_config_path.read_text(encoding="utf-8"))
    verify_code_and_tool_locks(config)
    output_root = windows_to_wsl(str(config["output_root"]))
    conversion = prepare(config, output_root)
    if args.stage == "prepare":
        print(json.dumps({"stage": "prepare", "files": len(conversion["files"])}, indent=2))
        return 0
    flight = run_flight(config, output_root, conversion)
    if args.stage == "flight":
        print(json.dumps({"stage": "flight", "contacts": flight["successful_contacts"]}, indent=2))
        return 0
    slices = freeze_slices(config, output_root, conversion, flight)
    print(json.dumps({"stage": "slice", **slices["counts"]}, indent=2))
    return 0


args_config_path = Path()


if __name__ == "__main__":
    raise SystemExit(main())
