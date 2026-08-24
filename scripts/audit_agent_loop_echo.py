#!/usr/bin/env python3
"""Post-hoc output-length and recent-tail echo diagnostic for E-LOOP-STABILITY."""

from __future__ import annotations

import argparse
import csv
import difflib
import importlib.util
import json
from pathlib import Path
import statistics
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.state.sliding_memory import MemoryLimits, recent_tail  # noqa: E402


_READ_PATH = ROOT / "scripts/read_agent_loop_stability.py"
_SPEC = importlib.util.spec_from_file_location("loop_stability_reader_for_echo", _READ_PATH)
assert _SPEC is not None and _SPEC.loader is not None
reader = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = reader
_SPEC.loader.exec_module(reader)


def echo_fraction(previous: list[str], current: list[str]) -> float:
    if not current:
        return 0.0
    matched = sum(block.size for block in difflib.SequenceMatcher(a=previous, b=current, autojunk=False).get_matching_blocks())
    return matched / len(current)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--phase1-responses", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    runtime = json.loads((ROOT / manifest["source_runtime"]["path"]).read_text(encoding="utf-8"))
    score = json.loads((ROOT / manifest["source_score"]["path"]).read_text(encoding="utf-8"))
    score_by_id = {str(row["file_id"]): row for row in score["meetings"]}
    rows = [json.loads(line) for line in args.phase1_responses.read_text(encoding="utf-8").splitlines()]
    by_key = {(str(row["file_id"]), int(row["turn_index"]), str(row["arm"])): row for row in rows}
    limits = MemoryLimits(**{key: int(value) for key, value in manifest["memory_limits"].items()})
    arms = list(manifest["arms"])
    totals = {arm: {"reference": 0, "hypothesis": 0, "echoes": [], "high_echo": 0, "eligible": 0} for arm in arms}
    for meeting in runtime["meetings"]:
        file_id = str(meeting["file_id"])
        reference, _ = reader._reference(args.data_dir / score_by_id[file_id]["reference_relative"])
        histories = {arm: [] for arm in arms}
        for turn in meeting["turns"]:
            indices = [
                index for index, token in enumerate(reference)
                if float(token["end"]) > float(turn["start"]) and float(token["start"]) < float(turn["end"])
            ]
            for arm in arms:
                row = by_key[(file_id, int(turn["index"]), arm)]
                hypothesis = reader.normalize_tokens(str(row["text"]))
                previous = reader.normalize_tokens(recent_tail(histories[arm], limits.recent_characters))
                fraction = echo_fraction(previous, hypothesis)
                totals[arm]["reference"] += len(indices)
                totals[arm]["hypothesis"] += len(hypothesis)
                totals[arm]["echoes"].append(fraction)
                if len(hypothesis) >= 3 and previous:
                    totals[arm]["eligible"] += 1
                    totals[arm]["high_echo"] += int(fraction >= 0.8)
                histories[arm].append(row)
    result = {"schema": "agent-loop-stability-echo-posthoc-v1", "arms": {}}
    for arm, values in totals.items():
        result["arms"][arm] = {
            "hypothesis_to_reference_word_ratio": values["hypothesis"] / values["reference"],
            "median_recent_tail_echo_fraction": statistics.median(values["echoes"]),
            "high_echo_outputs": values["high_echo"],
            "echo_eligible_outputs": values["eligible"],
            "high_echo_rate": values["high_echo"] / values["eligible"] if values["eligible"] else 0.0,
        }
    result["claim_boundary"] = "Post-hoc mechanism diagnostic; it does not replace the registered verdict."
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
