#!/usr/bin/env python3
"""Build frozen runtime/score bindings for E4-DISJOINT-DIR without model contact."""

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
from meeting_minutes_agent.probes.state_audit import contains_entity  # noqa: E402
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _terms(text: str) -> tuple[str, ...]:
    arm = gated_arm(text, chunk_index=0, gate_config=GateConfig(min_evidence=1, inventory_cap=8))
    return tuple(entry.canonical_surface for entry in arm.entries)


def _write(document: dict[str, object], path: Path) -> None:
    document["content_hash"] = config_hash(document)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-manifest", required=True)
    parser.add_argument("--score-manifest", required=True)
    parser.add_argument("--responses", action="append", required=True)
    parser.add_argument("--runtime-out", required=True)
    parser.add_argument("--score-out", required=True)
    args = parser.parse_args(argv)
    runtime_out = Path(args.runtime_out)
    score_out = Path(args.score_out)
    if runtime_out.exists() or score_out.exists():
        parser.error("binding output exists; refusing overwrite")

    runtime = load_pass0_runtime(args.runtime_manifest)
    score = load_pass0_score(args.score_manifest)
    score_by = {entry.uniq_id: entry for entry in score.entries}
    response_paths = [Path(path) for path in args.responses]
    records: dict[tuple[str, int], dict[str, object]] = {}
    for path in response_paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record.get("outcome") != "ok":
                continue
            key = (str(record["uniq_id"]), int(record["turn_index"]))
            if key in records:
                raise ValueError(f"duplicate Pass-0 response: {key}")
            records[key] = record
    expected = {(entry.uniq_id, turn.index) for entry in runtime.entries for turn in entry.turns}
    if set(records) != expected:
        raise ValueError(f"Pass-0 incomplete: missing={len(expected - set(records))}, extra={len(set(records) - expected)}")

    runtime_targets: list[dict[str, object]] = []
    score_targets: list[dict[str, object]] = []
    for dialogue in runtime.entries:
        score_dialogue = score_by[dialogue.uniq_id]
        score_turns = {turn.index: turn for turn in score_dialogue.turns}
        hypotheses = {turn.index: str(records[(dialogue.uniq_id, turn.index)]["text"]) for turn in dialogue.turns}
        for turn in dialogue.turns[1:]:
            score_turn = score_turns[turn.index]
            carry = tuple(
                entity
                for entity in score_dialogue.entity_list
                if contains_entity(score_turn.reference_text, entity)
                and any(
                    prior.speaker_id == turn.speaker_id
                    and contains_entity(score_turns[prior.index].reference_text, entity)
                    for prior in dialogue.turns[: turn.index]
                )
            )
            if not carry:
                continue
            prior = dialogue.turns[: turn.index]
            speaker = _terms(" ".join(hypotheses[item.index] for item in prior if item.speaker_id == turn.speaker_id))
            wrong = _terms(" ".join(hypotheses[item.index] for item in prior if item.speaker_id != turn.speaker_id))
            global_terms = _terms(" ".join(hypotheses[item.index] for item in prior))
            width = min(len(speaker), len(wrong), len(global_terms))
            if width < 1:
                continue
            speaker = speaker[:width]
            wrong = wrong[:width]
            global_terms = global_terms[:width]
            speaker_set = {normalize_english(term) for term in speaker}
            wrong_set = {normalize_english(term) for term in wrong}
            if speaker_set & wrong_set:
                continue
            target_id = f"{dialogue.uniq_id}-t{turn.index:03d}"
            runtime_targets.append(
                {
                    "target_id": target_id,
                    "uniq_id": dialogue.uniq_id,
                    "turn_index": turn.index,
                    "speaker_id": turn.speaker_id,
                    "start": turn.start,
                    "end": turn.end,
                    "global_terms": list(global_terms),
                    "speaker_terms": list(speaker),
                    "wrong_terms": list(wrong),
                    "source_tar": dialogue.source_tar,
                    "tar_member": dialogue.tar_member,
                    "audio_sha256": dialogue.audio_sha256,
                }
            )
            score_targets.append(
                {
                    "target_id": target_id,
                    "uniq_id": dialogue.uniq_id,
                    "reference_text": score_turn.reference_text,
                    "carry_entities": list(carry),
                }
            )
    provenance = {
        "pass0_runtime_content_hash": runtime.content_hash,
        "pass0_score_content_hash": score.content_hash,
        "pass0_response_sha256": {str(path): _sha(path) for path in response_paths},
        "selection": "natural-carry-and-runtime-speaker-wrong-disjoint-v1",
        "state_gate": {"min_evidence": 1, "inventory_cap": 8, "equal_width": True},
    }
    runtime_document: dict[str, object] = {
        "schema_version": "e4-disjoint-dir-runtime-binding-v1",
        "experiment_id": "E4-DISJOINT-DIR-v1",
        "provenance": provenance,
        "targets": runtime_targets,
    }
    score_document: dict[str, object] = {
        "schema_version": "e4-disjoint-dir-score-binding-v1",
        "experiment_id": "E4-DISJOINT-DIR-v1",
        "provenance": provenance,
        "targets": score_targets,
    }
    runtime_out.parent.mkdir(parents=True, exist_ok=True)
    score_out.parent.mkdir(parents=True, exist_ok=True)
    _write(runtime_document, runtime_out)
    _write(score_document, score_out)
    calls = 2 * len(runtime_targets)
    audio_seconds = 2 * sum(float(item["end"]) - float(item["start"]) for item in runtime_targets)
    print(json.dumps({"targets": len(runtime_targets), "calls": calls, "audio_seconds": audio_seconds}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
