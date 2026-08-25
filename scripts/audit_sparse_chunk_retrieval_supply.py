#!/usr/bin/env python3
"""Zero-model admission audit for sparse per-chunk retrieval."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.state.chunk_retrieval import (  # noqa: E402
    RetrievalLimits,
    build_index,
    render_candidates,
    retrieve_for_arm,
)


def _rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def audit(runtime: dict[str, object], source_dir: Path, limits: RetrievalLimits) -> dict[str, object]:
    meetings = []
    eligible = distinct = equal_cardinality = contexts_ok = total = 0
    for meeting in runtime["meetings"]:
        file_id = str(meeting["file_id"])
        rows = _rows(source_dir / f"{file_id}-responses.jsonl")
        by_turn = {int(row["turn_index"]): row for row in rows}
        index = build_index(rows, limits)
        meeting_eligible = meeting_distinct = 0
        for turn in meeting["turns"]:
            source = by_turn[int(turn["index"])]
            query = str(source.get("text", ""))
            speaker = retrieve_for_arm("R2-speaker", str(turn["speaker_id"]), query, index, limits)
            deranged = retrieve_for_arm("R3-deranged", str(turn["speaker_id"]), query, index, limits)
            total += 1
            if speaker:
                eligible += 1
                meeting_eligible += 1
                distinct += int(speaker != deranged)
                meeting_distinct += int(speaker != deranged)
                equal_cardinality += int(len(speaker) == len(deranged))
                contexts_ok += int(len(render_candidates(speaker, limits.maximum_context_characters)) <= limits.maximum_context_characters)
        meetings.append(
            {
                "file_id": file_id,
                "turns": len(meeting["turns"]),
                "eligible_turns": meeting_eligible,
                "route_distinct_turns": meeting_distinct,
            }
        )
    eligible_meetings = sum(row["eligible_turns"] >= 50 for row in meetings)
    route_rate = distinct / eligible if eligible else 0.0
    gates = {
        "minimum_eligible_turns": eligible >= 400,
        "minimum_eligible_meetings": eligible_meetings >= 3,
        "route_distinct_rate": route_rate == 1.0,
        "equal_candidate_cardinality": equal_cardinality == eligible,
        "context_budget": contexts_ok == eligible,
    }
    return {
        "schema": "sparse-chunk-retrieval-supply-read-v3",
        "experiment_id": "E-CHUNK-RETRIEVAL-SUPPLY-V3",
        "verdict": "SPARSE-CHUNK-RETRIEVAL-SUPPLY-READY" if all(gates.values()) else "SPARSE-CHUNK-RETRIEVAL-SUPPLY-INSUFFICIENT",
        "limits": vars(limits),
        "totals": {
            "turns": total,
            "eligible_turns": eligible,
            "eligible_meetings": eligible_meetings,
            "route_distinct_turns": distinct,
            "route_distinct_rate": route_rate,
            "equal_cardinality_turns": equal_cardinality,
        },
        "gates": gates,
        "meetings": meetings,
        "claim_boundary": "Output-only supply; no claim about correctness, stability, or ASR utility.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists")
    runtime = json.loads(args.runtime.read_text(encoding="utf-8"))
    result = audit(runtime, args.source_dir, RetrievalLimits())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "totals": result["totals"], "gates": result["gates"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
