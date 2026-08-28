#!/usr/bin/env python3
"""Freeze the reference-blind LHCP full-pool semantic extraction supply."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from download_material_lhcp_development_audio import sha256_file  # noqa: E402
from read_material_lhcp_bm25_local_extractor import source_occurrence  # noqa: E402
from read_material_lhcp_full_pool_ceiling import candidate_id  # noqa: E402


def write_json_exclusive(path: Path, value: Any) -> None:
    payload = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def write_jsonl_exclusive(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def build_supply(
    config: dict[str, Any],
    trace_rows: list[dict[str, Any]],
    source_candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(trace_rows) != int(config["counts"]["queries"]):
        raise ValueError("trace query count drift")
    meeting_ids = {str(row["meeting_id"]) for row in trace_rows}
    if len(meeting_ids) != int(config["counts"]["meetings"]):
        raise ValueError("meeting count drift")
    selected: list[dict[str, Any]] = []
    for row in source_candidates:
        meeting_id = Path(str(row["audio_path"])).stem
        if meeting_id not in meeting_ids:
            continue
        occurrence = source_occurrence(row)
        canonical = str(row["canonical"])
        span = str(occurrence["source_span"])
        key_text = f"Official material candidate: {canonical}. Context: {span}"
        selected.append({
            "candidate_id": candidate_id(meeting_id, canonical),
            "meeting_id": meeting_id,
            "key_text": key_text,
            "value": {
                "canonical": canonical,
                "category": str(row["category"]),
                "source_page": int(occurrence["page"]),
                "source_relative_path": str(occurrence["relative_path"]),
                "source_span": span,
            },
        })
    selected.sort(key=lambda row: (str(row["meeting_id"]), str(row["candidate_id"])))
    if len(selected) != int(config["counts"]["keys"]):
        raise ValueError("candidate count drift")
    if len({str(row["candidate_id"]) for row in selected}) != len(selected):
        raise ValueError("candidate identity collision")

    instruction = str(config["construction"]["query_instruction"])
    queries: list[dict[str, Any]] = []
    for position, row in enumerate(trace_rows):
        prior = [str(value) for value in row["runtime_context"]["prior_topic_keywords"]]
        if len(prior) > int(config["construction"]["maximum_prior_keywords"]):
            raise ValueError(f"prior keyword overflow: {row['turn_id']}")
        speaker_labels = [str(value) for value in row["runtime_context"]["speaker_labels"]]
        query_text = (
            f"{instruction}Predicted speaker labels: {', '.join(speaker_labels) if speaker_labels else 'none'}\n"
            f"Prior topic keywords: {', '.join(prior) if prior else 'none'}\n"
            f"Transcript: {row['pass0']['transcript_text']}"
        )
        queries.append({
            "position": position,
            "meeting_id": str(row["meeting_id"]),
            "turn_id": str(row["turn_id"]),
            "speaker_labels": speaker_labels,
            "prior_topic_keywords": prior,
            "potentially_truncated": bool(row["runtime_context"]["potentially_truncated"]),
            "query_text": query_text,
        })
    return selected, queries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--semantic-root", required=True, type=Path)
    parser.add_argument("--supply-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output_root.exists():
        parser.error(f"output root exists: {args.output_root}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    bindings = {
        "preregistration_sha256": ROOT / str(config["inputs"]["preregistration_path"]),
        "semantic_trace_sha256": args.semantic_root / "trace.jsonl",
        "semantic_receipt_sha256": args.semantic_root / "receipt.json",
        "supply_receipt_sha256": args.supply_root / "receipt.json",
        "candidate_pool_sha256": args.supply_root / "candidate-pool.json",
        "builder_sha256": Path(__file__).resolve(),
    }
    for field, path in bindings.items():
        if sha256_file(path) != config["inputs"][field]:
            raise ValueError(f"{field} mismatch")
    source = json.loads((args.supply_root / "candidate-pool.json").read_text(encoding="utf-8"))
    if source.get("reference_reads") != 0:
        raise ValueError("candidate source reference firewall failed")
    trace_rows = [json.loads(line) for line in (args.semantic_root / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    candidates, queries = build_supply(config, trace_rows, list(source["candidates"]))
    args.output_root.mkdir(parents=True)
    candidates_path = args.output_root / "candidates.json"
    queries_path = args.output_root / "queries.jsonl"
    write_json_exclusive(candidates_path, {
        "schema": "material-lhcp-full-pool-semantic-candidates-v1",
        "reference_reads": 0,
        "candidates": candidates,
    })
    write_jsonl_exclusive(queries_path, queries)
    receipt = {
        "schema": "material-lhcp-full-pool-semantic-supply-receipt-v1",
        "experiment_id": config["experiment_id"],
        "meetings": len({str(row["meeting_id"]) for row in queries}),
        "keys": len(candidates),
        "queries": len(queries),
        "reference_reads": 0,
        "confirmation_access": 0,
        "embedding_calls": 0,
        "omni_calls": 0,
        "artifacts": {
            name: {"sha256": sha256_file(args.output_root / name), "bytes": (args.output_root / name).stat().st_size}
            for name in ("candidates.json", "queries.jsonl")
        },
        "verdict": "LHCP_FULL_POOL_SEMANTIC_SUPPLY_FROZEN",
    }
    write_json_exclusive(args.output_root / "receipt.json", receipt)
    print(json.dumps({"verdict": receipt["verdict"], "keys": len(candidates), "queries": len(queries)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
