#!/usr/bin/env python3
"""Build the frozen zero-model roster for E4-DISJOINT-PREV."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.probes.e4_power import budget_summary, dialogue_stats, stable_order  # noqa: E402

EXPECTED_JSONL_SHA256 = "4bbf64387d1c581df2c7ab5db9af4461e1112ee489377b67084c9b40cb6d45e8"
SEED = "e4-disjoint-prev-2026-08-21-v1"
STAGES = (20, 40, 60)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ids(path: Path) -> set[str]:
    return {str(item["uniq_id"]) for item in json.loads(path.read_text(encoding="utf-8"))["entries"]}


def build_roster(jsonl: Path, discovery: Path, confirmatory: Path) -> dict[str, object]:
    source_hash = _sha(jsonl)
    if source_hash != EXPECTED_JSONL_SHA256:
        raise ValueError(f"JSONL hash mismatch: {source_hash}")
    left, right = _ids(discovery), _ids(confirmatory)
    if left & right or len(left | right) != 299:
        raise ValueError("expected exactly 299 non-overlapping excluded dialogues")
    excluded = left | right
    records = (json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip())
    stats = [dialogue_stats(record) for record in records if str(record["uniq_id"]) not in excluded]
    eligible = stable_order([item for item in stats if item.carry_mentions >= 2], SEED)
    if len(eligible) < STAGES[-1]:
        raise ValueError(f"need {STAGES[-1]} eligible dialogues, found {len(eligible)}")
    selected = eligible[: STAGES[-1]]
    stages = []
    for size in STAGES:
        prefix = selected[:size]
        stages.append({"dialogues": size, **budget_summary(prefix, second_pass_arms=0)})
    return {
        "schema_version": "e4-disjoint-prevalence-roster-v1",
        "experiment_id": "E4-DISJOINT-PREV-v1",
        "status": "candidate roster; no model contact authorized",
        "source_jsonl_sha256": source_hash,
        "seed": SEED,
        "excluded_dialogues": len(excluded),
        "selection_rule": "sha256(seed:uniq_id), carry_mentions >= 2, first 60; cumulative stages 20/40/60",
        "stages": stages,
        "entries": [item.__dict__ for item in selected],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", required=True)
    parser.add_argument("--discovery-manifest", required=True)
    parser.add_argument("--confirmatory-roster", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        parser.error("output exists; refusing overwrite")
    document = build_roster(Path(args.jsonl), Path(args.discovery_manifest), Path(args.confirmatory_roster))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stages": document["stages"], "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
