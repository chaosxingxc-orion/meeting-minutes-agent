#!/usr/bin/env python3
"""Build the frozen reference-blind Pass0 runtime for sealed confirmation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from build_material_new_surface_pass0_runtime import sha256_file, wav_info  # noqa: E402
from meeting_minutes_agent.heads.transcribe_attribute import (  # noqa: E402
    TRANSCRIBE_ONLY_TEMPLATE_ID,
    TRANSCRIBE_ONLY_TEMPLATE_SHA256,
)
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402


def build(
    cohort_path: Path,
    admission_path: Path,
    trace_schema_path: Path,
    dataset_root: Path,
    runner_path: Path,
    reader_path: Path,
    preregistration_path: Path,
    *,
    model_path: str,
    model_sha256: str,
    mmproj_path: str,
    mmproj_sha256: str,
    server_binary: str,
    server_sha256: str,
) -> dict[str, object]:
    cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
    admission = json.loads(admission_path.read_text(encoding="utf-8"))
    if cohort.get("schema") != "material-new-surface-frozen-cohort-v1":
        raise ValueError("cohort schema mismatch")
    if cohort.get("config_sha256") != sha256_file(admission_path):
        raise ValueError("cohort admission-config binding mismatch")
    trace_sha256 = sha256_file(trace_schema_path)
    if admission.get("trace_contract") != {
        "path": trace_schema_path.relative_to(ROOT).as_posix(),
        "sha256": trace_sha256,
    }:
        raise ValueError("admission trace-contract binding mismatch")

    clips: list[dict[str, object]] = []
    for item in cohort["items"]:
        if item["split"] != "confirmation":
            continue
        for audio_role in ("reference_audio", "answer_audio"):
            binding = item["audio"][audio_role]
            path = dataset_root / str(binding["relative_path"])
            if not path.is_file() or sha256_file(path) != binding["sha256"]:
                raise ValueError(f"audio binding mismatch: {item['item_id']} {audio_role}")
            info = wav_info(path)
            if abs(float(info["duration_s"]) - float(binding["duration_s"])) > 0.001:
                raise ValueError(f"audio duration mismatch: {item['item_id']} {audio_role}")
            role = audio_role.removesuffix("_audio")
            clips.append({
                "position": len(clips),
                "item_id": item["item_id"],
                "meeting_id": item["call_id"],
                "audio_role": audio_role,
                "turn_id": f"{item['item_id']}-{role}",
                "request_id": f"emns-confirm-{item['item_id'].lower()}-{role}-pass0-v1",
                "audio_relative": binding["relative_path"],
                "audio_sha256": binding["sha256"],
                "audio_bytes": path.stat().st_size,
                **info,
            })
    if len(clips) != 80:
        raise ValueError(f"expected 80 confirmation clips, got {len(clips)}")
    runtime: dict[str, object] = {
        "schema": "material-new-surface-pass0-runtime-v1",
        "experiment_id": "E-MATERIAL-NEW-SURFACE-PASS0-CONFIRMATION",
        "evidence_tier": "INDEPENDENT_NEW_SURFACE_CONFIRMATION",
        "claim_boundary": "Reference-blind confirmation Pass0 only; no reference, material, embedding, or Omni correction read.",
        "inputs": {
            "admission_config_sha256": sha256_file(admission_path),
            "cohort_sha256": sha256_file(cohort_path),
            "trace_schema_sha256": trace_sha256,
            "runner_sha256": sha256_file(runner_path),
            "reader_sha256": sha256_file(reader_path),
            "preregistration_sha256": sha256_file(preregistration_path),
            "builder_sha256": sha256_file(Path(__file__).resolve()),
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
        },
        "decoding": {"temperature": 0, "seed": 0, "max_tokens": 512},
        "transport": {"timeout_seconds": 300, "max_retries": 0, "max_audio_seconds_per_request": 120},
        "trace": {
            "capture_exact_wire_request": True,
            "capture_exact_wire_response": True,
            "append_only_index": True,
            "fsync_each_artifact_and_row": True,
            "resume_policy": "Only an exact validated prefix of this runtime may resume; orphan or drifted artifacts fail closed.",
        },
        "clips": clips,
        "budget": {
            "calls": len(clips),
            "audio_seconds": sum(float(clip["duration_s"]) for clip in clips),
            "maximum_output_tokens": len(clips) * 512,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--admission-config", required=True, type=Path)
    parser.add_argument("--trace-schema", required=True, type=Path)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--runner", required=True, type=Path)
    parser.add_argument("--reader", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--mmproj-path", required=True)
    parser.add_argument("--mmproj-sha256", required=True)
    parser.add_argument("--server-binary", required=True)
    parser.add_argument("--server-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output exists: {args.output}")
    runtime = build(
        args.cohort.resolve(), args.admission_config.resolve(), args.trace_schema.resolve(),
        args.dataset_root.resolve(), args.runner.resolve(), args.reader.resolve(),
        args.preregistration.resolve(), model_path=args.model_path,
        model_sha256=args.model_sha256, mmproj_path=args.mmproj_path,
        mmproj_sha256=args.mmproj_sha256, server_binary=args.server_binary,
        server_sha256=args.server_sha256,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(runtime, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"clips": len(runtime["clips"]), **runtime["budget"], "content_hash": runtime["content_hash"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
