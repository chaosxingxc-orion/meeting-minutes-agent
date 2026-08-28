#!/usr/bin/env python3
"""Build the frozen LHCP-ASR development Pass0 runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import wave


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.heads.transcribe_attribute import (  # noqa: E402
    TRANSCRIBE_ONLY_TEMPLATE_ID,
    TRANSCRIBE_ONLY_TEMPLATE_SHA256,
)
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def build(
    slice_manifest_path: Path,
    source_root: Path,
    runner_path: Path,
    reader_path: Path,
    readiness_path: Path,
    preregistration_path: Path,
    *,
    model_path: str,
    model_sha256: str,
    mmproj_path: str,
    mmproj_sha256: str,
    server_binary: str,
    server_sha256: str,
) -> dict[str, object]:
    manifest = json.loads(slice_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "material-lhcp-slicer-overlap-fix-manifest-v1":
        raise ValueError("slice manifest schema mismatch")
    if manifest.get("counts", {}).get("meetings") != 25 or manifest["counts"].get("new_slices") != 396:
        raise ValueError("slice manifest cohort mismatch")

    clips: list[dict[str, object]] = []
    prior_end_by_meeting: dict[str, float] = {}
    for meeting_position, meeting in enumerate(manifest["meetings"]):
        if meeting["position"] != meeting_position:
            raise ValueError("meeting order mismatch")
        meeting_id = str(meeting["meeting_id"])
        slice_manifest = meeting["slice_manifest"]
        if slice_manifest["meeting_id"] != meeting_id:
            raise ValueError(f"nested meeting id mismatch: {meeting_id}")
        for entry_position, entry in enumerate(slice_manifest["entries"]):
            if entry["index"] != entry_position:
                raise ValueError(f"slice order mismatch: {meeting_id}")
            start = float(entry["start"])
            end = float(entry["end"])
            if end <= start or end - start > 120.000001:
                raise ValueError(f"invalid slice bounds: {meeting_id} {entry_position}")
            if start + 1e-9 < prior_end_by_meeting.get(meeting_id, start):
                raise ValueError(f"adjacent slice overlap: {meeting_id} {entry_position}")
            prior_end_by_meeting[meeting_id] = end
            relative = Path("slices") / meeting_id / str(entry["filename"])
            path = source_root / relative
            if not path.is_file() or sha256_file(path) != entry["sha256"]:
                raise ValueError(f"audio binding mismatch: {meeting_id} {entry_position}")
            info = wav_info(path)
            if info["channels"] != 1 or info["sample_rate_hz"] != 16000 or info["sample_width_bytes"] != 2:
                raise ValueError(f"audio format mismatch: {meeting_id} {entry_position}")
            # A source recording may end up to 80 ms before the planned final
            # boundary. Preserve both values and fail on larger discrepancies.
            if abs(float(info["duration_s"]) - (end - start)) > 0.100001:
                raise ValueError(f"audio duration mismatch: {meeting_id} {entry_position}")
            speakers = sorted({str(turn["speaker"]) for turn in entry["turns"]})
            clips.append({
                "position": len(clips),
                "meeting_position": meeting_position,
                "meeting_id": meeting_id,
                "slice_index": entry_position,
                "turn_id": f"{meeting_id}-slice{entry_position:04d}",
                "request_id": f"lhcp-{meeting_id}-slice{entry_position:04d}-pass0-v1",
                "audio_relative": relative.as_posix(),
                "audio_sha256": entry["sha256"],
                "audio_bytes": path.stat().st_size,
                "slice_start_s": start,
                "slice_end_s": end,
                "speaker_labels": speakers,
                "turn_count": len(entry["turns"]),
                "turns_sha256": hashlib.sha256(
                    json.dumps(entry["turns"], sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
                **info,
            })
    audio_seconds = sum(float(clip["duration_s"]) for clip in clips)
    expected_seconds = float(manifest["counts"]["new_slice_audio_seconds"])
    if len(clips) != 396 or audio_seconds > expected_seconds or expected_seconds - audio_seconds > 1.0:
        raise ValueError("runtime queue total mismatch")

    runtime: dict[str, object] = {
        "schema": "material-lhcp-development-pass0-runtime-v1",
        "experiment_id": "E-MATERIAL-LHCP-DEVELOPMENT-PASS0",
        "claim_boundary": "Reference-blind structural Pass0 only; no references, confirmation, materials, retrieval, embeddings, correction, or quality scoring.",
        "inputs": {
            "slice_manifest_sha256": sha256_file(slice_manifest_path),
            "runner_sha256": sha256_file(runner_path),
            "reader_sha256": sha256_file(reader_path),
            "readiness_auditor_sha256": sha256_file(readiness_path),
            "preregistration_sha256": sha256_file(preregistration_path),
            "builder_sha256": sha256_file(Path(__file__).resolve()),
        },
        "source": {
            "slice_manifest_relative": "slice-manifest.json",
            "meeting_count": 25,
            "slice_count": 396,
            "turn_provenance": "tool-diar",
        },
        "model": {
            "base_url": "http://127.0.0.1:8080",
            "model_path": model_path,
            "model_sha256": model_sha256,
            "mmproj_path": mmproj_path,
            "mmproj_sha256": mmproj_sha256,
            "server_binary": server_binary,
            "server_sha256": server_sha256,
            "slots": 1,
        },
        "prompt": {
            "template_id": TRANSCRIBE_ONLY_TEMPLATE_ID,
            "template_sha256": TRANSCRIBE_ONLY_TEMPLATE_SHA256,
            "supplied_text": [],
            "speaker_metadata_supplied_to_model": False,
        },
        "decoding": {"temperature": 0, "seed": 0, "max_tokens": 512},
        "transport": {"timeout_seconds": 300, "max_retries": 0, "max_audio_seconds_per_request": 120},
        "trace": {
            "capture_exact_wire_request": True,
            "capture_exact_wire_response": True,
            "append_only_index": True,
            "fsync_each_artifact_and_row": True,
            "resume_policy": "Only an exact validated prefix may resume; orphan or drifted artifacts fail closed.",
        },
        "clips": clips,
        "budget": {
            "calls": len(clips),
            "audio_seconds": expected_seconds,
            "actual_wav_audio_seconds": audio_seconds,
            "maximum_output_tokens": len(clips) * 512,
        },
        "wall_clock_estimate": {
            "basis": "Linear extrapolation from the 2026-08-26 40-call Pass0 after server warm-up; not an LHCP measurement.",
            "lower_minutes": 45,
            "upper_minutes": 120,
        },
        "stopping_rules": {
            "hash_drift": "stop before server contact",
            "non_prefix_or_duplicate_index": "stop; do not repair in place",
            "request_failure": "stop immediately; preserve append-only prefix",
            "empty_response": "preserve as data and continue; structural read decides",
        },
    }
    runtime["content_hash"] = config_hash(runtime)
    return runtime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slice-manifest", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--runner", required=True, type=Path)
    parser.add_argument("--reader", required=True, type=Path)
    parser.add_argument("--readiness-auditor", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--mmproj-path", required=True)
    parser.add_argument("--mmproj-sha256", required=True)
    parser.add_argument("--server-binary", required=True)
    parser.add_argument("--server-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output exists: {args.output}")
    runtime = build(
        args.slice_manifest.resolve(), args.source_root.resolve(), args.runner.resolve(),
        args.reader.resolve(), args.readiness_auditor.resolve(), args.preregistration.resolve(),
        model_path=args.model_path, model_sha256=args.model_sha256,
        mmproj_path=args.mmproj_path, mmproj_sha256=args.mmproj_sha256,
        server_binary=args.server_binary, server_sha256=args.server_sha256,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(runtime, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"clips": len(runtime["clips"]), **runtime["budget"], "content_hash": runtime["content_hash"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
