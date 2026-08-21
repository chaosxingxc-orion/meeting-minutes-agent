#!/usr/bin/env python3
"""Read one completed E4-DISJOINT-PREV stage without model contact."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.glossary.arms import gated_arm  # noqa: E402
from meeting_minutes_agent.glossary.gate import GateConfig  # noqa: E402
from meeting_minutes_agent.probes.contextasr_scoring import normalize_english  # noqa: E402
from meeting_minutes_agent.probes.e4_confirmatory import load_pass0_runtime, load_pass0_score  # noqa: E402
from meeting_minutes_agent.probes.e4_prevalence import BREAK_EVEN, cluster_bootstrap_interval, screening_decision  # noqa: E402
from meeting_minutes_agent.probes.state_audit import contains_entity  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _terms(text: str) -> tuple[str, ...]:
    return tuple(
        entry.canonical_surface
        for entry in gated_arm(text, chunk_index=0, gate_config=GateConfig(min_evidence=1, inventory_cap=8)).entries
    )


def render_report(result: dict[str, object]) -> str:
    return "\n".join(
        [
            f"decision: {result['decision']}",
            f"stage_dialogues: {result['stage_dialogues']}",
            f"pass0_calls: {result['pass0']['calls']}",
            f"natural_carry_targets: {result['supply']['natural_carry_targets']}",
            f"usable_targets: {result['supply']['usable_targets']}",
            f"usable_carry_fraction: {result['supply']['usable_carry_fraction']:.6f}",
            f"predicate_positive_targets: {result['prevalence']['positive_targets']}",
            f"predicate_prevalence: {result['prevalence']['point']:.6f}",
            f"break_even_prevalence: {result['prevalence']['break_even']:.6f}",
            f"cluster_bootstrap_80: {result['prevalence']['cluster_bootstrap_80']}",
            f"cluster_bootstrap_90: {result['prevalence']['cluster_bootstrap_90']}",
        ]
    ) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-manifest", required=True)
    parser.add_argument("--score-manifest", required=True)
    parser.add_argument("--responses", action="append", required=True)
    parser.add_argument("--stage-dialogues", type=int, choices=(20, 40, 60), required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        parser.error("output directory exists; refusing overwrite")
    runtime = load_pass0_runtime(args.runtime_manifest)
    score = load_pass0_score(args.score_manifest)
    selected_runtime = runtime.entries[: args.stage_dialogues]
    selected_ids = {entry.uniq_id for entry in selected_runtime}
    score_by = {entry.uniq_id: entry for entry in score.entries if entry.uniq_id in selected_ids}
    records: dict[tuple[str, int], dict[str, object]] = {}
    response_paths = [Path(path) for path in args.responses]
    for path in response_paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record.get("outcome") != "ok" or str(record["uniq_id"]) not in selected_ids:
                continue
            key = (str(record["uniq_id"]), int(record["turn_index"]))
            if key in records:
                raise ValueError(f"duplicate response: {key}")
            records[key] = record
    expected = {(entry.uniq_id, turn.index) for entry in selected_runtime for turn in entry.turns}
    if set(records) != expected:
        raise ValueError(f"Pass-0 stage incomplete: missing={len(expected - set(records))}, extra={len(set(records) - expected)}")

    total_targets = total_carry = usable_targets = usable_carry = positive_targets = 0
    dialogue_counts: list[tuple[int, int]] = []
    for entry in selected_runtime:
        score_entry = score_by[entry.uniq_id]
        score_turns = {turn.index: turn for turn in score_entry.turns}
        hypotheses = {turn.index: str(records[(entry.uniq_id, turn.index)]["text"]) for turn in entry.turns}
        dialogue_positive = dialogue_usable = 0
        for turn in entry.turns[1:]:
            score_turn = score_turns[turn.index]
            carry = tuple(
                entity
                for entity in score_entry.entity_list
                if contains_entity(score_turn.reference_text, entity)
                and any(
                    prior.speaker_id == turn.speaker_id
                    and contains_entity(score_turns[prior.index].reference_text, entity)
                    for prior in entry.turns[: turn.index]
                )
            )
            if not carry:
                continue
            total_targets += 1
            total_carry += len(carry)
            prior = entry.turns[: turn.index]
            speaker = _terms(" ".join(hypotheses[item.index] for item in prior if item.speaker_id == turn.speaker_id))
            wrong = _terms(" ".join(hypotheses[item.index] for item in prior if item.speaker_id != turn.speaker_id))
            global_terms = _terms(" ".join(hypotheses[item.index] for item in prior))
            width = min(len(speaker), len(wrong), len(global_terms))
            if width < 1:
                continue
            usable_targets += 1
            usable_carry += len(carry)
            dialogue_usable += 1
            speaker_set = {normalize_english(term) for term in speaker[:width]}
            wrong_set = {normalize_english(term) for term in wrong[:width]}
            if not (speaker_set & wrong_set):
                positive_targets += 1
                dialogue_positive += 1
        if dialogue_usable:
            dialogue_counts.append((dialogue_positive, dialogue_usable))
    if not usable_targets or not total_carry:
        raise ValueError("stage produced no usable prevalence denominator")
    point = positive_targets / usable_targets
    usable_fraction = usable_carry / total_carry
    ci80 = cluster_bootstrap_interval(dialogue_counts, level=0.80, seed=20260821 + args.stage_dialogues)
    ci90 = cluster_bootstrap_interval(dialogue_counts, level=0.90, seed=20260821 + args.stage_dialogues)
    decision = screening_decision(
        stage_dialogues=args.stage_dialogues,
        prevalence=point,
        ci80_lower=ci80[0],
        ci90_upper=ci90[1],
        usable_fraction=usable_fraction,
    )
    result: dict[str, object] = {
        "schema_version": "e4-disjoint-prevalence-read-v1",
        "experiment_id": "E4-DISJOINT-PREV-v1",
        "stage_dialogues": args.stage_dialogues,
        "decision": decision,
        "inputs": {
            "runtime_manifest_hash": runtime.content_hash,
            "score_manifest_hash": score.content_hash,
            "response_sha256": {str(path): _sha(path) for path in response_paths},
        },
        "pass0": {"calls": len(expected), "dialogues": len(selected_runtime)},
        "supply": {
            "natural_carry_targets": total_targets,
            "natural_carry_mentions": total_carry,
            "usable_targets": usable_targets,
            "usable_carry_mentions": usable_carry,
            "usable_carry_fraction": usable_fraction,
            "dialogues_with_usable_targets": len(dialogue_counts),
        },
        "prevalence": {
            "positive_targets": positive_targets,
            "point": point,
            "break_even": BREAK_EVEN,
            "cluster_bootstrap_80": ci80,
            "cluster_bootstrap_90": ci90,
            "bootstrap_replicates": 20_000,
        },
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "verdict.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (output_dir / "report.txt").write_text(render_report(result), encoding="utf-8")
    print(json.dumps({"decision": decision, "prevalence": point, "ci80": ci80, "usable_fraction": usable_fraction}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
