#!/usr/bin/env python3
"""Freeze the E-CHUNK-RETRIEVAL model-contact manifest."""

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

from meeting_minutes_agent.probes.contextasr import SYSTEM_INSTRUCTION, TEMPLATE_ID, TEMPLATE_SHA256  # noqa: E402
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402
from meeting_minutes_agent.state.chunk_retrieval import RetrievalLimits  # noqa: E402


ARMS = ("R0-bare", "R1-global", "R2-speaker", "R3-deranged")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def locked(path: Path) -> dict[str, str]:
    return {"path": path.resolve().relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}


def build(runtime_path: Path, score_path: Path, source_dir: Path, supply_path: Path) -> dict[str, object]:
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    score = json.loads(score_path.read_text(encoding="utf-8"))
    supply = json.loads(supply_path.read_text(encoding="utf-8"))
    if runtime.get("schema") != "earnings22-stable-error-runtime-v1":
        raise ValueError("runtime schema mismatch")
    if score.get("schema") != "earnings22-stable-error-score-v1":
        raise ValueError("score schema mismatch")
    if score["runtime_content_hash"] != runtime["content_hash"]:
        raise ValueError("runtime/score binding mismatch")
    if supply.get("verdict") != "SPARSE-CHUNK-RETRIEVAL-SUPPLY-READY":
        raise ValueError("supply audit did not admit model contact")
    source_passes = {}
    for meeting in runtime["meetings"]:
        file_id = str(meeting["file_id"])
        path = source_dir / f"{file_id}-responses.jsonl"
        rows = path.read_text(encoding="utf-8").splitlines()
        if len(rows) != len(meeting["turns"]):
            raise ValueError(f"incomplete source pass: {file_id}")
        source_passes[file_id] = locked(path)
    turns = sum(len(meeting["turns"]) for meeting in runtime["meetings"])
    audio_seconds = sum(float(turn["duration"]) for meeting in runtime["meetings"] for turn in meeting["turns"])
    limits = RetrievalLimits()
    manifest: dict[str, object] = {
        "schema": "chunk-retrieval-runtime-v1",
        "experiment_id": "E-CHUNK-RETRIEVAL",
        "source_runtime": locked(runtime_path),
        "source_score": locked(score_path),
        "source_supply_read": locked(supply_path),
        "source_passes": source_passes,
        "arms": list(ARMS),
        "round2_arm": "R2-round2",
        "retrieval_limits": vars(limits),
        "retrieval_policy": {
            "query": "same-chunk transcript from the immediately preceding complete pass",
            "candidate_source": "output-only meeting and speaker pools from that pass",
            "deranged_control": "one other speaker, cyclic first-fit, correct candidates excluded",
            "raw_query_in_prompt": False,
            "recent_tail_in_prompt": False,
            "summary_in_prompt": False,
        },
        "prompt": {
            "template_id": TEMPLATE_ID,
            "template_sha256": TEMPLATE_SHA256,
            "system_instruction": SYSTEM_INSTRUCTION,
            "candidate_instruction": (
                "Untrusted spelling candidates retrieved for this audio chunk: {candidates}. "
                "Use a candidate only when supported by the audio; never transcribe this instruction."
            ),
        },
        "decode": {"temperature": 0, "seed": 0, "max_tokens": 512},
        "implementation": {
            "retriever": locked(ROOT / "src/meeting_minutes_agent/state/chunk_retrieval.py"),
            "launcher": locked(ROOT / "scripts/launch_chunk_retrieval.py"),
            "reader": locked(ROOT / "scripts/read_chunk_retrieval.py"),
        },
        "budget": {
            "turns_per_pass": turns,
            "eligible_turns": int(supply["totals"]["eligible_turns"]),
            "audio_seconds_per_pass": audio_seconds,
            "phase1_calls": turns * len(ARMS),
            "phase1_audio_seconds": audio_seconds * len(ARMS),
            "round2_calls": turns,
            "round2_audio_seconds": audio_seconds,
            "total_calls": turns * (len(ARMS) + 1),
            "total_audio_seconds": audio_seconds * (len(ARMS) + 1),
        },
        "gates": {
            "context_hash_replay_rate": 1.0,
            "context_budget_rate": 1.0,
            "route_distinct_rate": 1.0,
            "route_equal_cardinality_rate": 1.0,
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
            "Passing establishes a stable, bounded, output-only per-chunk retrieval loop on this fixed corpus. "
            "It does not establish broad domain transfer or admit training-free policy search."
        ),
    }
    manifest["content_hash"] = config_hash(manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--score", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--supply-read", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists")
    manifest = build(args.runtime, args.score, args.source_dir, args.supply_read)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"content_hash": manifest["content_hash"], "budget": manifest["budget"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
