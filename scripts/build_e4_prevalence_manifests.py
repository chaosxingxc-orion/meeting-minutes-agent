#!/usr/bin/env python3
"""Materialize leakage-separated manifests for E4-DISJOINT-PREV."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402


def _tar_index(directory: Path, wanted: set[str]) -> dict[str, tuple[Path, str]]:
    found: dict[str, tuple[Path, str]] = {}
    for path in sorted(directory.glob("*.tar")):
        with tarfile.open(path, "r") as archive:
            for member in archive.getmembers():
                stem = Path(member.name).stem
                if member.isfile() and stem in wanted:
                    found[stem] = (path, member.name)
        if len(found) == len(wanted):
            break
    return found


def _hash_members(members: dict[str, tuple[Path, str]]) -> dict[str, str]:
    grouped: dict[Path, list[tuple[str, str]]] = {}
    for uniq_id, (path, member) in members.items():
        grouped.setdefault(path, []).append((uniq_id, member))
    hashes: dict[str, str] = {}
    for path, items in grouped.items():
        with tarfile.open(path, "r") as archive:
            for uniq_id, member in items:
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError(f"unreadable member: {path}/{member}")
                digest = hashlib.sha256()
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                hashes[uniq_id] = digest.hexdigest()
    return hashes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", required=True)
    parser.add_argument("--roster", required=True)
    parser.add_argument("--tar-dir", required=True)
    parser.add_argument("--runtime-out", required=True)
    parser.add_argument("--score-out", required=True)
    args = parser.parse_args(argv)
    outputs = [Path(args.runtime_out), Path(args.score_out)]
    if any(path.exists() for path in outputs):
        parser.error("output exists; refusing overwrite")
    roster_path = Path(args.roster)
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    ids = [str(item["uniq_id"]) for item in roster["entries"]]
    if len(ids) != 60 or len(set(ids)) != 60:
        raise ValueError("roster must contain exactly 60 unique dialogues")
    wanted = set(ids)
    records: dict[str, dict[str, object]] = {}
    for line in Path(args.jsonl).read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if str(record["uniq_id"]) in wanted:
            records[str(record["uniq_id"])] = record
    if set(records) != wanted:
        raise ValueError(f"missing JSON records: {sorted(wanted - set(records))[:5]}")
    members = _tar_index(Path(args.tar_dir), wanted)
    if set(members) != wanted:
        raise ValueError(f"missing audio members: {sorted(wanted - set(members))[:5]}")
    audio_hashes = _hash_members(members)
    runtime_entries, score_entries = [], []
    for position, uniq_id in enumerate(ids):
        record = records[uniq_id]
        roles = {role: f"speaker_{index + 1}" for index, role in enumerate(dict.fromkeys(x["role"] for x in record["dialogue"]))}
        runtime_turns = [
            {"index": index, "speaker_id": roles[str(turn["role"])], "start": float(turn["start"]), "end": float(turn["end"])}
            for index, turn in enumerate(record["dialogue"])
        ]
        score_turns = [
            {"index": index, "speaker_id": roles[str(turn["role"])], "reference_text": str(turn["text"])}
            for index, turn in enumerate(record["dialogue"])
        ]
        tar_path, member = members[uniq_id]
        stage = 20 if position < 20 else 40 if position < 40 else 60
        runtime_entries.append({
            "uniq_id": uniq_id, "stage": stage, "duration": float(record["duration"]), "turns": runtime_turns,
            "source_tar": str(tar_path), "tar_member": member, "audio_sha256": audio_hashes[uniq_id],
        })
        score_entries.append({"uniq_id": uniq_id, "stage": stage, "entity_list": [str(x) for x in record["entity_list"]], "turns": score_turns})
    common = {
        "experiment_id": "E4-DISJOINT-PREV-v1",
        "roster": str(roster_path),
        "roster_sha256": hashlib.sha256(roster_path.read_bytes()).hexdigest(),
        "stage_boundaries": [20, 40, 60],
    }
    runtime = {"schema_version": "e4-cf-pass0-runtime-v1", **common, "entries": runtime_entries}
    score = {"schema_version": "e4-cf-pass0-score-v1", **common, "entries": score_entries}
    runtime["content_hash"] = config_hash(runtime)
    score["content_hash"] = config_hash(score)
    outputs[0].parent.mkdir(parents=True, exist_ok=True)
    outputs[0].write_text(json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    outputs[1].write_text(json.dumps(score, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"runtime_hash": runtime["content_hash"], "score_hash": score["content_hash"], "dialogues": len(ids)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
