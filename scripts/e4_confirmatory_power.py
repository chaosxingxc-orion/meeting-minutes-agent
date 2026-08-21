#!/usr/bin/env python3
"""Run the registered zero-model E4 confirmatory power census."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.probes.e4_power import (  # noqa: E402
    budget_summary,
    dialogue_stats,
    required_paired_mentions,
    select_roster,
)
from meeting_minutes_agent.probes.state_audit import load_manifest  # noqa: E402


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_plan(jsonl: Path, exclusion_manifest: Path, *, seed: str) -> tuple[dict[str, object], dict[str, object]]:
    excluded = {entry.uniq_id for entry in load_manifest(exclusion_manifest).entries}
    records = [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    stats = [dialogue_stats(record) for record in records if str(record["uniq_id"]) not in excluded]
    assumptions = {
        "alpha_two_sided": 0.05,
        "power": 0.80,
        "primary_mde": 0.05,
        "paired_discordance_rate": 0.15,
        "dialogue_design_effect": 1.5,
        "usable_state_fraction": 0.85,
        "second_pass_arms": 4,
    }
    required = required_paired_mentions(
        mde=assumptions["primary_mde"],
        discordance_rate=assumptions["paired_discordance_rate"],
        design_effect=assumptions["dialogue_design_effect"],
    )
    roster = select_roster(stats, required_mentions=required, usable_fraction=assumptions["usable_state_fraction"], seed=seed)
    scenarios = []
    for mde in (0.05, 0.075, 0.10):
        mentions = required_paired_mentions(mde=mde, discordance_rate=0.15, design_effect=1.5)
        scenario_roster = select_roster(stats, required_mentions=mentions, usable_fraction=0.85, seed=seed)
        scenarios.append({"mde": mde, "required_usable_mentions": mentions, **budget_summary(scenario_roster, second_pass_arms=4)})
    result: dict[str, object] = {
        "schema_version": "e4-confirmatory-power-v1",
        "experiment_id": "E4-POWER-UNSEEN-v1",
        "source": {"jsonl": str(jsonl), "jsonl_sha256": _sha(jsonl)},
        "exclusion": {"manifest": str(exclusion_manifest), "dialogues": sorted(excluded)},
        "seed": seed,
        "corpus": {
            "unseen_dialogues": len(stats),
            "eligible_ge2": sum(x.carry_mentions >= 2 for x in stats),
            "carry_mentions": sum(x.carry_mentions for x in stats),
            "target_turns": sum(x.target_turns for x in stats),
        },
        "assumptions": assumptions,
        "required_usable_mentions": required,
        "selection_target_mentions_before_attrition": int(__import__("math").ceil(required / assumptions["usable_state_fraction"])),
        "recommended_budget": budget_summary(roster, second_pass_arms=4),
        "scenarios": scenarios,
        "decision": "CONFIRMATORY-FEASIBLE-BUT-LARGE",
    }
    roster_doc = {
        "schema_version": "e4-confirmatory-candidate-roster-v1",
        "experiment_id": "E4-CONFIRMATORY-CANDIDATES-v1",
        "seed": seed,
        "source_jsonl_sha256": result["source"]["jsonl_sha256"],
        "excluded_dialogues": sorted(excluded),
        "selection_rule": "sha256(seed:uniq_id) over unseen dialogues with >=2 same-speaker carry mentions; prefix until primary target mass",
        "entries": [item.__dict__ for item in roster],
    }
    return result, roster_doc


def render_report(result: dict[str, object]) -> str:
    budget = result["recommended_budget"]
    lines = [
        f"decision: {result['decision']}",
        f"unseen_dialogues: {result['corpus']['unseen_dialogues']}",
        f"eligible_ge2: {result['corpus']['eligible_ge2']}",
        f"required_usable_mentions: {result['required_usable_mentions']}",
        f"selection_target_before_attrition: {result['selection_target_mentions_before_attrition']}",
        "",
        "recommended_primary_budget:",
    ]
    lines.extend(f"  {key}: {value}" for key, value in budget.items())
    lines.extend(["", "mde\tdialogues\tcarry_mentions\ttotal_calls\ttotal_audio_hours"])
    for scenario in result["scenarios"]:
        lines.append(f"{scenario['mde']:.3f}\t{scenario['dialogues']}\t{scenario['carry_mentions']}\t{scenario['total_calls']}\t{scenario['total_audio_seconds']/3600:.2f}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", required=True); parser.add_argument("--exclude-manifest", required=True)
    parser.add_argument("--verdict-out", required=True); parser.add_argument("--report-out", required=True); parser.add_argument("--roster-out", required=True)
    parser.add_argument("--seed", default="e4-confirmatory-2026-08-20-v1"); args = parser.parse_args(argv)
    outputs = [Path(args.verdict_out), Path(args.report_out), Path(args.roster_out)]
    if any(path.exists() for path in outputs): parser.error("registered output exists; refusing overwrite")
    result, roster = build_plan(Path(args.jsonl), Path(args.exclude_manifest), seed=args.seed)
    outputs[0].parent.mkdir(parents=True, exist_ok=False); outputs[2].parent.mkdir(parents=True, exist_ok=True)
    outputs[0].write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    outputs[1].write_text(render_report(result), encoding="utf-8")
    outputs[2].write_text(json.dumps(roster, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": result["decision"], "budget": result["recommended_budget"], "roster": str(outputs[2])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
