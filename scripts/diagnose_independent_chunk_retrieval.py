#!/usr/bin/env python3
"""Posthoc descriptive diagnostics for the frozen independent-supply read."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from audit_independent_chunk_retrieval_supply import reference_tokens, rows  # noqa: E402
from meeting_minutes_agent.state.independent_chunk_retrieval import (  # noqa: E402
    IndependentRetrievalLimits,
    build_independent_index,
    retrieve_independent,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--score", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists")
    runtime = json.loads(args.runtime.read_text(encoding="utf-8"))
    score = json.loads(args.score.read_text(encoding="utf-8"))
    score_by_id = {str(row["file_id"]): row for row in score["meetings"]}
    supported: Counter[tuple[str, str]] = Counter()
    unsupported: Counter[tuple[str, str]] = Counter()
    similarity_buckets: Counter[str] = Counter()
    limits = IndependentRetrievalLimits()
    for meeting in runtime["meetings"]:
        file_id = str(meeting["file_id"])
        source_rows = rows(args.source_dir / f"{file_id}-responses.jsonl")
        by_turn = {int(row["turn_index"]): row for row in source_rows}
        index = build_independent_index(source_rows)
        refs = reference_tokens(args.data_dir / str(score_by_id[file_id]["reference_relative"]))
        for turn in meeting["turns"]:
            turn_index = int(turn["index"])
            candidates = retrieve_independent(
                str(turn["speaker_id"]), turn_index, str(by_turn[turn_index].get("text", "")), index, limits
            )
            local_reference = {
                str(token["token"]) for token in refs
                if float(token["end"]) > float(turn["start"]) and float(token["start"]) < float(turn["end"])
            }
            for candidate in candidates:
                pair = (candidate.matched_query_term, candidate.term)
                (supported if candidate.term in local_reference else unsupported)[pair] += 1
                lower = int(candidate.similarity * 20) / 20
                similarity_buckets[f"{lower:.2f}-{min(lower + 0.05, 1.0):.2f}"] += 1
    result = {
        "schema": "independent-chunk-retrieval-posthoc-diagnostic-v1",
        "status": "POSTHOC-DESCRIPTIVE-NONBRANCHING",
        "top_supported_pairs": [
            {"query": query, "candidate": candidate, "count": count}
            for (query, candidate), count in supported.most_common(25)
        ],
        "top_unsupported_pairs": [
            {"query": query, "candidate": candidate, "count": count}
            for (query, candidate), count in unsupported.most_common(25)
        ],
        "similarity_buckets": dict(sorted(similarity_buckets.items())),
        "claim_boundary": "Describes the registered failure only; it cannot tune thresholds or admit a model flight.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
