#!/usr/bin/env python3
"""Audit whether the material-conditioned Omni flight can be frozen without rereads."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
from pathlib import Path
from statistics import NormalDist


ROOT = Path(__file__).resolve().parents[1]
TURN_ID = re.compile(r"-turn(?P<index>\d+)$")


def load_semantic_gate_module():
    path = Path(__file__).with_name("run_material_gate_ci_semantic_gate.py")
    spec = importlib.util.spec_from_file_location("material_runtime_gate_ci_semantic_gate_frozen", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen semantic gate implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else ROOT / path


def subset_bounds(values: list[float], count: int) -> dict[str, float]:
    if count < 0 or count > len(values):
        raise ValueError("subset count outside available values")
    ordered = sorted(values)
    return {
        "minimum": sum(ordered[:count]),
        "maximum": sum(ordered[len(ordered) - count :]) if count else 0.0,
    }


def required_pairs(*, effect: float, alpha: float, power: float, discordant_fraction: float) -> int:
    if not 0 < effect < 1 or not 0 < alpha < 1 or not 0 < power < 1:
        raise ValueError("effect, alpha, and power must be probabilities")
    if not effect <= discordant_fraction <= 1:
        raise ValueError("discordant fraction must be at least the absolute effect")
    normal = NormalDist()
    z_sum = normal.inv_cdf(1 - alpha / 2) + normal.inv_cdf(power)
    return math.ceil((z_sum**2) * discordant_fraction / (effect**2))


def validate_trace(path: Path, required_fields: list[str]) -> tuple[list[dict[str, object]], list[str]]:
    if not path.exists():
        return [], ["required frozen per-turn dispatch trace is absent"]
    rows: list[dict[str, object]] = []
    errors: list[str] = []
    seen: set[tuple[str, int]] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        row = json.loads(line)
        missing = sorted(set(required_fields) - set(row))
        if missing:
            errors.append(f"trace line {line_number} missing fields: {','.join(missing)}")
            continue
        identity = (str(row["file_id"]), int(row["turn_index"]))
        if identity in seen:
            errors.append(f"duplicate trace identity: {identity[0]}:{identity[1]}")
        seen.add(identity)
        rows.append(row)
    return rows, errors


def receipt_latencies(receipt_path: Path, expected_calls: int) -> list[float]:
    ledger = load_json(receipt_path)["config"]["request_ledger"]
    if len(ledger) != expected_calls:
        raise ValueError(f"receipt call count drift: {receipt_path}")
    indexed: dict[int, float] = {}
    for row in ledger:
        match = TURN_ID.search(str(row["request_id"]))
        if match is None:
            raise ValueError(f"unparseable request id in {receipt_path}")
        indexed[int(match.group("index"))] = float(row["latency_seconds"])
    if sorted(indexed) != list(range(expected_calls)):
        raise ValueError(f"receipt turn order drift: {receipt_path}")
    return [indexed[index] for index in range(expected_calls)]


def run_audit(config_path: Path) -> dict[str, object]:
    config = load_json(config_path)
    inputs = config["inputs"]
    integrity: dict[str, object] = {}
    documents: dict[str, dict[str, object]] = {}
    for name in (
        "registration",
        "pass0_runtime",
        "semantic_config",
        "development_read",
        "confirmation_read",
        "pass0_flight_summary",
    ):
        spec = inputs[name]
        path = resolve(str(spec["path"]))
        actual = sha256_file(path)
        integrity[name] = actual == spec["sha256"]
        documents[name] = load_json(path)

    runtime = documents["pass0_runtime"]
    registration = documents["registration"]
    development = documents["development_read"]
    confirmation = documents["confirmation_read"]
    flight_summary = documents["pass0_flight_summary"]
    frozen = config["frozen_confirmation"]
    errors: list[str] = []

    if not all(bool(value) for value in integrity.values()):
        errors.append("one or more frozen input hashes do not match")
    if development.get("selected_threshold") != frozen["threshold"]:
        errors.append("development threshold drift")
    if confirmation.get("selected_threshold") != frozen["threshold"]:
        errors.append("confirmation threshold drift")
    if confirmation.get("verdict") != "CONSTRUCTION_ISOLATED_SIGNAL_PRESENT":
        errors.append("semantic confirmation did not pass")

    confirmation_meetings = {
        str(row["file_id"]): row for row in runtime["meetings"] if row["split"] == "confirmation"
    }
    confirmation_metrics = {str(row["file_id"]): row for row in confirmation["meetings"]}
    expected_dispatch = {str(key): int(value) for key, value in frozen["per_meeting_dispatch"].items()}
    if set(confirmation_meetings) != set(expected_dispatch) or set(confirmation_metrics) != set(expected_dispatch):
        errors.append("confirmation meeting identities drift")

    flight_dir = resolve(str(inputs["pass0_flight_dir"]))
    semantic_gate = load_semantic_gate_module()
    response_hashes = {str(key): str(value) for key, value in flight_summary["responses_sha256"].items()}
    queries = semantic_gate.build_queries(registration, runtime, flight_dir, response_hashes)
    eligible_by_meeting: dict[str, list[int]] = {}
    for row in queries:
        if row["split"] == "confirmation":
            eligible_by_meeting.setdefault(str(row["file_id"]), []).append(int(row["turn_index"]))
    per_meeting: list[dict[str, object]] = []
    selected_audio_minimum = 0.0
    selected_audio_maximum = 0.0
    pass0_latency_minimum = 0.0
    pass0_latency_maximum = 0.0
    for file_id in sorted(expected_dispatch):
        meeting = confirmation_meetings[file_id]
        metric = confirmation_metrics[file_id]
        turns = meeting["turns"]
        eligible = int(metric["eligible_turns"])
        dispatched = expected_dispatch[file_id]
        eligible_indices = eligible_by_meeting.get(file_id, [])
        if len(eligible_indices) != eligible or int(metric["dispatched_turns"]) != dispatched:
            errors.append(f"aggregate count drift for {file_id}")
        receipt_path = flight_dir / f"{file_id}-receipt.json"
        expected_receipt_hash = str(flight_summary["receipts_sha256"][file_id])
        if sha256_file(receipt_path) != expected_receipt_hash:
            errors.append(f"Pass0 receipt hash drift for {file_id}")
        durations = {int(row["index"]): float(row["duration"]) for row in turns}
        all_latencies = receipt_latencies(receipt_path, len(turns))
        audio_bounds = subset_bounds([durations[index] for index in eligible_indices], dispatched)
        latency_bounds = subset_bounds([all_latencies[index] for index in eligible_indices], dispatched)
        selected_audio_minimum += audio_bounds["minimum"]
        selected_audio_maximum += audio_bounds["maximum"]
        pass0_latency_minimum += latency_bounds["minimum"]
        pass0_latency_maximum += latency_bounds["maximum"]
        per_meeting.append(
            {
                "file_id": file_id,
                "eligible_turns": eligible,
                "aggregate_dispatched_turns": dispatched,
                "dispatch_identities_frozen": False,
                "selected_audio_seconds_bounds": audio_bounds,
                "pass0_latency_seconds_proxy_bounds": latency_bounds,
            }
        )

    trace_spec = config["required_dispatch_trace"]
    trace_path = resolve(str(trace_spec["path"]))
    trace_rows, trace_errors = validate_trace(trace_path, [str(value) for value in trace_spec["required_fields"]])
    errors.extend(trace_errors)
    trace_counts: dict[str, int] = {}
    for row in trace_rows:
        file_id = str(row["file_id"])
        trace_counts[file_id] = trace_counts.get(file_id, 0) + 1
    if trace_rows and trace_counts != expected_dispatch:
        errors.append("dispatch trace counts do not match frozen confirmation aggregates")

    planning = config["power_planning"]
    effect = float(planning["minimum_absolute_effect"])
    alpha = float(planning["two_sided_alpha"])
    target_power = float(planning["power"])
    scenarios = [
        {
            "discordant_fraction": float(value),
            "required_paired_turns": required_pairs(
                effect=effect,
                alpha=alpha,
                power=target_power,
                discordant_fraction=float(value),
            ),
            "aggregate_dispatch_supply_sufficient": int(frozen["dispatched_turns"])
            >= required_pairs(
                effect=effect,
                alpha=alpha,
                power=target_power,
                discordant_fraction=float(value),
            ),
        }
        for value in planning["discordant_fraction_scenarios"]
    ]
    normal = NormalDist()
    z_sum = normal.inv_cdf(1 - alpha / 2) + normal.inv_cdf(target_power)
    maximum_supported_discordance = int(frozen["dispatched_turns"]) * effect**2 / (z_sum**2)

    trace_ready = not trace_errors and len(trace_rows) == int(frozen["dispatched_turns"])
    opportunity_ready = bool(planning["primary_opportunity_census_available"])
    executable = not errors and trace_ready and opportunity_ready
    blockers = []
    if not trace_ready:
        blockers.append("MISSING_FROZEN_PER_TURN_DISPATCH_TRACE")
    if not opportunity_ready:
        blockers.append("MISSING_FROZEN_PRIMARY_OPPORTUNITY_CENSUS")

    calls_per_dispatch = sum(int(value) for value in config["proposed_arms"].values())
    result = {
        "schema": "material-omni-capability-prereg-audit-verdict-v1",
        "experiment_id": config["experiment_id"],
        "evidence_tier": config["evidence_tier"],
        "config_sha256": sha256_file(config_path),
        "integrity": integrity,
        "confirmation_supply": {
            "eligible_turns": int(frozen["eligible_turns"]),
            "aggregate_dispatched_turns": int(frozen["dispatched_turns"]),
            "per_meeting": per_meeting,
            "dispatch_trace_path": str(trace_path.relative_to(ROOT)),
            "dispatch_trace_exists": trace_path.exists(),
            "dispatch_trace_rows": len(trace_rows),
        },
        "budget_if_trace_existed": {
            "R0_retain_calls": 0,
            "R1_correct_dispatch_calls": int(frozen["dispatched_turns"]),
            "R2_deranged_dispatch_calls": int(frozen["dispatched_turns"]),
            "total_omni_calls": int(frozen["dispatched_turns"]) * calls_per_dispatch,
            "selected_audio_seconds_per_active_arm_bounds": {
                "minimum": selected_audio_minimum,
                "maximum": selected_audio_maximum,
            },
            "total_model_contact_audio_seconds_bounds": {
                "minimum": selected_audio_minimum * calls_per_dispatch,
                "maximum": selected_audio_maximum * calls_per_dispatch,
            },
            "pass0_latency_proxy_seconds_for_two_active_arms_bounds": {
                "minimum": pass0_latency_minimum * calls_per_dispatch,
                "maximum": pass0_latency_maximum * calls_per_dispatch,
                "claim_limit": "Proxy only; material prompts may change latency.",
            },
        },
        "power_planning": {
            "minimum_absolute_effect": effect,
            "two_sided_alpha": alpha,
            "power": target_power,
            "scenarios": scenarios,
            "maximum_discordant_fraction_supported_by_aggregate_dispatch_supply": maximum_supported_discordance,
            "claim_limit": "Aggregate dispatch count is not a frozen primary-opportunity census.",
        },
        "gates": {
            "frozen_input_integrity": all(bool(value) for value in integrity.values()) and not any("drift" in error for error in errors),
            "frozen_per_turn_dispatch_trace": trace_ready,
            "frozen_primary_opportunity_census": opportunity_ready,
            "exact_runtime_manifest_can_be_built": executable,
            "one_shot_reader_can_be_bound": executable,
        },
        "blockers": blockers,
        "verdict": "PREREGISTRATION_READY" if executable else "NOT_RUN_MISSING_FROZEN_FLIGHT_INPUTS",
        "next_action": (
            "Freeze runtime manifest and reader, then request Omni authorization."
            if executable
            else "Do not rerun confirmation. Obtain a prospectively persisted selector trace on a new surface or explicitly authorize a separately registered trace-materialization read."
        ),
        "model_contact": {"reference_reads": 0, "embedding_calls": 0, "omni_calls": 0},
        "errors": errors,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("output directory exists; refusing to overwrite a frozen audit")
    result = run_audit(args.config)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "verdict.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"verdict": result["verdict"], "blockers": result["blockers"]}, indent=2))
    return 0 if all(bool(value) for value in result["integrity"].values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
