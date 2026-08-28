#!/usr/bin/env python3
"""Zero-model readiness audit for LHCP-ASR development Pass0."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in (SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import launch_material_lhcp_development_pass0 as launcher  # noqa: E402


def audit(
    runtime_path: Path, slice_manifest: Path, source_root: Path, reader: Path,
    preregistration: Path, output_root: Path,
) -> dict[str, Any]:
    runtime = launcher.load_runtime(runtime_path)
    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, observed: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "observed": observed})

    manifest = json.loads(slice_manifest.read_text(encoding="utf-8"))
    record("slice_manifest_sha256", launcher.sha256_file(slice_manifest) == runtime["inputs"]["slice_manifest_sha256"], launcher.sha256_file(slice_manifest))
    record("meeting_count", len(manifest["meetings"]) == 25 == runtime["source"]["meeting_count"], len(manifest["meetings"]))
    record("slice_count", len(runtime["clips"]) == 396 == runtime["source"]["slice_count"], len(runtime["clips"]))
    actual_audio_seconds = sum(float(c["duration_s"]) for c in runtime["clips"])
    record("manifest_audio_seconds", abs(float(runtime["budget"]["audio_seconds"]) - 37547.2558125) < 0.001, runtime["budget"]["audio_seconds"])
    record("actual_wav_audio_seconds", abs(actual_audio_seconds - float(runtime["budget"]["actual_wav_audio_seconds"])) < 0.001 and 0 <= float(runtime["budget"]["audio_seconds"]) - actual_audio_seconds <= 1.0, actual_audio_seconds)
    record("maximum_slice_seconds", max(float(c["duration_s"]) for c in runtime["clips"]) <= 120.000001, max(float(c["duration_s"]) for c in runtime["clips"]))
    record("budget_calls", runtime["budget"]["calls"] == 396, runtime["budget"]["calls"])
    record("budget_output_tokens", runtime["budget"]["maximum_output_tokens"] == 202752, runtime["budget"]["maximum_output_tokens"])
    record("transport_policy", runtime["model"]["slots"] == 1 and runtime["transport"]["max_retries"] == 0 and runtime["transport"]["timeout_seconds"] == 300, runtime["transport"])
    record("prompt_has_no_supplied_text", runtime["prompt"]["supplied_text"] == [] and runtime["prompt"]["speaker_metadata_supplied_to_model"] is False, runtime["prompt"])

    missing = drifted = 0
    audio_bytes = 0
    for clip in runtime["clips"]:
        path = source_root / clip["audio_relative"]
        if not path.is_file():
            missing += 1
            continue
        audio_bytes += path.stat().st_size
        if path.stat().st_size != clip["audio_bytes"] or launcher.sha256_file(path) != clip["audio_sha256"]:
            drifted += 1
    record("all_slice_audio_bound", missing == 0 and drifted == 0, {"missing": missing, "drifted": drifted, "bytes": audio_bytes})

    artifact_checks = {
        "runner_sha256": Path(launcher.__file__).resolve(),
        "reader_sha256": reader,
        "readiness_auditor_sha256": Path(__file__).resolve(),
        "preregistration_sha256": preregistration,
    }
    for field, path in artifact_checks.items():
        observed = launcher.sha256_file(path)
        record(field, observed == runtime["inputs"][field], observed)

    for field, sha_field, label in (
        ("model_path", "model_sha256", "model"),
        ("mmproj_path", "mmproj_sha256", "mmproj"),
        ("server_binary", "server_sha256", "server_binary"),
    ):
        path = Path(runtime["model"][field])
        observed = launcher.sha256_file(path) if path.is_file() else None
        record(f"{label}_sha256", observed == runtime["model"][sha_field], observed)

    required_bytes = int(audio_bytes * 1.5 + 512 * 1024 * 1024)
    parent = output_root.parent
    parent.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(parent).free
    record("output_root_absent", not output_root.exists(), str(output_root))
    record("external_trace_space", free_bytes >= required_bytes, {"free_bytes": free_bytes, "required_bytes": required_bytes})
    record("no_e_drive_dependency", all(not str(value).casefold().startswith(("e:\\", "/mnt/e/")) for value in (
        slice_manifest, source_root, output_root, runtime["model"]["model_path"], runtime["model"]["mmproj_path"], runtime["model"]["server_binary"]
    )), "all frozen paths use D or WSL root")

    passed = all(check["passed"] for check in checks)
    return {
        "schema": "material-lhcp-development-pass0-readiness-v1",
        "experiment_id": runtime["experiment_id"],
        "verdict": "LHCP_DEVELOPMENT_PASS0_READY_AWAITING_AUTHORIZATION" if passed else "LHCP_DEVELOPMENT_PASS0_NOT_READY",
        "model_contacts": 0, "reference_reads": 0, "confirmation_reads": 0,
        "runtime_sha256": launcher.sha256_file(runtime_path),
        "slice_manifest_sha256": launcher.sha256_file(slice_manifest),
        "output_root": str(output_root), "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--slice-manifest", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--reader", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.runtime, args.slice_manifest, args.source_root, args.reader, args.preregistration, args.output_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        parser.error(f"output exists: {args.output}")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "checks": len(result["checks"]), "failed": [c["name"] for c in result["checks"] if not c["passed"]]}, indent=2))
    return 0 if result["verdict"].endswith("AWAITING_AUTHORIZATION") else 1


if __name__ == "__main__":
    raise SystemExit(main())
