#!/usr/bin/env python3
"""Audit output-only supply for a bounded sliding-memory experiment."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re


TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9&.-]{1,}")
STOPWORDS = {
    "a", "about", "after", "again", "all", "also", "am", "an", "and", "any",
    "are", "as", "at", "be", "because", "been", "before", "being", "but", "by",
    "can", "could", "did", "do", "does", "doing", "for", "from", "had", "has",
    "have", "he", "her", "here", "him", "his", "how", "i", "if", "in", "into",
    "is", "it", "its", "just", "me", "more", "my", "no", "not", "now", "of",
    "on", "one", "or", "our", "out", "really", "re", "she", "so", "some",
    "than", "that", "the", "their", "them", "then", "there", "these", "they",
    "think", "this", "those", "to", "too", "uh", "um", "up", "us", "very",
    "was", "we", "well", "were", "what", "when", "which", "who", "will", "with",
    "would", "yeah", "yes", "you", "your",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tokens(text: str) -> list[str]:
    output = []
    for raw in TOKEN_RE.findall(text):
        token = raw.lower().strip(".-")
        if token in STOPWORDS:
            continue
        is_abbreviation = raw.isupper() and 2 <= len(raw) <= 12
        is_alphanumeric = any(char.isalpha() for char in raw) and any(char.isdigit() for char in raw)
        if len(token) >= 3 or is_abbreviation or is_alphanumeric:
            output.append(token)
    return output


def ranked_keywords(counter: Counter[str], minimum_count: int, cap: int) -> list[str]:
    eligible = ((term, count) for term, count in counter.items() if count >= minimum_count)
    return [term for term, _ in sorted(eligible, key=lambda item: (-item[1], item[0]))[:cap]]


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def audit(config: dict[str, object], runtime: dict[str, object], response_dir: Path) -> dict[str, object]:
    minimum_count = int(config["minimum_keyword_count"])
    global_cap = int(config["global_keyword_cap"])
    speaker_cap = int(config["speaker_keyword_cap"])
    window_seconds = int(config["window_seconds"])
    meetings = []
    total_ready = 0
    total_global_carry = 0
    total_speaker_carry = 0

    for meeting in runtime["meetings"]:
        file_id = str(meeting["file_id"])
        response_path = response_dir / f"{file_id}-responses.jsonl"
        expected_hash = str(config["source_responses"][file_id])
        if sha256_file(response_path) != expected_hash:
            raise ValueError(f"response hash mismatch: {file_id}")
        responses = {int(row["turn_index"]): row for row in load_jsonl(response_path)}
        global_counts: Counter[str] = Counter()
        speaker_counts: dict[str, Counter[str]] = defaultdict(Counter)
        seen_global_windows: dict[str, set[int]] = defaultdict(set)
        seen_speaker_windows: dict[tuple[str, str], set[int]] = defaultdict(set)
        memory_ready = 0
        global_carry = 0
        speaker_carry = 0
        window_ids = set()

        for turn in sorted(meeting["turns"], key=lambda row: int(row["index"])):
            index = int(turn["index"])
            row = responses[index]
            if row.get("outcome") != "ok":
                raise ValueError(f"non-ok response: {file_id}:{index}")
            speaker = str(turn["speaker_id"])
            window = int(float(turn["start"]) // window_seconds)
            window_ids.add(window)
            current_tokens = set(tokens(str(row.get("text", ""))))
            global_memory = set(ranked_keywords(global_counts, minimum_count, global_cap))
            speaker_memory = set(ranked_keywords(speaker_counts[speaker], minimum_count, speaker_cap))
            if global_memory:
                memory_ready += 1
            if current_tokens & {term for term in global_memory if any(old < window for old in seen_global_windows[term])}:
                global_carry += 1
            if current_tokens & {
                term for term in speaker_memory
                if any(old < window for old in seen_speaker_windows[(speaker, term)])
            }:
                speaker_carry += 1
            global_counts.update(tokens(str(row.get("text", ""))))
            speaker_counts[speaker].update(tokens(str(row.get("text", ""))))
            for term in current_tokens:
                seen_global_windows[term].add(window)
                seen_speaker_windows[(speaker, term)].add(window)

        meeting_row = {
            "file_id": file_id,
            "turns": len(responses),
            "windows": len(window_ids),
            "memory_ready_turns": memory_ready,
            "global_cross_window_carry_turns": global_carry,
            "speaker_cross_window_carry_turns": speaker_carry,
            "final_global_keywords": ranked_keywords(global_counts, minimum_count, global_cap),
            "speakers_with_memory": sum(
                bool(ranked_keywords(counter, minimum_count, speaker_cap))
                for counter in speaker_counts.values()
            ),
        }
        meetings.append(meeting_row)
        total_ready += memory_ready
        total_global_carry += global_carry
        total_speaker_carry += speaker_carry

    gates = config["gates"]
    adequate = [row for row in meetings if row["windows"] >= int(gates["minimum_windows_per_meeting"])]
    passed = (
        len(adequate) >= int(gates["minimum_meetings"])
        and total_ready >= int(gates["minimum_memory_ready_turns"])
        and total_speaker_carry >= int(gates["minimum_speaker_carry_opportunities"])
    )
    return {
        "schema": "agent-loop-stability-supply-read-v1",
        "experiment_id": "E-LOOP-STABILITY-SUPPLY",
        "verdict": "LOOP-STABILITY-SUPPLY-READY" if passed else "LOOP-STABILITY-SUPPLY-INSUFFICIENT",
        "parameters": {
            key: config[key] for key in (
                "window_seconds", "summary_character_cap", "recent_tail_character_cap",
                "global_keyword_cap", "speaker_keyword_cap", "minimum_keyword_count",
            )
        },
        "totals": {
            "meetings": len(meetings),
            "adequate_meetings": len(adequate),
            "turns": sum(row["turns"] for row in meetings),
            "memory_ready_turns": total_ready,
            "global_cross_window_carry_turns": total_global_carry,
            "speaker_cross_window_carry_turns": total_speaker_carry,
        },
        "gates": gates,
        "meetings": meetings,
        "claim_boundary": "Output-only recurrence establishes experiment supply, not correctness or transcription improvement.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--response-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    runtime_path = Path(config["source_runtime"]["path"])
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    if sha256_file(runtime_path) != config["source_runtime"]["sha256"]:
        raise ValueError("runtime hash mismatch")
    result = audit(config, runtime, args.response_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], **result["totals"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
