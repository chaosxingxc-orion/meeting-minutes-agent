#!/usr/bin/env python3
"""Run the frozen zero-model E4 disjoint-policy power census."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.probes.e4_disjoint_power import build_scenario, cluster_summary  # noqa: E402
from meeting_minutes_agent.probes.e4_power import dialogue_stats  # noqa: E402

EXPECTED_JSONL_SHA256 = "4bbf64387d1c581df2c7ab5db9af4461e1112ee489377b67084c9b40cb6d45e8"
EXPECTED_EXCLUSIONS = 299
SEED = "e4-disjoint-power-2026-08-21-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def entry_ids(path: Path) -> set[str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return {str(item["uniq_id"]) for item in document["entries"]}


def render_report(result: dict[str, object]) -> str:
    corpus = result["corpus"]
    lines = [
        f"decision: {result['decision']}",
        "predicate_prevalence_status: scenario-only; not measured on unseen Pass-0 state",
        f"excluded_dialogues: {result['exclusion']['count']}",
        f"remaining_dialogues: {corpus['remaining_dialogues']}",
        f"eligible_dialogues: {corpus['cluster_summary']['eligible_dialogues']}",
        f"remaining_carry_mentions: {corpus['carry_mentions']}",
        f"remaining_target_turns: {corpus['target_turns']}",
        "",
        "mde\tprevalence\trequired_raw_carry\tdialogues\tdedup_calls\tdedup_audio_hours\tnaive_calls",
    ]
    for scenario in result["scenarios"]:
        if not scenario["feasible"]:
            lines.append(
                f"{scenario['mde']:.3f}\t{scenario['assumed_predicate_prevalence']:.6f}\t"
                f"INFEASIBLE\t-\t-\t-\t-"
            )
            continue
        budget = scenario["budget"]
        lines.append(
            f"{scenario['mde']:.3f}\t{scenario['assumed_predicate_prevalence']:.6f}\t"
            f"{scenario['required_raw_carry']}\t{budget['dialogues']}\t"
            f"{budget['deduplicated_total_calls']}\t"
            f"{budget['deduplicated_total_audio_seconds'] / 3600:.2f}\t"
            f"{budget['naive_four_arm_total_calls']}"
        )
    return "\n".join(lines) + "\n"


def build_result(jsonl: Path, discovery: Path, confirmatory: Path) -> tuple[dict[str, object], dict[str, object]]:
    source_hash = sha256(jsonl)
    if source_hash != EXPECTED_JSONL_SHA256:
        raise ValueError(f"JSONL hash mismatch: expected {EXPECTED_JSONL_SHA256}, got {source_hash}")
    discovery_ids = entry_ids(discovery)
    confirmatory_ids = entry_ids(confirmatory)
    overlap = discovery_ids & confirmatory_ids
    excluded = discovery_ids | confirmatory_ids
    if overlap or len(excluded) != EXPECTED_EXCLUSIONS:
        raise ValueError(
            f"exclusion gate failed: discovery={len(discovery_ids)}, confirmatory={len(confirmatory_ids)}, "
            f"overlap={len(overlap)}, union={len(excluded)}"
        )

    records = [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    remaining = [dialogue_stats(record) for record in records if str(record["uniq_id"]) not in excluded]
    carry_supply = sum(item.carry_mentions for item in remaining)
    scenarios: list[dict[str, object]] = []
    primary_roster: list[dict[str, object]] | None = None
    insufficient = False
    observed_prevalence = 418 / 774
    for mde in (0.03, 0.04, 0.05):
        for prevalence in (0.40, 0.50, observed_prevalence):
            try:
                scenario = build_scenario(
                    remaining,
                    mde=mde,
                    prevalence=prevalence,
                    usable_fraction=0.85,
                    discordance_rate=0.15,
                    design_effect=1.5,
                    seed=SEED,
                )
            except ValueError as exc:
                scenario = {
                    "mde": mde,
                    "assumed_predicate_prevalence": prevalence,
                    "feasible": False,
                    "reason": str(exc),
                }
                if mde == 0.03 and prevalence == 0.40:
                    insufficient = True
            else:
                roster = scenario.pop("roster")
                scenario["feasible"] = True
                scenario["roster_id_sha256"] = hashlib.sha256(
                    "\n".join(str(item["uniq_id"]) for item in roster).encode()
                ).hexdigest()
                if mde == 0.03 and prevalence == 0.40:
                    primary_roster = roster
            scenarios.append(scenario)

    decision = "INSUFFICIENT-CARRY-SUPPLY" if insufficient else "SCENARIO-POWER-READY-PREVALENCE-UNVERIFIED"
    result: dict[str, object] = {
        "schema_version": "e4-disjoint-power-v1",
        "experiment_id": "E4-DISJOINT-POWER-v1",
        "decision": decision,
        "source": {"jsonl": str(jsonl), "jsonl_sha256": source_hash},
        "exclusion": {
            "discovery_manifest": str(discovery),
            "confirmatory_roster": str(confirmatory),
            "count": len(excluded),
            "ids_sha256": hashlib.sha256("\n".join(sorted(excluded)).encode()).hexdigest(),
        },
        "identifiability": {
            "unseen_predicate_prevalence_measured": False,
            "reason": "speaker/wrong inventories require new Pass-0 model outputs",
            "e4_cf_descriptive_prevalence": observed_prevalence,
            "outcome_icc_measured": False,
            "design_effect_assumption": 1.5,
        },
        "assumptions": {
            "alpha_two_sided": 0.05,
            "power": 0.80,
            "discordance_rate": 0.15,
            "design_effect": 1.5,
            "usable_state_fraction": 0.85,
            "primary_mde": 0.03,
            "primary_prevalence": 0.40,
            "policy_arm_is_deterministic_alias": True,
        },
        "corpus": {
            "remaining_dialogues": len(remaining),
            "carry_mentions": carry_supply,
            "target_turns": sum(item.target_turns for item in remaining),
            "cluster_summary": cluster_summary(remaining),
        },
        "scenarios": scenarios,
    }
    roster_document = {
        "schema_version": "e4-disjoint-primary-candidate-roster-v1",
        "experiment_id": "E4-DISJOINT-POWER-v1",
        "status": "candidate-only; model contact not authorized",
        "seed": SEED,
        "source_jsonl_sha256": source_hash,
        "selection_assumptions": {"mde": 0.03, "predicate_prevalence": 0.40, "usable_state_fraction": 0.85},
        "entries": primary_roster or [],
    }
    return result, roster_document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", required=True)
    parser.add_argument("--discovery-manifest", required=True)
    parser.add_argument("--confirmatory-roster", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        parser.error("registered output directory exists; refusing overwrite")
    result, roster = build_result(
        Path(args.jsonl), Path(args.discovery_manifest), Path(args.confirmatory_roster)
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "verdict.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (output_dir / "report.txt").write_text(render_report(result), encoding="utf-8")
    (output_dir / "primary-candidate-roster.json").write_text(json.dumps(roster, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": result["decision"], "output_dir": str(output_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
