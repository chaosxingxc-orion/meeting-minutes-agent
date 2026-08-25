#!/usr/bin/env python3
"""One-shot registered read for E-LOOP-STABILITY."""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import csv
import difflib
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

from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402
from meeting_minutes_agent.state.sliding_memory import (  # noqa: E402
    MemoryLimits,
    build_meeting_memory,
    context_hash,
    render_context,
)


_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
_ALLOWED_CLASSES = frozenset({"ABBREVIATION", "ALPHANUMERIC"})


def normalize_tokens(text: str) -> list[str]:
    value = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    return _TOKEN.findall(value)


def edit_distance(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_token in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_token in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_token != right_token),
                )
            )
        previous = current
    return previous[-1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_manifest(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "agent-loop-stability-runtime-v1":
        raise ValueError("manifest schema mismatch")
    expected = config_hash({key: item for key, item in value.items() if key != "content_hash"})
    if value.get("content_hash") != expected:
        raise ValueError("manifest content hash mismatch")
    return value


def _rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _reference(path: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    tokens = []
    active: dict[str, dict[str, object]] = {}
    entities = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="|"):
            if not row.get("ts") or not row.get("endTs"):
                continue
            try:
                start, end = float(row["ts"]), float(row["endTs"])
            except ValueError:
                continue
            normalized = normalize_tokens(row["token"])
            if not normalized:
                continue
            index = len(tokens)
            tokens.append({"token": normalized[0], "start": start, "end": end})
            current = set()
            for raw in ast.literal_eval(row.get("tags", "[]")):
                entity_id, separator, entity_class = raw.partition(":")
                if not separator or entity_class not in _ALLOWED_CLASSES:
                    continue
                current.add(entity_id)
                value = active.setdefault(entity_id, {"class": entity_class, "indices": [], "start": start, "end": end})
                value["indices"].append(index)  # type: ignore[union-attr]
                value["end"] = end
            for entity_id in list(active):
                if entity_id not in current and active[entity_id]["indices"]:
                    value = active.pop(entity_id)
                    value["surface"] = " ".join(str(tokens[i]["token"]) for i in value["indices"])  # type: ignore[union-attr]
                    entities.append(value)
    for value in active.values():
        value["surface"] = " ".join(str(tokens[i]["token"]) for i in value["indices"])  # type: ignore[union-attr]
        entities.append(value)
    return tokens, entities


def observed_form(reference: list[str], hypothesis: list[str], start: int, end: int) -> str:
    target = reference[start:end]
    width = len(target)
    for index in range(len(hypothesis) - width + 1):
        if hypothesis[index : index + width] == target:
            return " ".join(target)
    collected = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=reference, b=hypothesis, autojunk=False).get_opcodes():
        if max(i1, start) >= min(i2, end):
            continue
        if tag == "equal":
            collected.extend(hypothesis[j1 + max(start, i1) - i1 : j1 + min(end, i2) - i1])
        elif tag == "replace":
            collected.extend(hypothesis[j1:j2])
    return " ".join(collected) if collected else "<DEL>"


def consistency(forms: dict[tuple[str, str, str], list[str]], file_id: str) -> float | None:
    numerator = 0
    denominator = 0
    for (meeting, _, _), values in forms.items():
        if meeting != file_id or len(values) < 3:
            continue
        numerator += max(Counter(values).values())
        denominator += len(values)
    return numerator / denominator if denominator else None


def choose_verdict(gates: dict[str, bool]) -> str:
    structural = gates["complete"] and gates["context_hash_replay"] and gates["context_budget"]
    stable = gates["consistency_vs_bare"] and gates["consistency_vs_deranged"] and gates["convergence"]
    safety = gates["wer_noninferior"] and gates["worst_speaker_noninferior"] and gates["unsupported_activation"] and gates["language_drift"]
    if not structural:
        return "LOOP-STABILITY-READ-INVALID"
    if stable and safety:
        return "LOOP-STABILITY-REACHABLE"
    if stable:
        return "CONTEXT-STABLE-BUT-HARMFUL"
    return "LOOP-STABILITY-NOT-REACHED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--phase1-responses", required=True, type=Path)
    parser.add_argument("--round2-responses", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; refusing second read")
    manifest = _load_manifest(args.manifest)
    runtime_lock, score_lock = manifest["source_runtime"], manifest["source_score"]
    runtime_path, score_path = ROOT / runtime_lock["path"], ROOT / score_lock["path"]
    if sha256_file(runtime_path) != runtime_lock["sha256"] or sha256_file(score_path) != score_lock["sha256"]:
        raise ValueError("source manifest hash mismatch")
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    score = json.loads(score_path.read_text(encoding="utf-8"))
    phase1, round2 = _rows(args.phase1_responses), _rows(args.round2_responses)
    all_rows = phase1 + round2
    by_key = {(str(row["file_id"]), int(row["turn_index"]), str(row["arm"])): row for row in all_rows}
    expected_arms = list(manifest["arms"]) + [str(manifest["round2_arm"])]
    expected = {
        (str(meeting["file_id"]), int(turn["index"]), arm)
        for meeting in runtime["meetings"] for turn in meeting["turns"] for arm in expected_arms
    }
    complete = len(by_key) == len(all_rows) == len(expected) and set(by_key) == expected
    limits = MemoryLimits(**{key: int(value) for key, value in manifest["memory_limits"].items()})
    replay_matches = 0
    replay_total = 0
    context_budget_ok = 0
    maximum_context = limits.summary_characters + limits.recent_characters + 1600
    metrics = {arm: {"errors": 0, "reference_words": 0, "drift": 0, "unsupported": 0, "unsupported_supply": 0} for arm in expected_arms}
    speaker_scores: dict[str, dict[tuple[str, str], list[int]]] = {arm: defaultdict(lambda: [0, 0]) for arm in expected_arms}
    meeting_scores: dict[str, dict[str, list[int]]] = {arm: defaultdict(lambda: [0, 0]) for arm in expected_arms}
    forms: dict[str, dict[tuple[str, str, str], list[str]]] = {arm: defaultdict(list) for arm in expected_arms}
    score_by_id = {str(row["file_id"]): row for row in score["meetings"]}
    hypotheses: dict[tuple[str, int, str], list[str]] = {}

    for meeting in runtime["meetings"]:
        file_id = str(meeting["file_id"])
        source_lock = manifest["source_passes"][file_id]
        source_path = ROOT / source_lock["path"]
        if sha256_file(source_path) != source_lock["sha256"]:
            raise ValueError(f"source pass hash mismatch: {file_id}")
        source_rows = _rows(source_path)
        memory1 = build_meeting_memory(source_rows, limits)
        l3_rows = [by_key[(file_id, int(turn["index"]), "L3-speaker")] for turn in meeting["turns"]]
        memory2 = build_meeting_memory(l3_rows, limits)
        histories = {arm: [] for arm in expected_arms}
        reference_path = args.data_dir / score_by_id[file_id]["reference_relative"]
        if sha256_file(reference_path) != score_by_id[file_id]["reference_sha256"]:
            raise ValueError(f"reference hash mismatch: {file_id}")
        ref_tokens, entities = _reference(reference_path)
        for turn in meeting["turns"]:
            turn_index = int(turn["index"])
            local_indices = [
                index for index, token in enumerate(ref_tokens)
                if float(token["end"]) > float(turn["start"]) and float(token["start"]) < float(turn["end"])
            ]
            local_reference = [str(ref_tokens[index]["token"]) for index in local_indices]
            for arm in expected_arms:
                row = by_key[(file_id, turn_index, arm)]
                render_arm = "L3-speaker" if arm == "L3-round2" else arm
                memory = memory2 if arm == "L3-round2" else memory1
                rendered = render_context(render_arm, str(turn["speaker_id"]), memory, histories[arm], limits)
                replay_total += 1
                replay_matches += context_hash(rendered) == row["context_sha256"]
                context_budget_ok += int(row["context_characters"] <= maximum_context)
                histories[arm].append(row)
                hypothesis = normalize_tokens(str(row["text"]))
                hypotheses[(file_id, turn_index, arm)] = hypothesis
                errors = edit_distance(local_reference, hypothesis)
                metrics[arm]["errors"] += errors
                metrics[arm]["reference_words"] += len(local_reference)
                speaker_scores[arm][(file_id, str(turn["speaker_id"]))][0] += errors
                speaker_scores[arm][(file_id, str(turn["speaker_id"]))][1] += len(local_reference)
                meeting_scores[arm][file_id][0] += errors
                meeting_scores[arm][file_id][1] += len(local_reference)
                text = str(row["text"])
                metrics[arm]["drift"] += int(any(ord(char) > 127 for char in text) and not any(char.isascii() and char.isalpha() for char in text))
                reference_set, hypothesis_set = set(local_reference), set(hypothesis)
                for term in row.get("injected_terms", []):
                    normalized = normalize_tokens(str(term))
                    if len(normalized) != 1 or normalized[0] in reference_set:
                        continue
                    metrics[arm]["unsupported_supply"] += 1
                    metrics[arm]["unsupported"] += int(normalized[0] in hypothesis_set)
            for entity in entities:
                midpoint = (float(entity["start"]) + float(entity["end"])) / 2
                if not (float(turn["start"]) <= midpoint < float(turn["end"])):
                    continue
                entity_indices = entity["indices"]
                if not local_indices or not all(index in local_indices for index in entity_indices):
                    continue
                start = local_indices.index(entity_indices[0])
                end = start + len(entity_indices)
                for arm in expected_arms:
                    forms[arm][(file_id, str(turn["speaker_id"]), str(entity["surface"]))].append(
                        observed_form(local_reference, hypotheses[(file_id, turn_index, arm)], start, end)
                    )

    arm_results = {}
    consistency_by_meeting = {arm: {} for arm in expected_arms}
    for arm in expected_arms:
        for meeting in runtime["meetings"]:
            file_id = str(meeting["file_id"])
            consistency_by_meeting[arm][file_id] = consistency(forms[arm], file_id)
        values = [value for value in consistency_by_meeting[arm].values() if value is not None]
        worst_speaker = max(errors / words for errors, words in speaker_scores[arm].values() if words)
        arm_results[arm] = {
            "wer": metrics[arm]["errors"] / metrics[arm]["reference_words"],
            "worst_speaker_wer": worst_speaker,
            "language_drift_outputs": metrics[arm]["drift"],
            "unsupported_activation_rate": (
                metrics[arm]["unsupported"] / metrics[arm]["unsupported_supply"]
                if metrics[arm]["unsupported_supply"] else 0.0
            ),
            "consistency": sum(values) / len(values) if values else None,
            "consistency_by_meeting": consistency_by_meeting[arm],
        }

    def delta(left_arm: str, right_arm: str) -> tuple[float, dict[str, float]]:
        total_errors = total_words = 0
        per_meeting = {}
        for meeting in runtime["meetings"]:
            file_id = str(meeting["file_id"])
            errors = words = 0
            for turn in meeting["turns"]:
                left = hypotheses[(file_id, int(turn["index"]), left_arm)]
                right = hypotheses[(file_id, int(turn["index"]), right_arm)]
                errors += edit_distance(left, right)
                words += max(len(left), len(right), 1)
            per_meeting[file_id] = errors / words
            total_errors += errors
            total_words += words
        return total_errors / total_words, per_meeting

    first_delta, first_by_meeting = delta("L3-speaker", "L0-bare")
    second_delta, second_by_meeting = delta("L3-round2", "L3-speaker")
    convergence_ratio = second_delta / first_delta if first_delta else (0.0 if second_delta == 0 else float("inf"))
    gates_config = manifest["gates"]
    comparable = [file_id for file_id, value in consistency_by_meeting["L3-speaker"].items() if value is not None]
    better_bare = sum(
        consistency_by_meeting["L3-speaker"][file_id] > consistency_by_meeting["L0-bare"][file_id]
        for file_id in comparable
    )
    better_deranged = sum(
        consistency_by_meeting["L3-speaker"][file_id] > consistency_by_meeting["L4-deranged"][file_id]
        for file_id in comparable
    )
    gates = {
        "complete": complete,
        "context_hash_replay": replay_matches / replay_total == gates_config["context_hash_replay_rate"],
        "context_budget": context_budget_ok / replay_total == gates_config["context_budget_rate"],
        "consistency_vs_bare": (
            arm_results["L3-speaker"]["consistency"] is not None
            and arm_results["L0-bare"]["consistency"] is not None
            and arm_results["L3-speaker"]["consistency"] - arm_results["L0-bare"]["consistency"]
            >= gates_config["minimum_consistency_gain_vs_bare"]
            and better_bare >= gates_config["minimum_meetings_consistency_better_than_bare"]
        ),
        "consistency_vs_deranged": better_deranged >= gates_config["minimum_meetings_consistency_better_than_deranged"],
        "convergence": convergence_ratio <= gates_config["maximum_convergence_ratio"],
        "wer_noninferior": arm_results["L3-speaker"]["wer"] - arm_results["L0-bare"]["wer"] <= gates_config["maximum_wer_increase"],
        "worst_speaker_noninferior": arm_results["L3-speaker"]["worst_speaker_wer"] - arm_results["L0-bare"]["worst_speaker_wer"] <= gates_config["maximum_worst_speaker_wer_increase"],
        "unsupported_activation": arm_results["L3-speaker"]["unsupported_activation_rate"] <= gates_config["maximum_unsupported_activation_rate"],
        "language_drift": arm_results["L3-speaker"]["language_drift_outputs"] - arm_results["L0-bare"]["language_drift_outputs"] <= gates_config["maximum_language_drift_increase"],
    }
    verdict = choose_verdict(gates)
    result = {
        "schema": "agent-loop-stability-read-v1",
        "experiment_id": "E-LOOP-STABILITY",
        "verdict": verdict,
        "manifest_content_hash": manifest["content_hash"],
        "counts": {"phase1": len(phase1), "round2": len(round2), "expected": len(expected)},
        "context_replay": {"matches": replay_matches, "total": replay_total, "within_budget": context_budget_ok},
        "arms": arm_results,
        "convergence": {
            "l3_vs_bare_delta": first_delta,
            "round2_vs_l3_delta": second_delta,
            "ratio": convergence_ratio,
            "l3_vs_bare_by_meeting": first_by_meeting,
            "round2_vs_l3_by_meeting": second_by_meeting,
        },
        "consistency_direction": {"better_than_bare_meetings": better_bare, "better_than_deranged_meetings": better_deranged},
        "gates": gates,
        "registered_thresholds": gates_config,
        "claim_boundary": manifest["claim_boundary"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": verdict, "gates": gates, "convergence": result["convergence"], "arms": arm_results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
