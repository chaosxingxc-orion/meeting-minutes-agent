#!/usr/bin/env python3
"""Freeze reference-blind material keys and per-slice LHCP queries."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.state.material_retrieval import word_tokens  # noqa: E402
from meeting_minutes_agent.state.material_trace import (  # noqa: E402
    candidate_keyset_sha256,
    sha256_text,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def keywords(text: str, maximum: int) -> list[str]:
    counts = Counter(word_tokens(text))
    return [token for token, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:maximum]]


def derangement(meeting_ids: Iterable[str]) -> dict[str, str]:
    ordered = sorted(str(value) for value in meeting_ids)
    if len(ordered) < 2:
        raise ValueError("derangement requires at least two meetings")
    return {meeting_id: ordered[(index + 1) % len(ordered)] for index, meeting_id in enumerate(ordered)}


def _source_occurrence(candidate: dict[str, Any]) -> dict[str, Any]:
    occurrences = candidate.get("occurrences", [])
    if not occurrences:
        raise ValueError(f"candidate has no occurrence: {candidate.get('canonical')}")
    return min(
        occurrences,
        key=lambda row: (int(row["page"]), str(row["relative_path"]), str(row["source_span"])),
    )


def select_candidates(
    source_candidates: list[dict[str, Any]],
    development_ids: set[str],
    *,
    width: int,
    salt: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {meeting_id: [] for meeting_id in development_ids}
    for row in source_candidates:
        meeting_id = Path(str(row["audio_path"])).stem
        if meeting_id in grouped:
            grouped[meeting_id].append(row)
    selected: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    for meeting_id in sorted(grouped):
        rows = grouped[meeting_id]
        canonical_keys = [str(row["canonical"]).casefold() for row in rows]
        if len(canonical_keys) != len(set(canonical_keys)):
            raise ValueError(f"duplicate canonical candidate: {meeting_id}")
        ordered = sorted(
            rows,
            key=lambda row: (
                hashlib.sha256(
                    f"{salt}:{meeting_id}:{str(row['canonical']).casefold()}".encode("utf-8")
                ).hexdigest(),
                str(row["canonical"]).casefold(),
            ),
        )
        if len(ordered) < width:
            raise ValueError(f"meeting {meeting_id} has {len(ordered)} candidates; requires {width}")
        meeting_selected: list[dict[str, Any]] = []
        for selection_index, row in enumerate(ordered[:width], 1):
            occurrence = _source_occurrence(row)
            canonical = str(row["canonical"])
            source_span = str(occurrence["source_span"])
            key_text = f"Official material candidate: {canonical}. Context: {source_span}"
            prompt_text = f"Official material evidence: {canonical}. Source excerpt: {source_span}"
            meeting_selected.append({
                "selection_index": selection_index,
                "candidate_id": f"lhcp-{meeting_id}-{sha256_text(canonical.casefold())[:12]}",
                "meeting_id": meeting_id,
                "key_text": key_text,
                "key_sha256": sha256_text(key_text),
                "value": {
                    "canonical": canonical,
                    "category": str(row["category"]),
                    "source_page": int(occurrence["page"]),
                    "source_relative_path": str(occurrence["relative_path"]),
                    "source_span": source_span,
                    "prompt_text": prompt_text,
                    "prompt_sha256": sha256_text(prompt_text),
                },
            })
        selected.extend(meeting_selected)
        inventory.append({
            "meeting_id": meeting_id,
            "available_candidates": len(rows),
            "selected_candidates": len(meeting_selected),
            "keyset_sha256": candidate_keyset_sha256(meeting_selected),
        })
    return selected, inventory


def build_queries(
    pass0_rows: list[dict[str, Any]],
    mapping: dict[str, str],
    keysets: dict[str, str],
    *,
    maximum_keywords: int,
    instruction: str,
    length_limited_position: int,
) -> list[dict[str, Any]]:
    prior: dict[str, dict[str, Any]] = {}
    expected_slice: dict[str, int] = {}
    queries: list[dict[str, Any]] = []
    for expected_position, row in enumerate(pass0_rows):
        position = int(row["position"])
        meeting_id = str(row["meeting_id"])
        slice_index = int(row["slice_index"])
        if position != expected_position:
            raise ValueError(f"Pass0 position drift at {expected_position}")
        if meeting_id not in mapping:
            raise ValueError(f"Pass0 meeting outside development cohort: {meeting_id}")
        if slice_index != expected_slice.get(meeting_id, 0):
            raise ValueError(f"non-contiguous slice order: {meeting_id} slice {slice_index}")
        expected_slice[meeting_id] = slice_index + 1
        prior_row = prior.get(meeting_id)
        prior_text = str(prior_row["transcript_text"]) if prior_row else ""
        prior_keywords = keywords(prior_text, maximum_keywords) if prior_text else []
        speaker_labels = sorted(str(value) for value in row.get("speaker_labels", []))
        query_text = (
            f"{instruction}Predicted speaker labels: {', '.join(speaker_labels) if speaker_labels else 'none'}\n"
            f"Prior topic keywords: {', '.join(prior_keywords) if prior_keywords else 'none'}\n"
            f"Transcript: {row['transcript_text']}"
        )
        query_context = {
            "speaker_labels": speaker_labels,
            "prior_turn_id": str(prior_row["turn_id"]) if prior_row else None,
            "prior_transcript_sha256": str(prior_row["transcript_sha256"]) if prior_row else None,
            "prior_topic_keywords": prior_keywords,
        }
        control_id = mapping[meeting_id]
        queries.append({
            "schema": "material-lhcp-development-query-row-v1",
            "experiment_id": "E-MATERIAL-LHCP-DEVELOPMENT-QUERY-SUPPLY",
            "position": position,
            "meeting_id": meeting_id,
            "slice_index": slice_index,
            "turn_id": str(row["turn_id"]),
            "audio_sha256": str(row["audio_sha256"]),
            "transcript_text": str(row["transcript_text"]),
            "transcript_sha256": str(row["transcript_sha256"]),
            "potentially_truncated": position == length_limited_position,
            "runtime_context": query_context,
            "query_text": query_text,
            "query_sha256": sha256_text(query_text),
            "correct_material": {"meeting_id": meeting_id, "keyset_sha256": keysets[meeting_id]},
            "deranged_material": {"meeting_id": control_id, "keyset_sha256": keysets[control_id]},
        })
        prior[meeting_id] = row
    return queries


def build_supply(
    config: dict[str, Any],
    cohort: dict[str, Any],
    source_pool: dict[str, Any],
    pass0_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    development = [row for row in cohort["items"] if row["cohort_role"] == "development"]
    development_ids = {Path(str(row["audio_path"])).stem for row in development}
    expected_meetings = int(config["passing_gates"]["development_meetings"])
    if len(development) != expected_meetings or len(development_ids) != expected_meetings:
        raise ValueError("development cohort count or identity drift")
    if source_pool.get("reference_reads") != 0:
        raise ValueError("source material firewall failed")
    selected, inventory = select_candidates(
        list(source_pool["candidates"]),
        development_ids,
        width=int(config["construction"]["key_width"]),
        salt=str(config["construction"]["key_selection_salt"]),
    )
    mapping = derangement(development_ids)
    keysets = {str(row["meeting_id"]): str(row["keyset_sha256"]) for row in inventory}
    queries = build_queries(
        pass0_rows,
        mapping,
        keysets,
        maximum_keywords=int(config["construction"]["maximum_prior_keywords"]),
        instruction=str(config["construction"]["query_instruction"]),
        length_limited_position=int(config["construction"]["length_limited_position"]),
    )
    if len(queries) != int(config["passing_gates"]["queries"]):
        raise ValueError("query count drift")
    return selected, inventory, mapping, queries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--supply-root", required=True, type=Path)
    parser.add_argument("--pass0-root", required=True, type=Path)
    parser.add_argument("--pass0-read", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output_root.exists():
        parser.error(f"output root exists: {args.output_root}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    bindings = {
        "cohort_sha256": args.cohort,
        "supply_receipt_sha256": args.supply_root / "receipt.json",
        "candidate_pool_sha256": args.supply_root / "candidate-pool.json",
        "pass0_index_sha256": args.pass0_root / "index.jsonl",
        "pass0_receipt_sha256": args.pass0_root / "receipt.json",
        "pass0_structural_read_sha256": args.pass0_read,
        "builder_sha256": Path(__file__).resolve(),
        "reader_sha256": ROOT / str(config["inputs"]["reader_path"]),
    }
    for field, path in bindings.items():
        if sha256_file(path) != config["inputs"][field]:
            raise ValueError(f"{field} mismatch")
    structural_read = json.loads(args.pass0_read.read_text(encoding="utf-8"))
    if (
        structural_read.get("verdict") != "PASS0_TRACE_COMPLETE"
        or structural_read.get("reference_access") != "NONE"
        or structural_read.get("confirmation_access") != "NONE"
    ):
        raise ValueError("Pass0 structural prerequisite failed")
    cohort = json.loads(args.cohort.read_text(encoding="utf-8"))
    source_pool = json.loads((args.supply_root / "candidate-pool.json").read_text(encoding="utf-8"))
    pass0_rows = [json.loads(line) for line in (args.pass0_root / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    selected, inventory, mapping, queries = build_supply(config, cohort, source_pool, pass0_rows)

    args.output_root.mkdir(parents=True)
    selected_document = {
        "schema": "material-lhcp-development-selected-candidates-v1",
        "experiment_id": config["experiment_id"],
        "reference_reads": 0,
        "candidates": selected,
    }
    mapping_document = {
        "schema": "material-lhcp-development-derangement-v1",
        "policy": config["construction"]["deranged_control"],
        "mapping": mapping,
    }
    write_json_exclusive(args.output_root / "selected-candidates.json", selected_document)
    write_json_exclusive(args.output_root / "derangement.json", mapping_document)
    write_jsonl_exclusive(args.output_root / "queries.jsonl", queries)
    artifacts = {
        name: {"sha256": sha256_file(args.output_root / name), "bytes": (args.output_root / name).stat().st_size}
        for name in ("selected-candidates.json", "derangement.json", "queries.jsonl")
    }
    receipt = {
        "schema": "material-lhcp-development-query-supply-receipt-v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": sha256_file(args.config),
        "reference_reads": 0,
        "confirmation_access": 0,
        "embedding_calls": 0,
        "omni_calls": 0,
        "totals": {
            "meetings": len(inventory),
            "available_candidates": sum(int(row["available_candidates"]) for row in inventory),
            "selected_candidates": len(selected),
            "queries": len(queries),
            "queries_with_prior_context": sum(bool(row["runtime_context"]["prior_turn_id"]) for row in queries),
            "potentially_truncated_queries": sum(bool(row["potentially_truncated"]) for row in queries),
        },
        "meeting_inventory": inventory,
        "artifacts": artifacts,
        "verdict": "LHCP_DEVELOPMENT_QUERY_SUPPLY_FROZEN",
    }
    write_json_exclusive(args.output_root / "receipt.json", receipt)
    print(json.dumps({"verdict": receipt["verdict"], **receipt["totals"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
