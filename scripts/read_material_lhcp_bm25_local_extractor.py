#!/usr/bin/env python3
"""Build and score the reference-blind LHCP BM25 local candidate extractor."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from download_material_lhcp_development_audio import sha256_file  # noqa: E402
from read_material_lhcp_development_opportunity_power import tokens  # noqa: E402
from read_material_lhcp_full_pool_ceiling import candidate_id  # noqa: E402


def source_occurrence(candidate: dict[str, Any]) -> dict[str, Any]:
    occurrences = list(candidate.get("occurrences", []))
    if not occurrences:
        raise ValueError(f"candidate has no occurrence: {candidate.get('canonical')}")
    return min(occurrences, key=lambda row: (int(row["page"]), str(row["relative_path"]), str(row["source_span"])))


def candidate_document(candidate: dict[str, Any], canonical_weight: int) -> list[str]:
    canonical = tokens(str(candidate["canonical"]))
    span = tokens(str(source_occurrence(candidate)["source_span"]))
    if not canonical or not span:
        raise ValueError(f"empty candidate document: {candidate.get('canonical')}")
    return canonical * canonical_weight + span


def bm25_scores(
    documents: list[list[str]],
    query: list[str],
    *,
    k1: float,
    b: float,
) -> list[float]:
    if not documents:
        raise ValueError("BM25 requires documents")
    document_counts = [Counter(document) for document in documents]
    average_length = sum(len(document) for document in documents) / len(documents)
    document_frequency: Counter[str] = Counter()
    for document in documents:
        document_frequency.update(set(document))
    query_counts = Counter(query)
    scores: list[float] = []
    for document, counts in zip(documents, document_counts, strict=True):
        score = 0.0
        length_norm = k1 * (1 - b + b * len(document) / average_length)
        for term, query_frequency in query_counts.items():
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            df = document_frequency[term]
            inverse_document_frequency = math.log(1 + (len(documents) - df + 0.5) / (df + 0.5))
            score += query_frequency * inverse_document_frequency * frequency * (k1 + 1) / (frequency + length_norm)
        scores.append(score)
    return scores


def variant_verdict(hits: int, meetings: int, gates: dict[str, Any]) -> str:
    if hits >= int(gates["minimum_primary_opportunity_slices"]) and meetings >= int(gates["minimum_primary_opportunity_meetings"]):
        return "BM25_LOCAL_EXTRACTION_POWER_READY"
    if hits >= int(gates["exploratory_minimum_opportunity_slices"]) and meetings >= int(gates["exploratory_minimum_opportunity_meetings"]):
        return "BM25_LOCAL_EXTRACTION_EXPLORATORY_ONLY"
    return "BM25_LOCAL_EXTRACTION_INSUFFICIENT"


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


def audit(
    config: dict[str, Any],
    trace_rows: list[dict[str, Any]],
    source_candidates: list[dict[str, Any]],
    oracle_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    trace = {str(row["turn_id"]): row for row in trace_rows}
    oracle = {str(row["turn_id"]): row for row in oracle_rows}
    if len(trace) != 396 or len(oracle) != 396 or set(trace) != set(oracle):
        raise ValueError("trace/oracle identity closure failed")
    meeting_ids = {str(row["meeting_id"]) for row in trace_rows}
    candidates_by_meeting: dict[str, list[dict[str, Any]]] = {meeting_id: [] for meeting_id in meeting_ids}
    for candidate in source_candidates:
        meeting_id = Path(str(candidate["audio_path"])).stem
        if meeting_id in candidates_by_meeting:
            candidates_by_meeting[meeting_id].append(candidate)
    if sum(len(rows) for rows in candidates_by_meeting.values()) != int(config["construction"]["development_candidates"]):
        raise ValueError("development candidate count drift")

    canonical_weight = int(config["bm25"]["canonical_weight"])
    k1 = float(config["bm25"]["k1"])
    b = float(config["bm25"]["b"])
    widths = [int(value) for value in config["evaluation"]["widths"]]
    primary_width = int(config["evaluation"]["primary_width"])
    indices: dict[str, tuple[list[dict[str, Any]], list[list[str]]]] = {}
    for meeting_id, rows in candidates_by_meeting.items():
        ordered = sorted(rows, key=lambda row: candidate_id(meeting_id, str(row["canonical"])))
        indices[meeting_id] = (ordered, [candidate_document(row, canonical_weight) for row in ordered])

    outputs: list[dict[str, Any]] = []
    metrics: dict[str, dict[int, dict[str, Any]]] = {
        variant: {width: {"hits": 0, "meetings": set()} for width in widths}
        for variant in ("current_only", "current_plus_prior")
    }
    oracle_opportunity_slices = sum(bool(row["any_opportunity"]) for row in oracle_rows)
    if oracle_opportunity_slices != int(config["reconciliation"]["oracle_opportunity_slices"]):
        raise ValueError("oracle opportunity count drift")

    for position, trace_row in enumerate(trace_rows):
        turn_id = str(trace_row["turn_id"])
        if int(oracle[turn_id]["position"]) != position:
            raise ValueError(f"oracle position drift: {turn_id}")
        meeting_id = str(trace_row["meeting_id"])
        candidates, documents = indices[meeting_id]
        current = tokens(str(trace_row["pass0"]["transcript_text"]))
        prior = [str(value).casefold() for value in trace_row["runtime_context"]["prior_topic_keywords"]]
        queries = {
            "current_only": current,
            "current_plus_prior": current + prior,
        }
        opportunity_ids = {str(row["candidate_id"]) for row in oracle[turn_id]["opportunities"]}
        variant_outputs: dict[str, Any] = {}
        for variant, query in queries.items():
            scores = bm25_scores(documents, query, k1=k1, b=b)
            ranked = sorted(
                zip(candidates, scores, strict=True),
                key=lambda item: (-item[1], candidate_id(meeting_id, str(item[0]["canonical"]))),
            )
            top = [{
                "candidate_id": candidate_id(meeting_id, str(candidate["canonical"])),
                "canonical": candidate["canonical"],
                "score": score,
            } for candidate, score in ranked[:max(widths)]]
            width_hits: dict[str, bool] = {}
            for width in widths:
                hit = bool(opportunity_ids.intersection(str(row["candidate_id"]) for row in top[:width]))
                width_hits[str(width)] = hit
                metrics[variant][width]["hits"] += int(hit)
                if hit:
                    metrics[variant][width]["meetings"].add(meeting_id)
            variant_outputs[variant] = {"query_tokens": len(query), "top_candidates": top, "opportunity_hit": width_hits}
        outputs.append({
            "schema": "material-lhcp-bm25-local-extractor-row-v1",
            "position": position,
            "meeting_id": meeting_id,
            "turn_id": turn_id,
            "oracle_opportunity_candidates": len(opportunity_ids),
            "variants": variant_outputs,
        })

    variants: dict[str, Any] = {}
    for variant, width_metrics in metrics.items():
        table: list[dict[str, Any]] = []
        for width in widths:
            hits = int(width_metrics[width]["hits"])
            represented = len(width_metrics[width]["meetings"])
            table.append({
                "width": width,
                "opportunity_hit_slices": hits,
                "oracle_opportunity_recall": hits / oracle_opportunity_slices,
                "all_slice_coverage": hits / len(outputs),
                "opportunity_meetings": represented,
            })
        primary = next(row for row in table if row["width"] == primary_width)
        variants[variant] = {
            "width_table": table,
            "primary_width": primary_width,
            "primary_metrics": primary,
            "verdict": variant_verdict(primary["opportunity_hit_slices"], primary["opportunity_meetings"], config["gates"]),
        }
    verdict_order = {
        "BM25_LOCAL_EXTRACTION_INSUFFICIENT": 0,
        "BM25_LOCAL_EXTRACTION_EXPLORATORY_ONLY": 1,
        "BM25_LOCAL_EXTRACTION_POWER_READY": 2,
    }
    overall = max((row["verdict"] for row in variants.values()), key=verdict_order.__getitem__)
    result = {
        "schema": "material-lhcp-bm25-local-extractor-read-v1",
        "experiment_id": config["experiment_id"],
        "evidence_status": "POST_REFERENCE_DEVELOPMENT_DISCOVERY",
        "ranking_firewall": {"reference_fields_used": 0, "gold_fields_used": 0},
        "reference_access": {"new_reference_reads": 0, "confirmation_meetings": 0},
        "model_contact": {"embedding_calls": 0, "omni_calls": 0},
        "oracle_ceiling": {"opportunity_slices": oracle_opportunity_slices, "slices": len(outputs)},
        "variants": variants,
        "verdict": overall,
        "claim_boundary": "Post-reference development ranking discovery; not independent validation, runtime dispatch safety, or transcription gain.",
    }
    return result, outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--semantic-root", required=True, type=Path)
    parser.add_argument("--supply-root", required=True, type=Path)
    parser.add_argument("--oracle-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output_root.exists() or args.out.exists():
        parser.error("output exists; refusing to overwrite")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    bindings = {
        "preregistration_sha256": ROOT / str(config["inputs"]["preregistration_path"]),
        "semantic_trace_sha256": args.semantic_root / "trace.jsonl",
        "semantic_receipt_sha256": args.semantic_root / "receipt.json",
        "supply_receipt_sha256": args.supply_root / "receipt.json",
        "candidate_pool_sha256": args.supply_root / "candidate-pool.json",
        "oracle_receipt_sha256": args.oracle_root / "receipt.json",
        "oracle_rows_sha256": args.oracle_root / "rows.jsonl",
        "token_helper_sha256": ROOT / str(config["inputs"]["token_helper_path"]),
        "identity_helper_sha256": ROOT / str(config["inputs"]["identity_helper_path"]),
        "reader_sha256": Path(__file__).resolve(),
    }
    for field, path in bindings.items():
        if sha256_file(path) != config["inputs"][field]:
            raise ValueError(f"{field} mismatch")
    trace_rows = [json.loads(line) for line in (args.semantic_root / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    source_pool = json.loads((args.supply_root / "candidate-pool.json").read_text(encoding="utf-8"))
    oracle_rows = [json.loads(line) for line in (args.oracle_root / "rows.jsonl").read_text(encoding="utf-8").splitlines()]
    result, rows = audit(config, trace_rows, list(source_pool["candidates"]), oracle_rows)
    args.output_root.mkdir(parents=True)
    rows_path = args.output_root / "rankings.jsonl"
    write_jsonl_exclusive(rows_path, rows)
    receipt = {
        "schema": "material-lhcp-bm25-local-extractor-receipt-v1",
        "experiment_id": config["experiment_id"],
        "reference_fields_used_for_ranking": 0,
        "gold_fields_used_for_ranking": 0,
        "new_reference_reads": 0,
        "confirmation_access": 0,
        "embedding_calls": 0,
        "omni_calls": 0,
        "verdict": result["verdict"],
        "artifacts": {"rankings.jsonl": {"sha256": sha256_file(rows_path), "bytes": rows_path.stat().st_size}},
    }
    write_json_exclusive(args.output_root / "receipt.json", receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "variants": result["variants"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
