#!/usr/bin/env python3
"""One-shot scorer for repeated, stable Earnings-22 Pass-0 errors."""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import csv
import difflib
import json
from pathlib import Path
import re
import sys
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.client.receipts import hash_model_file  # noqa: E402
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402


ALLOWED_CLASSES = frozenset({"ABBREVIATION", "ALPHANUMERIC"})
MIN_REPETITIONS = 3
MIN_MAJORITY_PURITY = 0.70
MIN_STABLE_WRONG_GROUPS = 10
MIN_STABLE_WRONG_MEETINGS = 3
MIN_ANCHORED_STABLE_WRONG_GROUPS = 2
MIN_ANCHORED_STABLE_WRONG_MEETINGS = 2
_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")


def normalize_tokens(text: str) -> list[str]:
    value = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    return _TOKEN.findall(value)


def observed_form(reference: list[str], hypothesis: list[str], start: int, end: int) -> str:
    """Extract the deterministic hypothesis rendering aligned to one reference span."""
    target = reference[start:end]
    width = len(target)
    for index in range(len(hypothesis) - width + 1):
        if hypothesis[index : index + width] == target:
            return " ".join(target)
    collected: list[str] = []
    matcher = difflib.SequenceMatcher(a=reference, b=hypothesis, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if max(i1, start) >= min(i2, end):
            continue
        if tag == "equal":
            left = j1 + max(start, i1) - i1
            right = j1 + min(end, i2) - i1
            collected.extend(hypothesis[left:right])
        elif tag == "replace":
            collected.extend(hypothesis[j1:j2])
    return " ".join(collected) if collected else "<DEL>"


def classify_groups(occurrences: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for occurrence in occurrences:
        grouped[(str(occurrence["file_id"]), str(occurrence["speaker_id"]), str(occurrence["surface"]))].append(occurrence)
    output = []
    for (file_id, speaker, surface), rows in sorted(grouped.items()):
        forms = Counter(str(row["observed_form"]) for row in rows)
        majority_form, majority_count = sorted(forms.items(), key=lambda item: (-item[1], item[0]))[0]
        purity = majority_count / len(rows)
        stable = len(rows) >= MIN_REPETITIONS and purity >= MIN_MAJORITY_PURITY
        category = "insufficient-repeat"
        if stable:
            category = "stable-correct" if majority_form == surface else "stable-wrong"
        elif len(rows) >= MIN_REPETITIONS:
            category = "unstable"
        output.append(
            {
                "file_id": file_id,
                "speaker_id": speaker,
                "surface": surface,
                "entity_class": rows[0]["entity_class"],
                "occurrences": len(rows),
                "majority_form": majority_form,
                "majority_count": majority_count,
                "majority_purity": purity,
                "category": category,
                "legal_ticker_anchor": bool(rows[0]["legal_ticker_anchor"]),
            }
        )
    return output


def choose_decision(groups: list[dict[str, object]]) -> tuple[str, dict[str, bool]]:
    wrong = [row for row in groups if row["category"] == "stable-wrong"]
    anchored = [row for row in wrong if row["legal_ticker_anchor"]]
    gates = {
        "stable_wrong_groups": len(wrong) >= MIN_STABLE_WRONG_GROUPS,
        "stable_wrong_meetings": len({row["file_id"] for row in wrong}) >= MIN_STABLE_WRONG_MEETINGS,
        "anchored_stable_wrong_groups": len(anchored) >= MIN_ANCHORED_STABLE_WRONG_GROUPS,
        "anchored_stable_wrong_meetings": len({row["file_id"] for row in anchored}) >= MIN_ANCHORED_STABLE_WRONG_MEETINGS,
    }
    if gates["stable_wrong_groups"] and gates["stable_wrong_meetings"]:
        decision = "STABLE-ERROR-SUPPLY-READY" if all(gates.values()) else "STABLE-ERROR-SUPPLY-PRESENT-ANCHOR-LIMITED"
    else:
        decision = "INSUFFICIENT-STABLE-ERROR-SUPPLY"
    return decision, gates


def _load_json(path: Path, schema: str) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != schema:
        raise ValueError(f"schema mismatch: {path}")
    expected = config_hash({key: item for key, item in value.items() if key != "content_hash"})
    if value.get("content_hash") != expected:
        raise ValueError(f"content hash mismatch: {path}")
    return value


def _reference(path: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    tokens = []
    active: dict[str, dict[str, object]] = {}
    entities = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="|")
        for row in reader:
            if not row.get("ts") or not row.get("endTs"):
                continue
            try:
                start, end = float(row["ts"]), float(row["endTs"])
            except ValueError:
                continue
            normalized = normalize_tokens(row["token"])
            if not normalized:
                continue
            token_index = len(tokens)
            tokens.append({"token": normalized[0], "start": start, "end": end})
            tags = ast.literal_eval(row.get("tags", "[]"))
            current = set()
            for raw in tags:
                entity_id, separator, entity_class = raw.partition(":")
                if not separator or entity_class not in ALLOWED_CLASSES:
                    continue
                current.add(entity_id)
                value = active.setdefault(entity_id, {"class": entity_class, "indices": [], "start": start, "end": end})
                value["indices"].append(token_index)  # type: ignore[union-attr]
                value["end"] = end
            for entity_id in list(active):
                if entity_id not in current and active[entity_id]["indices"]:
                    value = active.pop(entity_id)
                    indices = value["indices"]
                    surface = " ".join(str(tokens[index]["token"]) for index in indices)  # type: ignore[union-attr]
                    entities.append({**value, "surface": surface})
    for value in active.values():
        indices = value["indices"]
        surface = " ".join(str(tokens[index]["token"]) for index in indices)  # type: ignore[union-attr]
        entities.append({**value, "surface": surface})
    return tokens, entities


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--score", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--responses-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; refusing a second read")
    runtime = _load_json(args.runtime, "earnings22-stable-error-runtime-v1")
    score = _load_json(args.score, "earnings22-stable-error-score-v1")
    if score["runtime_content_hash"] != runtime["content_hash"]:
        raise ValueError("runtime/score binding mismatch")
    score_by_id = {row["file_id"]: row for row in score["meetings"]}
    occurrences = []
    response_count = 0
    for meeting in runtime["meetings"]:
        file_id = meeting["file_id"]
        response_path = args.responses_dir / f"{file_id}-responses.jsonl"
        responses = [json.loads(line) for line in response_path.read_text(encoding="utf-8").splitlines()]
        by_turn = {int(row["turn_index"]): row for row in responses if row.get("outcome") == "ok"}
        expected = {int(turn["index"]) for turn in meeting["turns"]}
        if set(by_turn) != expected or len(responses) != len(expected):
            raise ValueError(f"incomplete or duplicate responses: {file_id}")
        response_count += len(responses)
        score_row = score_by_id[file_id]
        reference_path = args.data_dir / score_row["reference_relative"]
        if hash_model_file(reference_path) != score_row["reference_sha256"]:
            raise ValueError(f"reference hash mismatch: {file_id}")
        ref_tokens, entities = _reference(reference_path)
        ticker = " ".join(normalize_tokens(str(score_row["ticker_anchor"])))
        for entity in entities:
            midpoint = (float(entity["start"]) + float(entity["end"])) / 2
            candidate_turns = [turn for turn in meeting["turns"] if float(turn["start"]) <= midpoint < float(turn["end"])]
            if not candidate_turns:
                continue
            turn = max(candidate_turns, key=lambda row: (float(row["duration"]), -int(row["index"])))
            segment_indices = [index for index, token in enumerate(ref_tokens) if float(token["end"]) > float(turn["start"]) and float(token["start"]) < float(turn["end"])]
            if not segment_indices:
                continue
            local_reference = [str(ref_tokens[index]["token"]) for index in segment_indices]
            entity_indices = entity["indices"]
            if not all(index in segment_indices for index in entity_indices):
                continue
            local_start = segment_indices.index(entity_indices[0])
            local_end = local_start + len(entity_indices)
            hypothesis = normalize_tokens(str(by_turn[int(turn["index"])]["text"]))
            surface = str(entity["surface"])
            occurrences.append(
                {
                    "file_id": file_id,
                    "speaker_id": turn["speaker_id"],
                    "surface": surface,
                    "entity_class": entity["class"],
                    "turn_index": turn["index"],
                    "observed_form": observed_form(local_reference, hypothesis, local_start, local_end),
                    "legal_ticker_anchor": bool(ticker and surface == ticker),
                }
            )
    groups = classify_groups(occurrences)
    decision, gates = choose_decision(groups)
    categories = Counter(str(row["category"]) for row in groups)
    result = {
        "schema": "earnings22-stable-error-supply-read-v1",
        "decision": decision,
        "thresholds": {
            "minimum_repetitions": MIN_REPETITIONS,
            "minimum_majority_purity": MIN_MAJORITY_PURITY,
            "minimum_stable_wrong_groups": MIN_STABLE_WRONG_GROUPS,
            "minimum_stable_wrong_meetings": MIN_STABLE_WRONG_MEETINGS,
            "minimum_anchored_stable_wrong_groups": MIN_ANCHORED_STABLE_WRONG_GROUPS,
            "minimum_anchored_stable_wrong_meetings": MIN_ANCHORED_STABLE_WRONG_MEETINGS,
        },
        "response_count": response_count,
        "target_occurrences": len(occurrences),
        "groups": len(groups),
        "categories": dict(sorted(categories.items())),
        "decision_gates": gates,
        "stable_wrong_meetings": len({row["file_id"] for row in groups if row["category"] == "stable-wrong"}),
        "anchored_stable_wrong_groups": sum(row["category"] == "stable-wrong" and row["legal_ticker_anchor"] for row in groups),
        "anchored_stable_wrong_meetings": len({row["file_id"] for row in groups if row["category"] == "stable-wrong" and row["legal_ticker_anchor"]}),
        "per_group": groups,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: result[key] for key in ("decision", "response_count", "target_occurrences", "groups", "categories", "decision_gates")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
