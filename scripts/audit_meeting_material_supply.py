#!/usr/bin/env python3
"""One-shot gold-read audit for official meeting-material candidate supply."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.state.external_identity_retrieval import (  # noqa: E402
    contains_identity,
    identity_tokens,
    trigger_identity,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def reference_rows(path: Path) -> list[dict[str, object]]:
    output = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="|"):
            try:
                start, end = float(row["ts"]), float(row["endTs"])
            except (KeyError, TypeError, ValueError):
                continue
            token = str(row.get("token", ""))
            if identity_tokens(token):
                output.append({"token": token, "start": start, "end": end})
    return output


def validate_provenance(
    candidate_registry: dict[str, object], material_pages: list[dict[str, object]]
) -> tuple[int, int]:
    page_lookup = {
        (str(row["file_id"]), str(row["document_sha256"]), int(row["page"])): str(row["text"])
        for row in material_pages
    }
    checked = 0
    missing = 0
    for meeting in candidate_registry["meetings"]:
        file_id = str(meeting["file_id"])
        document_sha256 = str(meeting["document_sha256"])
        for candidate in meeting["candidates"]:
            checked += 1
            page_text = page_lookup.get((file_id, document_sha256, int(candidate["page"])), "")
            source_tokens = identity_tokens(str(candidate["source_span"]))
            page_tokens = identity_tokens(page_text)
            width = len(source_tokens)
            if not width or not any(
                page_tokens[index : index + width] == source_tokens
                for index in range(len(page_tokens) - width + 1)
            ):
                missing += 1
    return checked, missing


def score_arm(
    text: str,
    local_reference: str,
    candidates: list[dict[str, object]],
    threshold: float,
    maximum_candidates: int,
    maximum_characters: int,
) -> dict[str, object]:
    opportunities = []
    triggered = []
    exact_count = 0
    for candidate in candidates:
        canonical = str(candidate["canonical"])
        aliases = tuple(str(value) for value in candidate["aliases"])
        exact = contains_identity(text, aliases)
        supported = contains_identity(local_reference, aliases)
        if exact:
            exact_count += 1
        if supported and not exact:
            opportunities.append(canonical)
        trigger = trigger_identity(text, canonical, aliases, threshold)
        if trigger is not None:
            triggered.append((trigger, supported))
    triggered.sort(key=lambda item: (-item[0].similarity, item[0].canonical.casefold()))
    triggered = triggered[:maximum_candidates]
    rendered = "Known terms: " + "; ".join(item[0].canonical for item in triggered) if triggered else ""
    correct = [item[0].canonical for item in triggered if item[1]]
    false = [item[0].canonical for item in triggered if not item[1]]
    return {
        "opportunities": opportunities,
        "triggered": [item[0].canonical for item in triggered],
        "correct": correct,
        "false": false,
        "exact_count": exact_count,
        "rendered_characters": len(rendered),
        "budget_violation": len(rendered) > maximum_characters,
    }


def audit(
    source_registry: dict[str, object],
    candidate_registry: dict[str, object],
    runtime: dict[str, object],
    score: dict[str, object],
    material_pages: list[dict[str, object]],
    response_dir: Path,
    earnings22_root: Path,
) -> dict[str, object]:
    candidates_by_id = {
        str(row["file_id"]): list(row["candidates"]) for row in candidate_registry["meetings"]
    }
    eligible_ids = sorted(file_id for file_id, values in candidates_by_id.items() if values)
    deranged_id = {
        file_id: eligible_ids[(index + 1) % len(eligible_ids)] for index, file_id in enumerate(eligible_ids)
    }
    score_by_id = {str(row["file_id"]): row for row in score["meetings"]}
    source_by_id = {str(row["file_id"]): row for row in source_registry["meetings"]}
    threshold = float(source_registry["similarity_threshold"])
    maximum_candidates = int(source_registry["maximum_candidates_per_turn"])
    maximum_characters = int(source_registry["maximum_context_characters"])
    pass0_hashes = {
        "4430051": "3f446006c6dd0f63c462902969ea268f34c07330cc33fd8f4c60d06d29f20975",
        "4443920": "76866623d1c59a6d253bb32abc7d5a2ce8ae6a0f8394dbb8d0366582a0e3c5b7",
        "4461799": "8664437f7317a22cfe2625c5991fd00ffc4c12588a7b2176edd6360f29a2bd83",
        "4483589": "acf9309a919c5ea8c467e5130ca9401ab4c82f292f48c79798c298b91dd8c96e",
    }
    provenance_checked, provenance_missing = validate_provenance(candidate_registry, material_pages)

    meetings = []
    totals = {
        "turns": 0,
        "opportunity_activations": 0,
        "triggered_activations": 0,
        "correct_activations": 0,
        "false_activations": 0,
        "corrective_turns": 0,
        "triggered_turns": 0,
        "budget_violations": 0,
        "exact_form_trigger_violations": 0,
    }
    deranged_totals = {
        "turns": 0,
        "triggered_activations": 0,
        "correct_activations": 0,
        "false_activations": 0,
        "corrective_turns": 0,
        "triggered_turns": 0,
        "budget_violations": 0,
    }
    examples = []
    for meeting in runtime["meetings"]:
        file_id = str(meeting["file_id"])
        if file_id not in candidates_by_id or not candidates_by_id[file_id]:
            continue
        response_path = response_dir / f"{file_id}-responses.jsonl"
        if sha256_file(response_path) != pass0_hashes[file_id]:
            raise ValueError(f"Pass0 response hash mismatch: {file_id}")
        response_by_turn = {int(row["turn_index"]): row for row in json_rows(response_path)}
        score_row = score_by_id[file_id]
        reference_path = earnings22_root / str(score_row["reference_relative"]).removeprefix("datasets/earnings22/")
        if sha256_file(reference_path) != str(score_row["reference_sha256"]):
            raise ValueError(f"reference hash mismatch: {file_id}")
        references = reference_rows(reference_path)
        local = {
            "file_id": file_id,
            "issuer": source_by_id[file_id]["issuer"],
            "candidate_count": len(candidates_by_id[file_id]),
            "deranged_from": deranged_id[file_id],
            "turns": 0,
            "opportunity_activations": 0,
            "triggered_activations": 0,
            "correct_activations": 0,
            "false_activations": 0,
            "corrective_turns": 0,
            "triggered_turns": 0,
        }
        local_deranged = {key: 0 for key in deranged_totals if key != "turns"}
        local_deranged["turns"] = 0
        for turn in meeting["turns"]:
            turn_index = int(turn["index"])
            text = str(response_by_turn[turn_index].get("text", ""))
            local_reference = " ".join(
                str(row["token"])
                for row in references
                if float(row["end"]) > float(turn["start"]) and float(row["start"]) < float(turn["end"])
            )
            correct_arm = score_arm(
                text,
                local_reference,
                candidates_by_id[file_id],
                threshold,
                maximum_candidates,
                maximum_characters,
            )
            deranged_arm = score_arm(
                text,
                local_reference,
                candidates_by_id[deranged_id[file_id]],
                threshold,
                maximum_candidates,
                maximum_characters,
            )
            local["turns"] += 1
            local["opportunity_activations"] += len(correct_arm["opportunities"])
            local["triggered_activations"] += len(correct_arm["triggered"])
            local["correct_activations"] += len(correct_arm["correct"])
            local["false_activations"] += len(correct_arm["false"])
            local["corrective_turns"] += int(bool(correct_arm["correct"]))
            local["triggered_turns"] += int(bool(correct_arm["triggered"]))
            totals["budget_violations"] += int(correct_arm["budget_violation"])
            local_deranged["turns"] += 1
            local_deranged["triggered_activations"] += len(deranged_arm["triggered"])
            local_deranged["correct_activations"] += len(deranged_arm["correct"])
            local_deranged["false_activations"] += len(deranged_arm["false"])
            local_deranged["corrective_turns"] += int(bool(deranged_arm["correct"]))
            local_deranged["triggered_turns"] += int(bool(deranged_arm["triggered"]))
            local_deranged["budget_violations"] += int(deranged_arm["budget_violation"])
            if (correct_arm["triggered"] or deranged_arm["triggered"]) and len(examples) < 80:
                examples.append(
                    {
                        "file_id": file_id,
                        "turn_index": turn_index,
                        "correct": correct_arm,
                        "deranged": deranged_arm,
                    }
                )
        meetings.append({**local, "deranged": local_deranged})
        for key in (
            "turns",
            "opportunity_activations",
            "triggered_activations",
            "correct_activations",
            "false_activations",
            "corrective_turns",
            "triggered_turns",
        ):
            totals[key] += int(local[key])
        for key in deranged_totals:
            deranged_totals[key] += int(local_deranged[key])

    totals["trigger_precision"] = (
        totals["correct_activations"] / totals["triggered_activations"]
        if totals["triggered_activations"]
        else 0.0
    )
    totals["trigger_recall"] = (
        totals["correct_activations"] / totals["opportunity_activations"]
        if totals["opportunity_activations"]
        else 0.0
    )
    deranged_totals["trigger_precision"] = (
        deranged_totals["correct_activations"] / deranged_totals["triggered_activations"]
        if deranged_totals["triggered_activations"]
        else 0.0
    )
    gates_config = source_registry["gates"]
    distributed = sum(
        int(row["corrective_turns"]) >= int(gates_config["corrective_turns_per_meeting"])
        for row in meetings
    )
    precision_advantage = totals["trigger_precision"] - deranged_totals["trigger_precision"]
    gates = {
        "minimum_eligible_meetings": len(eligible_ids) >= int(gates_config["minimum_eligible_meetings"]),
        "complete_provenance": provenance_checked > 0 and provenance_missing == 0,
        "no_reference_use_in_construction": int(candidate_registry["construction_reference_reads"]) == 0,
        "minimum_corrective_turns": totals["corrective_turns"] >= int(gates_config["minimum_corrective_turns"]),
        "minimum_distributed_meetings": distributed >= int(gates_config["minimum_distributed_meetings"]),
        "minimum_trigger_precision": totals["trigger_precision"] >= float(gates_config["minimum_trigger_precision"]),
        "minimum_trigger_recall": totals["trigger_recall"] >= float(gates_config["minimum_trigger_recall"]),
        "deranged_separation": precision_advantage >= float(gates_config["minimum_precision_advantage_over_deranged"]),
        "no_exact_form_triggers": totals["exact_form_trigger_violations"] == 0,
        "context_budget": totals["budget_violations"] == 0 and deranged_totals["budget_violations"] == 0,
    }
    return {
        "schema": "meeting-material-supply-read-v1",
        "experiment_id": source_registry["experiment_id"],
        "verdict": "MEETING-MATERIAL-SUPPLY-FEASIBLE" if all(gates.values()) else "MEETING-MATERIAL-SUPPLY-INSUFFICIENT",
        "eligible_meetings": eligible_ids,
        "provenance_checked": provenance_checked,
        "provenance_missing": provenance_missing,
        "distributed_meetings": distributed,
        "precision_advantage_over_deranged": precision_advantage,
        "totals": totals,
        "deranged_totals": deranged_totals,
        "gates": gates,
        "meetings": meetings,
        "trigger_examples": examples,
        "claim_boundary": "Zero-model supply feasibility only; no Omni or training-free policy is admitted by this result.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--source-registry", required=True, type=Path)
    parser.add_argument("--candidate-registry", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--score", required=True, type=Path)
    parser.add_argument("--material-pages", required=True, type=Path)
    parser.add_argument("--response-dir", required=True, type=Path)
    parser.add_argument("--earnings22-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; refusing a second read")
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    paths = {
        "source_registry": args.source_registry,
        "candidate_registry": args.candidate_registry,
        "runtime": args.runtime,
        "score": args.score,
        "material_pages": args.material_pages,
        "reader": Path(__file__),
    }
    for label, path in paths.items():
        if sha256_file(path) != str(lock["sha256"][label]):
            parser.error(f"{label} hash mismatch")
    result = audit(
        json.loads(args.source_registry.read_text(encoding="utf-8")),
        json.loads(args.candidate_registry.read_text(encoding="utf-8")),
        json.loads(args.runtime.read_text(encoding="utf-8")),
        json.loads(args.score.read_text(encoding="utf-8")),
        json_rows(args.material_pages),
        args.response_dir,
        args.earnings22_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "totals": result["totals"], "deranged": result["deranged_totals"], "gates": result["gates"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
