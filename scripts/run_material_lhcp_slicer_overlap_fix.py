#!/usr/bin/env python3
"""Reslice the frozen LHCP development RTTMs with overlap-safe packing."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any
import wave


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.chunking.leakage import BoundaryProvenance  # noqa: E402
from meeting_minutes_agent.chunking.rttm import parse_rttm_file  # noqa: E402
from meeting_minutes_agent.chunking.slicer import (  # noqa: E402
    build_turn_aware_slice_plan,
    detect_energy_pause_transitions,
    materialize_slice_plan,
    read_audio_duration,
)


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


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


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


def verify_locks(config: dict[str, Any]) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    source_root = windows_to_wsl(str(config["source_root"]))
    inputs = config["inputs"]
    source_files = {
        "source_conversion_manifest_sha256": source_root / "conversion-manifest.json",
        "source_flight_summary_sha256": source_root / "flight-summary.json",
        "source_failed_slice_manifest_sha256": source_root / "slice-manifest.json",
    }
    code_files = {
        "slicer_sha256": ROOT / "src/meeting_minutes_agent/chunking/slicer.py",
        "rttm_parser_sha256": ROOT / "src/meeting_minutes_agent/chunking/rttm.py",
        "chunking_constants_sha256": ROOT / "src/meeting_minutes_agent/chunking/constants.py",
        "runner_sha256": Path(__file__).resolve(),
        "validator_sha256": ROOT / "scripts/validate_material_lhcp_slicer_overlap_fix.py",
        "preregistration_sha256": ROOT / "docs/readiness/2026-08-26-material-lhcp-slicer-overlap-fix-preregistration.md",
        "amendment_1_sha256": ROOT / "docs/readiness/2026-08-26-material-lhcp-slicer-overlap-fix-amendment-1.md",
    }
    for field, path in {**source_files, **code_files}.items():
        if not path.is_file() or sha256_file(path) != str(inputs[field]):
            raise ValueError(f"frozen lock mismatch: {field}")
    conversion = json.loads(source_files["source_conversion_manifest_sha256"].read_text(encoding="utf-8"))
    flight = json.loads(source_files["source_flight_summary_sha256"].read_text(encoding="utf-8"))
    failed = json.loads(source_files["source_failed_slice_manifest_sha256"].read_text(encoding="utf-8"))
    return source_root, conversion, flight, failed


def run(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    source_root, conversion, flight, failed = verify_locks(config)
    output_root = windows_to_wsl(str(config["output_root"]))
    if output_root.exists():
        raise FileExistsError(f"one-shot output root already exists: {output_root}")
    rows = list(conversion.get("files", []))
    outcomes = list(flight.get("outcomes", []))
    if len(rows) != 25 or len(outcomes) != 25 or flight.get("successful_contacts") != 25:
        raise ValueError("expected the complete frozen 25-meeting frontend trace")
    outcome_by_id = {str(row["meeting_id"]): row for row in outcomes}
    slicing = config["slicing"]
    meetings: list[dict[str, Any]] = []
    total_slices = 0
    total_seconds = 0.0
    maximum_seconds = 0.0
    output_root.mkdir(parents=True, exist_ok=False)
    for position, row in enumerate(rows):
        meeting_id = str(row["meeting_id"])
        if int(row["position"]) != position:
            raise ValueError(f"conversion order mismatch: {meeting_id}")
        wav_path = source_root / str(row["wav_relative_path"])
        rttm_path = source_root / "rttm" / f"{meeting_id}.rttm"
        outcome = outcome_by_id.get(meeting_id)
        if outcome is None or not outcome.get("ok"):
            raise ValueError(f"missing successful frozen outcome: {meeting_id}")
        if not wav_path.is_file() or sha256_file(wav_path) != str(row["wav_sha256"]):
            raise ValueError(f"frozen WAV mismatch: {meeting_id}")
        if not rttm_path.is_file() or sha256_file(rttm_path) != str(outcome["rttm_sha256"]):
            raise ValueError(f"frozen RTTM mismatch: {meeting_id}")
        info = wav_info(wav_path)
        if info["channels"] != 1 or info["sample_rate_hz"] != 16000 or info["sample_width_bytes"] != 2:
            raise ValueError(f"frozen WAV format mismatch: {meeting_id}")
        turns = parse_rttm_file(rttm_path)
        transitions = detect_energy_pause_transitions(wav_path)
        kwargs = {
            "turn_provenance": BoundaryProvenance.TOOL_DIAR,
            "total_duration_s": read_audio_duration(wav_path),
            "fallback_pause_transitions": transitions,
            "nominal_s": float(slicing["target_seconds"]),
            "min_s": float(slicing["minimum_seconds"]),
            "max_s": float(slicing["maximum_seconds"]),
            "snap_s": float(slicing["snap_seconds"]),
        }
        plan = build_turn_aware_slice_plan(meeting_id, turns, **kwargs)
        repeated = build_turn_aware_slice_plan(meeting_id, turns, **kwargs)
        if plan.content_hash != repeated.content_hash or plan.slices != repeated.slices:
            raise ValueError(f"non-deterministic planning result: {meeting_id}")
        manifest = materialize_slice_plan(
            plan,
            wav_path,
            output_root / "slices" / meeting_id,
            sample_rate=int(slicing["sample_rate_hz"]),
        )
        entries = [entry.to_dict() for entry in manifest.entries]
        if not entries or [int(entry["index"]) for entry in entries] != list(range(len(entries))):
            raise ValueError(f"empty or non-contiguous slices: {meeting_id}")
        durations = [float(entry["end"]) - float(entry["start"]) for entry in entries]
        if any(duration <= 0 or duration > 120.000000001 for duration in durations):
            raise ValueError(f"invalid slice duration: {meeting_id}")
        if any(float(left["end"]) - float(right["start"]) > 1e-9 for left, right in zip(entries, entries[1:])):
            raise ValueError(f"adjacent slice overlap survived correction: {meeting_id}")
        total_slices += len(entries)
        total_seconds += sum(durations)
        maximum_seconds = max(maximum_seconds, max(durations))
        meetings.append(
            {
                "position": position,
                "meeting_id": meeting_id,
                "source_wav_sha256": row["wav_sha256"],
                "source_rttm_sha256": outcome["rttm_sha256"],
                "plan_content_hash": plan.content_hash,
                "planning_repeated": True,
                "slice_manifest": manifest.to_dict(),
            }
        )
        print(f"reslice {position + 1:02d}/25 {meeting_id} n={len(entries)}", flush=True)
    result = {
        "schema": "material-lhcp-slicer-overlap-fix-manifest-v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": sha256_file(config_path),
        "source_artifact_hashes": {
            "conversion_manifest_sha256": config["inputs"]["source_conversion_manifest_sha256"],
            "flight_summary_sha256": config["inputs"]["source_flight_summary_sha256"],
            "failed_slice_manifest_sha256": config["inputs"]["source_failed_slice_manifest_sha256"],
        },
        "meetings": meetings,
        "counts": {
            "meetings": len(meetings),
            "old_slices": int(failed["counts"]["slices"]),
            "new_slices": total_slices,
            "old_slice_audio_seconds": float(failed["counts"]["slice_audio_seconds"]),
            "new_slice_audio_seconds": total_seconds,
            "maximum_slice_seconds": maximum_seconds,
            "sortformer_contacts": 0,
            "reference_reads": 0,
            "confirmation_reads": 0,
            "pass0_calls": 0,
            "embedding_calls": 0,
            "omni_calls": 0,
        },
    }
    atomic_json(output_root / "slice-manifest.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.config)
    print(json.dumps(result["counts"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
