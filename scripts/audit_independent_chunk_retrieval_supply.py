#!/usr/bin/env python3
"""One-shot gold-read supply audit for leave-one-chunk-out retrieval."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.state.chunk_retrieval import render_candidates  # noqa: E402
from meeting_minutes_agent.state.independent_chunk_retrieval import (  # noqa: E402
    IndependentRetrievalLimits,
    build_independent_index,
    retrieve_independent,
)
from meeting_minutes_agent.state.sliding_memory import content_tokens  # noqa: E402


_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
_EXPECTED_RUNTIME_SHA256 = "a2e272852cf35a6a67b9331b405a2472d3d3a217c8738f50693a8ad1898ce4b9"
_EXPECTED_SCORE_SHA256 = "163064779b3bf97244612fcd1af5333d04ffafe8a36c97656a32fa54dec70afb"
_EXPECTED_SOURCE_SHA256 = {
    "4430051": "3f446006c6dd0f63c462902969ea268f34c07330cc33fd8f4c60d06d29f20975",
    "4443920": "76866623d1c59a6d253bb32abc7d5a2ce8ae6a0f8394dbb8d0366582a0e3c5b7",
    "4461799": "8664437f7317a22cfe2625c5991fd00ffc4c12588a7b2176edd6360f29a2bd83",
    "4483589": "acf9309a919c5ea8c467e5130ca9401ab4c82f292f48c79798c298b91dd8c96e",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalize(text: str) -> list[str]:
    value = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    return _TOKEN.findall(value)


def reference_tokens(path: Path) -> list[dict[str, object]]:
    output = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="|"):
            if not row.get("ts") or not row.get("endTs"):
                continue
            try:
                start, end = float(row["ts"]), float(row["endTs"])
            except ValueError:
                continue
            tokens = normalize(row.get("token", ""))
            if tokens:
                output.append({"token": tokens[0], "start": start, "end": end})
    return output


def audit(runtime: dict[str, object], score: dict[str, object], source_dir: Path, data_dir: Path) -> dict[str, object]:
    limits = IndependentRetrievalLimits()
    score_by_id = {str(row["file_id"]): row for row in score["meetings"]}
    meetings = []
    total_turns = eligible_turns = supported_turns = 0
    candidate_count = supported_candidates = current_leaks = evidence_leaks = contexts_ok = 0
    unique_candidates: set[str] = set()
    for meeting in runtime["meetings"]:
        file_id = str(meeting["file_id"])
        source_path = source_dir / f"{file_id}-responses.jsonl"
        if sha256_file(source_path) != _EXPECTED_SOURCE_SHA256.get(file_id):
            raise ValueError(f"source pass hash mismatch: {file_id}")
        source_rows = rows(source_path)
        by_turn = {int(row["turn_index"]): row for row in source_rows}
        index = build_independent_index(source_rows)
        score_row = score_by_id[file_id]
        ref_path = data_dir / str(score_row["reference_relative"])
        if sha256_file(ref_path) != score_row["reference_sha256"]:
            raise ValueError(f"reference hash mismatch: {file_id}")
        refs = reference_tokens(ref_path)
        meeting_eligible = meeting_supported = meeting_candidates = 0
        for turn in meeting["turns"]:
            turn_index = int(turn["index"])
            query = str(by_turn[turn_index].get("text", ""))
            query_terms = set(content_tokens(query))
            candidates = retrieve_independent(str(turn["speaker_id"]), turn_index, query, index, limits)
            total_turns += 1
            if candidates:
                eligible_turns += 1
                meeting_eligible += 1
            local_reference = {
                str(token["token"]) for token in refs
                if float(token["end"]) > float(turn["start"]) and float(token["start"]) < float(turn["end"])
            }
            turn_supported = False
            for candidate in candidates:
                candidate_count += 1
                meeting_candidates += 1
                unique_candidates.add(candidate.term)
                current_leaks += int(candidate.term in query_terms)
                evidence_leaks += int(turn_index in candidate.supporting_turns)
                if candidate.term in local_reference:
                    supported_candidates += 1
                    turn_supported = True
            if turn_supported:
                supported_turns += 1
                meeting_supported += 1
            context = render_candidates([candidate.term for candidate in candidates], limits.maximum_context_characters)
            contexts_ok += int(len(context) <= limits.maximum_context_characters)
        meetings.append({
            "file_id": file_id,
            "turns": len(meeting["turns"]),
            "eligible_novel_turns": meeting_eligible,
            "reference_supported_turns": meeting_supported,
            "candidates": meeting_candidates,
        })
    eligible_meetings = sum(row["eligible_novel_turns"] >= 50 for row in meetings)
    supported_meetings = sum(row["reference_supported_turns"] >= 20 for row in meetings)
    precision = supported_candidates / candidate_count if candidate_count else 0.0
    gates = {
        "minimum_eligible_turns": eligible_turns >= 400,
        "minimum_eligible_meetings": eligible_meetings >= 3,
        "minimum_reference_supported_turns": supported_turns >= 100,
        "minimum_reference_supported_meetings": supported_meetings >= 3,
        "minimum_candidate_precision": precision >= 0.90,
        "minimum_unique_candidates": len(unique_candidates) >= 25,
        "no_current_query_leakage": current_leaks == 0,
        "no_current_turn_evidence": evidence_leaks == 0,
        "context_budget": contexts_ok == total_turns,
    }
    return {
        "schema": "independent-chunk-retrieval-supply-read-v1",
        "experiment_id": "E-CHUNK-RETRIEVAL-LOO-SUPPLY",
        "verdict": "INDEPENDENT-CHUNK-SUPPLY-READY" if all(gates.values()) else "INDEPENDENT-CHUNK-SUPPLY-INSUFFICIENT",
        "limits": vars(limits),
        "thresholds": {
            "minimum_eligible_turns": 400,
            "minimum_eligible_meetings": 3,
            "eligible_turns_per_meeting": 50,
            "minimum_reference_supported_turns": 100,
            "minimum_reference_supported_meetings": 3,
            "reference_supported_turns_per_meeting": 20,
            "minimum_candidate_precision": 0.90,
            "minimum_unique_candidates": 25,
        },
        "totals": {
            "turns": total_turns,
            "eligible_novel_turns": eligible_turns,
            "reference_supported_turns": supported_turns,
            "candidates": candidate_count,
            "reference_supported_candidates": supported_candidates,
            "candidate_precision": precision,
            "unique_candidates": len(unique_candidates),
            "current_query_leaks": current_leaks,
            "current_turn_evidence_leaks": evidence_leaks,
        },
        "gates": gates,
        "meetings": meetings,
        "claim_boundary": (
            "This gold-read audit tests supply and candidate relevance only. Gold is never available to runtime retrieval. "
            "Passing would admit a separately registered model experiment, not establish ASR utility."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--score", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; refusing second read")
    if sha256_file(args.runtime) != _EXPECTED_RUNTIME_SHA256:
        parser.error("runtime hash mismatch")
    if sha256_file(args.score) != _EXPECTED_SCORE_SHA256:
        parser.error("score hash mismatch")
    runtime = json.loads(args.runtime.read_text(encoding="utf-8"))
    score = json.loads(args.score.read_text(encoding="utf-8"))
    result = audit(runtime, score, args.source_dir, args.data_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "totals": result["totals"], "gates": result["gates"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
