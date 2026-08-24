#!/usr/bin/env python3
"""Freeze the E-LOOP-STABILITY model-contact manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.probes.contextasr import (  # noqa: E402
    SYSTEM_INSTRUCTION,
    TEMPLATE_ID,
    TEMPLATE_SHA256,
)
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402


ARMS = ("L0-bare", "L1-recent", "L2-global", "L3-speaker", "L4-deranged")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _locked(path: Path) -> dict[str, str]:
    return {"path": path.resolve().relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}


def build(runtime_path: Path, score_path: Path, source_dir: Path) -> dict[str, object]:
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    score = json.loads(score_path.read_text(encoding="utf-8"))
    if runtime.get("schema") != "earnings22-stable-error-runtime-v1":
        raise ValueError("runtime schema mismatch")
    if score.get("schema") != "earnings22-stable-error-score-v1":
        raise ValueError("score schema mismatch")
    if score["runtime_content_hash"] != runtime["content_hash"]:
        raise ValueError("runtime/score binding mismatch")
    source_passes = {}
    for meeting in runtime["meetings"]:
        file_id = str(meeting["file_id"])
        path = source_dir / f"{file_id}-responses.jsonl"
        if not path.is_file():
            raise ValueError(f"missing source pass: {file_id}")
        if len(path.read_text(encoding="utf-8").splitlines()) != len(meeting["turns"]):
            raise ValueError(f"incomplete source pass: {file_id}")
        source_passes[file_id] = _locked(path)
    calls = sum(len(meeting["turns"]) for meeting in runtime["meetings"])
    audio_seconds = sum(float(runtime_meeting["duration"]) for meeting in runtime["meetings"] for runtime_meeting in meeting["turns"])
    manifest: dict[str, object] = {
        "schema": "agent-loop-stability-runtime-v1",
        "experiment_id": "E-LOOP-STABILITY",
        "source_runtime": _locked(runtime_path),
        "source_score": _locked(score_path),
        "source_passes": source_passes,
        "arms": list(ARMS),
        "round2_arm": "L3-round2",
        "memory_limits": {
            "summary_characters": 1200,
            "recent_characters": 600,
            "global_keywords": 24,
            "speaker_keywords": 12,
            "minimum_keyword_count": 2,
        },
        "prompt": {
            "template_id": TEMPLATE_ID,
            "template_sha256": TEMPLATE_SHA256,
            "system_instruction": SYSTEM_INSTRUCTION,
        },
        "decode": {"temperature": 0, "seed": 0, "max_tokens": 512},
        "implementation": {
            "renderer": _locked(ROOT / "src/meeting_minutes_agent/state/sliding_memory.py"),
            "launcher": _locked(ROOT / "scripts/launch_agent_loop_stability.py"),
            "reader": _locked(ROOT / "scripts/read_agent_loop_stability.py"),
        },
        "budget": {
            "turns_per_pass": calls,
            "audio_seconds_per_pass": audio_seconds,
            "phase1_calls": calls * len(ARMS),
            "phase1_audio_seconds": audio_seconds * len(ARMS),
            "round2_calls": calls,
            "round2_audio_seconds": audio_seconds,
            "total_calls": calls * (len(ARMS) + 1),
            "total_audio_seconds": audio_seconds * (len(ARMS) + 1),
        },
        "gates": {
            "context_hash_replay_rate": 1.0,
            "context_budget_rate": 1.0,
            "minimum_consistency_gain_vs_bare": 0.02,
            "minimum_meetings_consistency_better_than_bare": 3,
            "minimum_meetings_consistency_better_than_deranged": 3,
            "maximum_convergence_ratio": 0.80,
            "maximum_wer_increase": 0.01,
            "maximum_worst_speaker_wer_increase": 0.02,
            "maximum_unsupported_activation_rate": 0.02,
            "maximum_language_drift_increase": 0,
        },
        "claim_boundary": (
            "Passing admits a stable bounded-memory loop only; it does not establish professional-term "
            "correction, utility improvement, or permission to run training-free policy search."
        ),
    }
    manifest["content_hash"] = config_hash(manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--score", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists")
    manifest = build(args.runtime, args.score, args.source_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"content_hash": manifest["content_hash"], "budget": manifest["budget"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
