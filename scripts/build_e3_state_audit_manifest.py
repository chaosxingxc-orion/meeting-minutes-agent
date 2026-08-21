#!/usr/bin/env python3
"""Build or summarize the frozen E3 ContextASR-Dialogue state-audit surface."""

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

from meeting_minutes_agent.probes.state_audit import contains_entity  # noqa: E402
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_stats(record: dict[str, object]) -> dict[str, int]:
    turns = list(record["dialogue"])
    entities = [str(x) for x in record["entity_list"]]
    same = 0
    global_only = 0
    target_turns = 0
    for index, target in enumerate(turns):
        target_entities = [entity for entity in entities if contains_entity(str(target["text"]), entity)]
        same_here = 0
        global_here = 0
        for entity in target_entities:
            prior = turns[:index]
            if any(
                turn["role"] == target["role"] and contains_entity(str(turn["text"]), entity)
                for turn in prior
            ):
                same += 1
                same_here += 1
            elif any(contains_entity(str(turn["text"]), entity) for turn in prior):
                global_only += 1
                global_here += 1
        if same_here or global_here:
            target_turns += 1
    return {"same_speaker_targets": same, "global_only_targets": global_only, "target_turns": target_turns}


def _stable(seed: str, uniq_id: str) -> str:
    return hashlib.sha256(f"{seed}:{uniq_id}".encode()).hexdigest()


def _tar_index(tar_dir: Path) -> dict[str, tuple[Path, tarfile.TarInfo]]:
    index: dict[str, tuple[Path, tarfile.TarInfo]] = {}
    for path in sorted(tar_dir.glob("*.tar")):
        with tarfile.open(path, "r") as archive:
            for member in archive.getmembers():
                if member.isfile() and member.name.lower().endswith(".wav"):
                    index[Path(member.name).stem] = (path, member)
    return index


def build_manifest(jsonl: Path, tar_dir: Path, *, n: int, seed: str) -> dict[str, object]:
    records = [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    enriched = [(record, _record_stats(record)) for record in records]
    eligible = [pair for pair in enriched if pair[1]["same_speaker_targets"] >= 2]
    eligible.sort(key=lambda pair: _stable(seed, str(pair[0]["uniq_id"])))
    selected = eligible[:n]
    if len(selected) != n:
        raise ValueError(f"requested {n} dialogues, only {len(selected)} have >=2 same-speaker carry targets")
    tar_members = _tar_index(tar_dir)
    entries: list[dict[str, object]] = []
    for record, stats in selected:
        uniq_id = str(record["uniq_id"])
        if uniq_id not in tar_members:
            raise ValueError(f"audio missing from tar set: {uniq_id}")
        tar_path, member = tar_members[uniq_id]
        with tarfile.open(tar_path, "r") as archive:
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"unreadable tar member: {member.name}")
            audio_hash = hashlib.sha256(source.read()).hexdigest()
        speaker_ids = {role: f"speaker_{index + 1}" for index, role in enumerate(dict.fromkeys(x["role"] for x in record["dialogue"]))}
        turns = [
            {
                "index": index,
                "speaker_id": speaker_ids[str(turn["role"])],
                "start": float(turn["start"]),
                "end": float(turn["end"]),
                "reference_text": str(turn["text"]),
            }
            for index, turn in enumerate(record["dialogue"])
        ]
        entries.append(
            {
                "uniq_id": uniq_id,
                "duration": float(record["duration"]),
                "entity_list": [str(x) for x in record["entity_list"]],
                "turns": turns,
                "selection_stats": stats,
                "source_tar": str(tar_path),
                "tar_member": member.name,
                "audio_sha256": audio_hash,
            }
        )
    census = {
        "dialogues": len(records),
        "eligible_same_speaker_ge2": len(eligible),
        "same_speaker_targets": sum(stats["same_speaker_targets"] for _, stats in enriched),
        "global_only_targets": sum(stats["global_only_targets"] for _, stats in enriched),
    }
    document: dict[str, object] = {
        "schema_version": "e3-state-audit-manifest-v1",
        "experiment_id": "E3-LEGAL-STATE-12-dialogue-v1",
        "purpose": "legal Pass-0 hypothesis-only glossary precision, pollution, carry, and speaker routing audit",
        "selection": {"n": n, "seed": seed, "criterion": ">=2 gold-side same-speaker carry targets"},
        "source": {"jsonl": str(jsonl), "jsonl_sha256": _file_sha256(jsonl), "tar_dir": str(tar_dir)},
        "census": census,
        "entries": entries,
    }
    document["content_hash"] = config_hash(document)
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", required=True)
    parser.add_argument("--tar-dir", required=True)
    parser.add_argument("--out")
    parser.add_argument("--n", type=int, default=12)
    parser.add_argument("--seed", default="e3-state-audit-2026-08-20-v1")
    args = parser.parse_args(argv)
    document = build_manifest(Path(args.jsonl), Path(args.tar_dir), n=args.n, seed=args.seed)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": args.out, "content_hash": document["content_hash"], "census": document["census"], "selected": len(document["entries"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
