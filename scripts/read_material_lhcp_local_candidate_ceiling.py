#!/usr/bin/env python3
"""Read the post-reference LHCP development local-candidate oracle ceiling."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from download_material_lhcp_development_audio import sha256_file  # noqa: E402
from read_material_lhcp_development_opportunity_power import (  # noqa: E402
    contains_phrase,
    reference_span,
    tokens,
)
from difflib import SequenceMatcher  # noqa: E402


def classify_candidate(
    pass0_slice_tokens: list[str],
    reference_window_tokens: list[str],
    canonical_tokens: list[str],
) -> str:
    reference_support = contains_phrase(reference_window_tokens, canonical_tokens)
    pass0_support = contains_phrase(pass0_slice_tokens, canonical_tokens)
    if reference_support and pass0_support:
        return "retain"
    if reference_support:
        return "wrong_to_correct_opportunity"
    return "unsupported"


def ceiling_verdict(
    opportunity_slices: int,
    opportunity_meetings: int,
    gates: dict[str, Any],
) -> str:
    if (
        opportunity_slices >= int(gates["minimum_primary_opportunity_slices"])
        and opportunity_meetings >= int(gates["minimum_primary_opportunity_meetings"])
    ):
        return "LHCP_LOCAL_CANDIDATE_POOL_POWER_READY"
    if (
        opportunity_slices >= int(gates["exploratory_minimum_opportunity_slices"])
        and opportunity_meetings >= int(gates["exploratory_minimum_opportunity_meetings"])
    ):
        return "LHCP_LOCAL_CANDIDATE_POOL_EXPLORATORY_ONLY"
    return "LHCP_LOCAL_CANDIDATE_POOL_INSUFFICIENT"


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
    references: list[dict[str, Any]],
    trace_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    refs = {str(row["meeting_id"]): row for row in references}
    trace_by_meeting: dict[str, list[dict[str, Any]]] = {}
    trace_positions: dict[str, int] = {}
    for position, row in enumerate(trace_rows):
        turn_id = str(row["turn_id"])
        if turn_id in trace_positions:
            raise ValueError(f"duplicate trace turn_id: {turn_id}")
        trace_positions[turn_id] = position
        trace_by_meeting.setdefault(str(row["meeting_id"]), []).append(row)
    if len(refs) != 25 or len(trace_rows) != 396 or set(refs) != set(trace_by_meeting):
        raise ValueError("reference or trace identity closure failed")

    padding = int(config["construction"]["reference_window_padding_tokens"])
    width = int(config["construction"]["candidate_width_per_slice"])
    rows_out: list[dict[str, Any]] = []
    meetings_out: list[dict[str, Any]] = []
    candidate_pair_counts: Counter[str] = Counter()
    unique_opportunity_candidates: set[str] = set()

    for meeting_id in sorted(refs):
        meeting_rows = sorted(
            trace_by_meeting[meeting_id],
            key=lambda row: int(str(row["turn_id"]).rsplit("slice", 1)[1]),
        )
        reference_tokens = tokens(str(refs[meeting_id]["transcription"]))
        if not reference_tokens:
            raise ValueError(f"empty normalized reference: {meeting_id}")
        hypothesis_tokens: list[str] = []
        intervals: list[tuple[int, int]] = []
        for row in meeting_rows:
            start = len(hypothesis_tokens)
            hypothesis_tokens.extend(tokens(str(row["pass0"]["transcript_text"])))
            intervals.append((start, len(hypothesis_tokens)))
        opcodes = SequenceMatcher(None, hypothesis_tokens, reference_tokens, autojunk=True).get_opcodes()

        meeting_slice_counts: Counter[str] = Counter()
        meeting_unique_opportunities: set[str] = set()
        for row, (hyp_start, hyp_end) in zip(meeting_rows, intervals, strict=True):
            candidates = list(row["retrieval"]["candidates"])
            if len(candidates) != width:
                raise ValueError(f"candidate width drift: {row['turn_id']}")
            candidate_ids = [str(candidate["candidate_id"]) for candidate in candidates]
            if len(set(candidate_ids)) != width:
                raise ValueError(f"duplicate candidates: {row['turn_id']}")
            if any(str(candidate["meeting_id"]) != meeting_id for candidate in candidates):
                raise ValueError(f"wrong-meeting candidate in correct inventory: {row['turn_id']}")
            if str(row["decision"]["top1_candidate_id"]) != candidate_ids[0]:
                raise ValueError(f"top1/rank-one mismatch: {row['turn_id']}")

            ref_start, ref_end = reference_span(
                opcodes,
                hyp_start,
                hyp_end,
                len(hypothesis_tokens),
                len(reference_tokens),
                padding,
            )
            reference_window = reference_tokens[ref_start:ref_end]
            pass0_slice = tokens(str(row["pass0"]["transcript_text"]))
            candidate_results: list[dict[str, Any]] = []
            for expected_rank, candidate in enumerate(candidates, 1):
                rank = int(candidate["rank"])
                if rank != expected_rank:
                    raise ValueError(f"candidate rank drift: {row['turn_id']}")
                phrase = tokens(str(candidate["value"]["canonical"]))
                if not phrase:
                    raise ValueError(f"empty canonical: {candidate['candidate_id']}")
                classification = classify_candidate(pass0_slice, reference_window, phrase)
                candidate_pair_counts[classification] += 1
                if classification == "wrong_to_correct_opportunity":
                    unique_opportunity_candidates.add(str(candidate["candidate_id"]))
                    meeting_unique_opportunities.add(str(candidate["candidate_id"]))
                candidate_results.append({
                    "candidate_id": candidate["candidate_id"],
                    "rank": rank,
                    "score": candidate["score"],
                    "canonical": candidate["value"]["canonical"],
                    "canonical_tokens": phrase,
                    "classification": classification,
                })

            opportunity_ranks = [
                int(candidate["rank"])
                for candidate in candidate_results
                if candidate["classification"] == "wrong_to_correct_opportunity"
            ]
            retain_ranks = [
                int(candidate["rank"])
                for candidate in candidate_results
                if candidate["classification"] == "retain"
            ]
            any_opportunity = bool(opportunity_ranks)
            any_supported = bool(opportunity_ranks or retain_ranks)
            top1_opportunity = 1 in opportunity_ranks
            meeting_slice_counts["opportunity_slices"] += int(any_opportunity)
            meeting_slice_counts["supported_slices"] += int(any_supported)
            meeting_slice_counts["top1_opportunity_slices"] += int(top1_opportunity)
            rows_out.append({
                "schema": "material-lhcp-local-candidate-ceiling-row-v1",
                "position": trace_positions[str(row["turn_id"])],
                "meeting_id": meeting_id,
                "turn_id": row["turn_id"],
                "speaker_labels": row["runtime_context"]["speaker_labels"],
                "potentially_truncated": bool(row["runtime_context"]["potentially_truncated"]),
                "reference_token_span": [ref_start, ref_end],
                "candidate_results": candidate_results,
                "opportunity_candidates": len(opportunity_ranks),
                "opportunity_ranks": opportunity_ranks,
                "best_opportunity_rank": min(opportunity_ranks) if opportunity_ranks else None,
                "any_opportunity": any_opportunity,
                "any_local_support": any_supported,
                "top1_opportunity": top1_opportunity,
            })
        meetings_out.append({
            "meeting_id": meeting_id,
            "slices": len(meeting_rows),
            "opportunity_slices": meeting_slice_counts["opportunity_slices"],
            "supported_slices": meeting_slice_counts["supported_slices"],
            "top1_opportunity_slices": meeting_slice_counts["top1_opportunity_slices"],
            "unique_opportunity_candidates": len(meeting_unique_opportunities),
        })

    rows_out.sort(key=lambda row: int(row["position"]))
    opportunity_rows = [row for row in rows_out if row["any_opportunity"]]
    supported_rows = [row for row in rows_out if row["any_local_support"]]
    top1_opportunity_rows = [row for row in rows_out if row["top1_opportunity"]]
    opportunity_meetings = len({str(row["meeting_id"]) for row in opportunity_rows})
    verdict = ceiling_verdict(len(opportunity_rows), opportunity_meetings, config["gates"])
    expected_top1 = int(config["reconciliation"]["expected_top1_opportunities"])
    if len(top1_opportunity_rows) != expected_top1:
        raise ValueError("top1 opportunity reconciliation failed")
    rank_counts = Counter(
        int(rank)
        for row in opportunity_rows
        for rank in row["opportunity_ranks"]
    )
    result = {
        "schema": "material-lhcp-local-candidate-ceiling-read-v1",
        "experiment_id": config["experiment_id"],
        "evidence_status": "POST_REFERENCE_DEVELOPMENT_DESCRIPTIVE",
        "reference_access": {
            "local_development_reference_reuses": 25,
            "new_source_reference_acquisitions": 0,
            "confirmation_meetings": 0,
        },
        "model_contact": {"embedding_calls": 0, "omni_calls": 0},
        "candidate_pairs": {
            "rows": len(rows_out) * width,
            "retain": candidate_pair_counts["retain"],
            "wrong_to_correct_opportunities": candidate_pair_counts["wrong_to_correct_opportunity"],
            "unsupported": candidate_pair_counts["unsupported"],
            "unique_opportunity_candidates": len(unique_opportunity_candidates),
        },
        "slice_ceiling": {
            "slices": len(rows_out),
            "opportunity_slices": len(opportunity_rows),
            "opportunity_coverage": len(opportunity_rows) / len(rows_out),
            "opportunity_meetings": opportunity_meetings,
            "locally_supported_slices": len(supported_rows),
            "local_support_coverage": len(supported_rows) / len(rows_out),
            "semantic_top1_opportunity_slices": len(top1_opportunity_rows),
            "semantic_top1_opportunity_capture": (
                len(top1_opportunity_rows) / len(opportunity_rows) if opportunity_rows else 0.0
            ),
            "best_opportunity_rank_distribution": dict(sorted(Counter(
                int(row["best_opportunity_rank"]) for row in opportunity_rows
            ).items())),
            "all_opportunity_rank_distribution": dict(sorted(rank_counts.items())),
        },
        "gates": {
            "primary_opportunity_slices": len(opportunity_rows) >= int(config["gates"]["minimum_primary_opportunity_slices"]),
            "primary_opportunity_meetings": opportunity_meetings >= int(config["gates"]["minimum_primary_opportunity_meetings"]),
            "exploratory_opportunity_slices": len(opportunity_rows) >= int(config["gates"]["exploratory_minimum_opportunity_slices"]),
            "exploratory_opportunity_meetings": opportunity_meetings >= int(config["gates"]["exploratory_minimum_opportunity_meetings"]),
        },
        "reconciliation": {
            "expected_top1_opportunities": expected_top1,
            "observed_top1_opportunities": len(top1_opportunity_rows),
            "passed": True,
        },
        "verdict": verdict,
        "claim_boundary": "Oracle ceiling on an already reference-open development surface; not a runtime selector or generalization result.",
    }
    return result, rows_out, meetings_out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--reference-root", required=True, type=Path)
    parser.add_argument("--semantic-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output_root.exists() or args.out.exists():
        parser.error("output exists; refusing to overwrite")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    bindings = {
        "preregistration_sha256": ROOT / str(config["inputs"]["preregistration_path"]),
        "preceding_config_sha256": ROOT / str(config["inputs"]["preceding_config_path"]),
        "preceding_read_sha256": ROOT / str(config["inputs"]["preceding_read_path"]),
        "reference_receipt_sha256": args.reference_root / "receipt.json",
        "references_sha256": args.reference_root / "references.jsonl",
        "semantic_trace_sha256": args.semantic_root / "trace.jsonl",
        "semantic_receipt_sha256": args.semantic_root / "receipt.json",
        "alignment_helper_sha256": ROOT / str(config["inputs"]["alignment_helper_path"]),
        "reader_sha256": Path(__file__).resolve(),
    }
    for field, path in bindings.items():
        if sha256_file(path) != config["inputs"][field]:
            raise ValueError(f"{field} mismatch")
    reference_receipt = json.loads((args.reference_root / "receipt.json").read_text(encoding="utf-8"))
    if (
        reference_receipt.get("development_references") != 25
        or reference_receipt.get("confirmation_access") != 0
        or reference_receipt.get("test_split_access") != 0
        or reference_receipt.get("audio_body_reads") != 0
    ):
        raise ValueError("reference firewall prerequisite failed")
    references = [
        json.loads(line)
        for line in (args.reference_root / "references.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    trace_rows = [
        json.loads(line)
        for line in (args.semantic_root / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    result, rows, meetings = audit(config, references, trace_rows)
    args.output_root.mkdir(parents=True)
    rows_path = args.output_root / "rows.jsonl"
    meetings_path = args.output_root / "meeting-summaries.json"
    write_jsonl_exclusive(rows_path, rows)
    write_json_exclusive(meetings_path, {
        "schema": "material-lhcp-local-candidate-ceiling-meetings-v1",
        "meetings": meetings,
    })
    receipt = {
        "schema": "material-lhcp-local-candidate-ceiling-receipt-v1",
        "experiment_id": config["experiment_id"],
        "local_development_reference_reuses": 25,
        "new_source_reference_acquisitions": 0,
        "confirmation_access": 0,
        "embedding_calls": 0,
        "omni_calls": 0,
        "verdict": result["verdict"],
        "artifacts": {
            name: {
                "sha256": sha256_file(args.output_root / name),
                "bytes": (args.output_root / name).stat().st_size,
            }
            for name in ("rows.jsonl", "meeting-summaries.json")
        },
    }
    write_json_exclusive(args.output_root / "receipt.json", receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "verdict": result["verdict"],
        "candidate_pairs": result["candidate_pairs"],
        "slice_ceiling": result["slice_ceiling"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
