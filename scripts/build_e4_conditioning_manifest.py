#!/usr/bin/env python3
"""Freeze E4 equal-length state arms from the completed E3 Pass-0 flight."""

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
from meeting_minutes_agent.probes.state_audit import carry_targets, load_manifest  # noqa: E402
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _terms(text: str) -> tuple[str, ...]:
    plan = gated_arm(text, chunk_index=0, gate_config=GateConfig(min_evidence=1, inventory_cap=8))
    return tuple(entry.canonical_surface for entry in plan.entries)


def _corrupt_token(token: str) -> str:
    if len(token) >= 4:
        chars = list(token)
        chars[1], chars[2] = chars[2], chars[1]
        return "".join(chars)
    return token + "x"


def _corrupt(term: str) -> str:
    return " ".join(_corrupt_token(token) for token in term.split())


def build(parent_manifest: Path, responses: Path) -> dict[str, object]:
    parent = load_manifest(parent_manifest)
    hypotheses: dict[str, dict[int, str]] = {}
    for line in responses.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("outcome") == "ok":
            hypotheses.setdefault(str(record["uniq_id"]), {})[int(record["turn_index"])] = str(record["text"])
    targets: list[dict[str, object]] = []
    for entry in parent.entries:
        dialogue_hypotheses = hypotheses[entry.uniq_id]
        for turn in entry.turns[1:]:
            carry = carry_targets(entry, turn.index, same_speaker=True)
            if not carry:
                continue
            prior = entry.turns[:turn.index]
            same_text = " ".join(dialogue_hypotheses[x.index] for x in prior if x.speaker_id == turn.speaker_id)
            global_text = " ".join(dialogue_hypotheses[x.index] for x in prior)
            wrong_text = " ".join(dialogue_hypotheses[x.index] for x in prior if x.speaker_id != turn.speaker_id)
            speaker_terms, global_terms, wrong_terms = _terms(same_text), _terms(global_text), _terms(wrong_text)
            width = min(len(speaker_terms), len(global_terms), len(wrong_terms))
            if width < 1:
                raise ValueError(f"registered E3 target cannot form equal state arms: {entry.uniq_id}/{turn.index}")
            speaker_terms = speaker_terms[:width]
            targets.append(
                {
                    "uniq_id": entry.uniq_id, "turn_index": turn.index, "speaker_id": turn.speaker_id,
                    "start": turn.start, "end": turn.end, "reference_text": turn.reference_text,
                    "carry_entities": list(carry), "pass0_text": dialogue_hypotheses[turn.index],
                    "state_width": width, "speaker_terms": list(speaker_terms),
                    "global_terms": list(global_terms[:width]), "wrong_terms": list(wrong_terms[:width]),
                    "corrupt_terms": [_corrupt(term) for term in speaker_terms],
                    "source_tar": entry.source_tar, "tar_member": entry.tar_member, "audio_sha256": entry.audio_sha256,
                }
            )
    document: dict[str, object] = {
        "schema_version": "e4-conditioning-manifest-v1", "experiment_id": "E4-CONDITIONING-36-v1",
        "purpose": "fixed complete second-pass speaker conditioning with equal-length semantic controls",
        "parent": {"manifest": str(parent_manifest), "manifest_hash": parent.content_hash,
                   "responses": str(responses), "responses_sha256": _sha(responses)},
        "selection": {"rule": "all frozen E3 targets with >=1 same-speaker gold-side carry entity; no error-based selection"},
        "arms": list(__import__("meeting_minutes_agent.probes.e4_conditioning", fromlist=["ARMS"]).ARMS),
        "targets": targets,
    }
    document["content_hash"] = config_hash(document)
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-manifest", required=True); parser.add_argument("--responses", required=True)
    parser.add_argument("--out", required=True); args = parser.parse_args(argv)
    document = build(Path(args.parent_manifest), Path(args.responses))
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "content_hash": document["content_hash"], "targets": len(document["targets"]), "calls": len(document["targets"]) * 6}))
    return 0


if __name__ == "__main__": raise SystemExit(main())
