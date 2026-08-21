#!/usr/bin/env python3
"""Build the frozen 32-sample English ContextASR capability manifest.

This command performs local, read-only source-data inspection and writes one
small JSON manifest.  It never contacts a model and never extracts audio to a
persistent directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
from collections import defaultdict
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_key(seed: str, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()


def _corrupt_token(token: str) -> str:
    if len(token) >= 4:
        chars = list(token)
        chars[1], chars[2] = chars[2], chars[1]
        return "".join(chars)
    return token + "x"


def _corrupt_entity(entity: str) -> str:
    return " ".join(_corrupt_token(token) for token in entity.split())


def _entity_cost(target: dict[str, object], candidate: dict[str, object]) -> tuple[int, int, str]:
    target_entities = [str(x) for x in target["entity_list"]]
    candidate_entities = [str(x) for x in candidate["entity_list"]]
    count_gap = abs(len(target_entities) - len(candidate_entities))
    token_gap = abs(
        sum(len(x.split()) for x in target_entities) - sum(len(x.split()) for x in candidate_entities)
    )
    return count_gap, token_gap, str(candidate["uniq_id"])


def _choose_derangement(target: dict[str, object], pool: list[dict[str, object]]) -> dict[str, object]:
    reference_lower = str(target["text"]).lower()
    candidates = [
        candidate
        for candidate in pool
        if candidate["uniq_id"] != target["uniq_id"]
        and candidate["domain_label"] == target["domain_label"]
        and not any(str(entity).lower() in reference_lower for entity in candidate["entity_list"])
    ]
    if not candidates:
        candidates = [
            candidate
            for candidate in pool
            if candidate["uniq_id"] != target["uniq_id"]
            and not any(str(entity).lower() in reference_lower for entity in candidate["entity_list"])
        ]
    if not candidates:
        raise ValueError(f"no legal derangement candidate for {target['uniq_id']}")
    return min(candidates, key=lambda candidate: _entity_cost(target, candidate))


def _round_robin_sample(records: list[dict[str, object]], *, n: int, seed: str) -> list[dict[str, object]]:
    by_domain: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        by_domain[str(record["domain_label"])].append(record)
    for domain, values in by_domain.items():
        values.sort(key=lambda value: _stable_key(seed, str(value["uniq_id"])))
    domains = sorted(by_domain, key=lambda domain: _stable_key(seed, domain))
    selected: list[dict[str, object]] = []
    offset = 0
    while len(selected) < n:
        progressed = False
        for domain in domains:
            values = by_domain[domain]
            if offset < len(values):
                selected.append(values[offset])
                progressed = True
                if len(selected) == n:
                    break
        if not progressed:
            break
        offset += 1
    if len(selected) != n:
        raise ValueError(f"requested {n} samples, but only {len(selected)} were eligible")
    return selected


def build_manifest(*, jsonl: Path, source_tar: Path, n_samples: int, seed: str) -> dict[str, object]:
    records = [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    record_by_id = {str(record["uniq_id"]): record for record in records}
    with tarfile.open(source_tar, "r") as archive:
        member_by_id = {
            Path(member.name).stem: member
            for member in archive.getmembers()
            if member.isfile() and member.name.lower().endswith(".wav")
        }
        eligible = [
            record_by_id[uniq_id]
            for uniq_id in sorted(member_by_id)
            if uniq_id in record_by_id
            and 0 < float(record_by_id[uniq_id]["duration"]) <= 120
            and record_by_id[uniq_id].get("entity_list")
        ]
        selected = _round_robin_sample(eligible, n=n_samples, seed=seed)
        entries: list[dict[str, object]] = []
        for record in selected:
            uniq_id = str(record["uniq_id"])
            member = member_by_id[uniq_id]
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError(f"tar member is not readable: {member.name}")
            audio_bytes = extracted.read()
            deranged = _choose_derangement(record, eligible)
            entities = [str(x) for x in record["entity_list"]]
            entries.append(
                {
                    "uniq_id": uniq_id,
                    "language": str(record["language"]),
                    "duration": float(record["duration"]),
                    "domain_label": str(record["domain_label"]),
                    "reference_text": str(record["text"]),
                    "entity_list": entities,
                    "deranged_from_id": str(deranged["uniq_id"]),
                    "deranged_entity_list": [str(x) for x in deranged["entity_list"]],
                    "corrupt_entity_list": [_corrupt_entity(entity) for entity in entities],
                    "source_tar": str(source_tar),
                    "tar_member": member.name,
                    "audio_sha256": hashlib.sha256(audio_bytes).hexdigest(),
                    "audio_bytes": len(audio_bytes),
                }
            )
    document: dict[str, object] = {
        "schema_version": "contextasr-smoke-manifest-v1",
        "experiment_id": "C-CTX-32-en-speech-v1",
        "purpose": "Tier-M1 frozen-core use of correct/domain/deranged/corrupt context hints",
        "selection": {
            "n_samples": n_samples,
            "seed": seed,
            "source_scope": source_tar.name,
            "algorithm": "domain round-robin; sha256(seed:id) within domain",
        },
        "source": {
            "dataset": "ContextASR-Bench",
            "jsonl": str(jsonl),
            "jsonl_sha256": _file_sha256(jsonl),
            "tar": str(source_tar),
            "tar_bytes": source_tar.stat().st_size,
        },
        "arms": ["C0-bare", "C1-domain", "C2-entity", "C3-deranged", "C4-corrupt"],
        "entries": entries,
    }
    document["content_hash"] = config_hash(document)
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", required=True)
    parser.add_argument("--source-tar", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--n-samples", type=int, default=32)
    parser.add_argument("--seed", default="cctx-2026-08-20-v1")
    args = parser.parse_args(argv)
    document = build_manifest(
        jsonl=Path(args.jsonl), source_tar=Path(args.source_tar), n_samples=args.n_samples, seed=args.seed
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "content_hash": document["content_hash"], "n": args.n_samples}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
