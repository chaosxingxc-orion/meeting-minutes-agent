#!/usr/bin/env python3
"""One-shot gold-read audit for externally registered company identities."""

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


_EXPECTED_CONFIG_SHA256 = "c1e003ed2b6180aa9c66ec7c98298b55e52261321afa3e0dc85ee75eeca20d48"
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


def response_rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def reference_tokens(path: Path) -> list[dict[str, object]]:
    output = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="|"):
            try:
                start, end = float(row["ts"]), float(row["endTs"])
            except (KeyError, TypeError, ValueError):
                continue
            tokens = identity_tokens(row.get("token", ""))
            if tokens:
                output.append({"token": tokens[0], "start": start, "end": end})
    return output


def audit(
    registry: dict[str, object],
    runtime: dict[str, object],
    score: dict[str, object],
    response_dir: Path,
    data_dir: Path,
) -> dict[str, object]:
    registry_by_id = {str(row["file_id"]): row for row in registry["meetings"]}
    score_by_id = {str(row["file_id"]): row for row in score["meetings"]}
    gates_config = registry["gates"]
    threshold = float(registry["similarity_threshold"])
    context_limit = int(registry["maximum_context_characters"])
    meetings = []
    totals = {
        "turns": 0,
        "reference_identity_turns": 0,
        "exact_pass0_identity_turns": 0,
        "corrective_opportunity_turns": 0,
        "triggered_turns": 0,
        "triggered_corrective_turns": 0,
        "false_trigger_turns": 0,
        "context_budget_violations": 0,
        "exact_identity_trigger_violations": 0,
        "construction_reference_reads": 0,
    }
    trigger_examples = []
    for meeting in runtime["meetings"]:
        file_id = str(meeting["file_id"])
        identity = registry_by_id[file_id]
        aliases = tuple(identity["aliases"])
        canonical = str(identity["canonical"])
        response_path = response_dir / f"{file_id}-responses.jsonl"
        if sha256_file(response_path) != _EXPECTED_SOURCE_SHA256[file_id]:
            raise ValueError(f"Pass0 response hash mismatch: {file_id}")
        by_turn = {int(row["turn_index"]): row for row in response_rows(response_path)}
        score_row = score_by_id[file_id]
        reference_path = data_dir / str(score_row["reference_relative"])
        if sha256_file(reference_path) != score_row["reference_sha256"]:
            raise ValueError(f"reference hash mismatch: {file_id}")
        refs = reference_tokens(reference_path)
        local = {
            "file_id": file_id,
            "ticker": identity["ticker"],
            "canonical": canonical,
            "turns": 0,
            "reference_identity_turns": 0,
            "exact_pass0_identity_turns": 0,
            "corrective_opportunity_turns": 0,
            "triggered_turns": 0,
            "triggered_corrective_turns": 0,
            "false_trigger_turns": 0,
        }
        for turn in meeting["turns"]:
            turn_index = int(turn["index"])
            text = str(by_turn[turn_index].get("text", ""))
            exact = contains_identity(text, aliases)
            trigger = trigger_identity(text, canonical, aliases, threshold)
            local_reference = " ".join(
                str(token["token"])
                for token in refs
                if float(token["end"]) > float(turn["start"]) and float(token["start"]) < float(turn["end"])
            )
            reference_has_identity = contains_identity(local_reference, aliases)
            opportunity = reference_has_identity and not exact
            triggered = trigger is not None
            corrective = triggered and opportunity
            false_trigger = triggered and not reference_has_identity
            totals["exact_identity_trigger_violations"] += int(triggered and exact)
            local["turns"] += 1
            local["reference_identity_turns"] += int(reference_has_identity)
            local["exact_pass0_identity_turns"] += int(exact)
            local["corrective_opportunity_turns"] += int(opportunity)
            local["triggered_turns"] += int(triggered)
            local["triggered_corrective_turns"] += int(corrective)
            local["false_trigger_turns"] += int(false_trigger)
            if triggered and len(canonical) > context_limit:
                totals["context_budget_violations"] += 1
            if triggered and len(trigger_examples) < 40:
                trigger_examples.append({
                    "file_id": file_id,
                    "turn_index": turn_index,
                    "observed_surface": trigger.observed_surface,
                    "canonical": canonical,
                    "similarity": trigger.similarity,
                    "reference_supported": reference_has_identity,
                    "corrective": corrective,
                })
        meetings.append(local)
        for key in (
            "turns",
            "reference_identity_turns",
            "exact_pass0_identity_turns",
            "corrective_opportunity_turns",
            "triggered_turns",
            "triggered_corrective_turns",
            "false_trigger_turns",
        ):
            totals[key] += local[key]
    totals["trigger_precision"] = (
        totals["triggered_corrective_turns"] / totals["triggered_turns"] if totals["triggered_turns"] else 0.0
    )
    totals["trigger_recall"] = (
        totals["triggered_corrective_turns"] / totals["corrective_opportunity_turns"]
        if totals["corrective_opportunity_turns"]
        else 0.0
    )
    distributed_meetings = sum(
        row["triggered_corrective_turns"] >= int(gates_config["corrective_turns_per_meeting"])
        for row in meetings
    )
    gates = {
        "minimum_corrective_turns": totals["triggered_corrective_turns"] >= int(gates_config["minimum_corrective_turns"]),
        "minimum_distributed_meetings": distributed_meetings >= int(gates_config["minimum_distributed_meetings"]),
        "minimum_trigger_precision": totals["trigger_precision"] >= float(gates_config["minimum_trigger_precision"]),
        "minimum_trigger_recall": totals["trigger_recall"] >= float(gates_config["minimum_trigger_recall"]),
        "no_exact_identity_triggers": totals["exact_identity_trigger_violations"] == 0,
        "no_reference_use_in_construction": totals["construction_reference_reads"] == 0,
        "context_budget": totals["context_budget_violations"] == 0,
    }
    return {
        "schema": "external-company-identity-supply-read-v1",
        "experiment_id": registry["experiment_id"],
        "verdict": (
            "EXTERNAL-COMPANY-IDENTITY-SUPPLY-FEASIBLE"
            if all(gates.values())
            else "EXTERNAL-COMPANY-IDENTITY-SUPPLY-INSUFFICIENT"
        ),
        "provenance": registry["provenance"],
        "runtime_admissibility": registry["runtime_admissibility"],
        "thresholds": gates_config,
        "totals": totals,
        "distributed_meetings": distributed_meetings,
        "gates": gates,
        "meetings": meetings,
        "trigger_examples": trigger_examples,
        "claim_boundary": (
            "This one-shot gold read measures supply feasibility only. External-public-registry provenance "
            "is not currently M0 and remains blocked from runtime pending an explicit ruling."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--score", required=True, type=Path)
    parser.add_argument("--response-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; refusing a second read")
    for path, expected, label in (
        (args.registry, _EXPECTED_CONFIG_SHA256, "registry"),
        (args.runtime, _EXPECTED_RUNTIME_SHA256, "runtime"),
        (args.score, _EXPECTED_SCORE_SHA256, "score"),
    ):
        if sha256_file(path) != expected:
            parser.error(f"{label} hash mismatch")
    result = audit(
        json.loads(args.registry.read_text(encoding="utf-8")),
        json.loads(args.runtime.read_text(encoding="utf-8")),
        json.loads(args.score.read_text(encoding="utf-8")),
        args.response_dir,
        args.data_dir,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "totals": result["totals"], "gates": result["gates"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
