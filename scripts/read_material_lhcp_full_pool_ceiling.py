#!/usr/bin/env python3
"""Read the post-reference LHCP full material-pool oracle ceiling."""

from __future__ import annotations

import argparse
from collections import Counter
from difflib import SequenceMatcher
import hashlib
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
from read_material_lhcp_local_candidate_ceiling import ceiling_verdict  # noqa: E402


def candidate_id(meeting_id: str, canonical: str) -> str:
    digest = hashlib.sha256(canonical.casefold().encode("utf-8")).hexdigest()[:12]
    return f"lhcp-{meeting_id}-{digest}"


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
    source_candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    refs = {str(row["meeting_id"]): row for row in references}
    trace_by_meeting: dict[str, list[dict[str, Any]]] = {}
    positions: dict[str, int] = {}
    for position, row in enumerate(trace_rows):
        turn_id = str(row["turn_id"])
        if turn_id in positions:
            raise ValueError(f"duplicate trace turn: {turn_id}")
        positions[turn_id] = position
        trace_by_meeting.setdefault(str(row["meeting_id"]), []).append(row)
    candidates_by_meeting: dict[str, list[dict[str, Any]]] = {meeting_id: [] for meeting_id in refs}
    for candidate in source_candidates:
        meeting_id = Path(str(candidate["audio_path"])).stem
        if meeting_id in candidates_by_meeting:
            candidates_by_meeting[meeting_id].append(candidate)
    if len(refs) != 25 or len(trace_rows) != 396 or set(refs) != set(trace_by_meeting):
        raise ValueError("reference or trace identity closure failed")
    expected_candidates = int(config["construction"]["development_candidates"])
    observed_candidates = sum(len(rows) for rows in candidates_by_meeting.values())
    if observed_candidates != expected_candidates:
        raise ValueError(f"development candidate count drift: {observed_candidates}")
    for meeting_id, rows in candidates_by_meeting.items():
        canonicals = [str(row["canonical"]).casefold() for row in rows]
        if len(canonicals) != len(set(canonicals)):
            raise ValueError(f"duplicate meeting canonical: {meeting_id}")

    padding = int(config["construction"]["reference_window_padding_tokens"])
    rows_out: list[dict[str, Any]] = []
    meetings_out: list[dict[str, Any]] = []
    candidate_pairs = 0
    supported_pairs = 0
    opportunity_pairs = 0
    unique_opportunity_candidates: set[str] = set()
    category_opportunities: Counter[str] = Counter()
    token_width_opportunities: Counter[int] = Counter()

    for meeting_id in sorted(refs):
        meeting_rows = sorted(
            trace_by_meeting[meeting_id],
            key=lambda row: int(str(row["turn_id"]).rsplit("slice", 1)[1]),
        )
        meeting_candidates = sorted(
            candidates_by_meeting[meeting_id],
            key=lambda row: (str(row["canonical"]).casefold(), str(row["canonical"])),
        )
        reference_tokens = tokens(str(refs[meeting_id]["transcription"]))
        hypothesis_tokens: list[str] = []
        intervals: list[tuple[int, int]] = []
        for row in meeting_rows:
            start = len(hypothesis_tokens)
            hypothesis_tokens.extend(tokens(str(row["pass0"]["transcript_text"])))
            intervals.append((start, len(hypothesis_tokens)))
        opcodes = SequenceMatcher(None, hypothesis_tokens, reference_tokens, autojunk=True).get_opcodes()
        meeting_opportunity_slices = 0
        meeting_supported_slices = 0
        meeting_unique: set[str] = set()

        for row, (hyp_start, hyp_end) in zip(meeting_rows, intervals, strict=True):
            ref_start, ref_end = reference_span(
                opcodes,
                hyp_start,
                hyp_end,
                len(hypothesis_tokens),
                len(reference_tokens),
                padding,
            )
            window = reference_tokens[ref_start:ref_end]
            pass0_slice = tokens(str(row["pass0"]["transcript_text"]))
            opportunities: list[dict[str, Any]] = []
            locally_supported = 0
            for candidate in meeting_candidates:
                phrase = tokens(str(candidate["canonical"]))
                if not phrase:
                    raise ValueError(f"empty canonical: {meeting_id}")
                candidate_pairs += 1
                reference_support = contains_phrase(window, phrase)
                if not reference_support:
                    continue
                locally_supported += 1
                supported_pairs += 1
                if contains_phrase(pass0_slice, phrase):
                    continue
                opportunity_pairs += 1
                cid = candidate_id(meeting_id, str(candidate["canonical"]))
                unique_opportunity_candidates.add(cid)
                meeting_unique.add(cid)
                category = str(candidate["category"])
                category_opportunities[category] += 1
                token_width_opportunities[len(phrase)] += 1
                opportunities.append({
                    "candidate_id": cid,
                    "canonical": candidate["canonical"],
                    "category": category,
                    "canonical_tokens": phrase,
                    "occurrences": len(candidate.get("occurrences", [])),
                })
            any_opportunity = bool(opportunities)
            any_supported = locally_supported > 0
            meeting_opportunity_slices += int(any_opportunity)
            meeting_supported_slices += int(any_supported)
            rows_out.append({
                "schema": "material-lhcp-full-pool-ceiling-row-v1",
                "position": positions[str(row["turn_id"])],
                "meeting_id": meeting_id,
                "turn_id": row["turn_id"],
                "speaker_labels": row["runtime_context"]["speaker_labels"],
                "potentially_truncated": bool(row["runtime_context"]["potentially_truncated"]),
                "meeting_candidates": len(meeting_candidates),
                "reference_token_span": [ref_start, ref_end],
                "locally_supported_candidates": locally_supported,
                "opportunity_candidates": len(opportunities),
                "any_local_support": any_supported,
                "any_opportunity": any_opportunity,
                "opportunities": opportunities,
            })
        meetings_out.append({
            "meeting_id": meeting_id,
            "candidates": len(meeting_candidates),
            "slices": len(meeting_rows),
            "supported_slices": meeting_supported_slices,
            "opportunity_slices": meeting_opportunity_slices,
            "unique_opportunity_candidates": len(meeting_unique),
        })

    rows_out.sort(key=lambda row: int(row["position"]))
    opportunity_rows = [row for row in rows_out if row["any_opportunity"]]
    supported_rows = [row for row in rows_out if row["any_local_support"]]
    opportunity_meetings = len({str(row["meeting_id"]) for row in opportunity_rows})
    verdict = ceiling_verdict(len(opportunity_rows), opportunity_meetings, config["gates"]).replace(
        "LOCAL_CANDIDATE_POOL", "FULL_MATERIAL_POOL"
    )
    if len(opportunity_rows) < int(config["reconciliation"]["minimum_eight_key_opportunity_slices"]):
        raise ValueError("full-pool opportunity ceiling fell below eight-key subset")
    result = {
        "schema": "material-lhcp-full-pool-ceiling-read-v1",
        "experiment_id": config["experiment_id"],
        "evidence_status": "POST_REFERENCE_DEVELOPMENT_DESCRIPTIVE",
        "reference_access": {
            "local_development_reference_reuses": 25,
            "new_source_reference_acquisitions": 0,
            "confirmation_meetings": 0,
        },
        "model_contact": {"embedding_calls": 0, "omni_calls": 0},
        "source_pool": {
            "development_candidates": observed_candidates,
            "candidate_pairs": candidate_pairs,
            "locally_supported_candidate_pairs": supported_pairs,
            "wrong_to_correct_candidate_pairs": opportunity_pairs,
            "unique_opportunity_candidates": len(unique_opportunity_candidates),
            "opportunity_categories": dict(sorted(category_opportunities.items())),
            "opportunity_token_widths": {str(key): value for key, value in sorted(token_width_opportunities.items())},
        },
        "slice_ceiling": {
            "slices": len(rows_out),
            "opportunity_slices": len(opportunity_rows),
            "opportunity_coverage": len(opportunity_rows) / len(rows_out),
            "opportunity_meetings": opportunity_meetings,
            "locally_supported_slices": len(supported_rows),
            "local_support_coverage": len(supported_rows) / len(rows_out),
        },
        "gates": {
            "primary_opportunity_slices": len(opportunity_rows) >= int(config["gates"]["minimum_primary_opportunity_slices"]),
            "primary_opportunity_meetings": opportunity_meetings >= int(config["gates"]["minimum_primary_opportunity_meetings"]),
            "exploratory_opportunity_slices": len(opportunity_rows) >= int(config["gates"]["exploratory_minimum_opportunity_slices"]),
            "exploratory_opportunity_meetings": opportunity_meetings >= int(config["gates"]["exploratory_minimum_opportunity_meetings"]),
        },
        "verdict": verdict,
        "claim_boundary": "Oracle source-coverage ceiling on reference-open development data; not a runtime selector, precision, or correction result.",
    }
    return result, rows_out, meetings_out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--reference-root", required=True, type=Path)
    parser.add_argument("--semantic-root", required=True, type=Path)
    parser.add_argument("--supply-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output_root.exists() or args.out.exists():
        parser.error("output exists; refusing to overwrite")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    bindings = {
        "preregistration_sha256": ROOT / str(config["inputs"]["preregistration_path"]),
        "preceding_read_sha256": ROOT / str(config["inputs"]["preceding_read_path"]),
        "reference_receipt_sha256": args.reference_root / "receipt.json",
        "references_sha256": args.reference_root / "references.jsonl",
        "semantic_trace_sha256": args.semantic_root / "trace.jsonl",
        "semantic_receipt_sha256": args.semantic_root / "receipt.json",
        "supply_receipt_sha256": args.supply_root / "receipt.json",
        "candidate_pool_sha256": args.supply_root / "candidate-pool.json",
        "alignment_helper_sha256": ROOT / str(config["inputs"]["alignment_helper_path"]),
        "verdict_helper_sha256": ROOT / str(config["inputs"]["verdict_helper_path"]),
        "reader_sha256": Path(__file__).resolve(),
    }
    for field, path in bindings.items():
        if sha256_file(path) != config["inputs"][field]:
            raise ValueError(f"{field} mismatch")
    reference_receipt = json.loads((args.reference_root / "receipt.json").read_text(encoding="utf-8"))
    source_pool = json.loads((args.supply_root / "candidate-pool.json").read_text(encoding="utf-8"))
    if (
        reference_receipt.get("confirmation_access") != 0
        or source_pool.get("reference_reads") != 0
    ):
        raise ValueError("reference firewall prerequisite failed")
    references = [json.loads(line) for line in (args.reference_root / "references.jsonl").read_text(encoding="utf-8").splitlines()]
    trace_rows = [json.loads(line) for line in (args.semantic_root / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    result, rows, meetings = audit(config, references, trace_rows, list(source_pool["candidates"]))
    args.output_root.mkdir(parents=True)
    write_jsonl_exclusive(args.output_root / "rows.jsonl", rows)
    write_json_exclusive(args.output_root / "meeting-summaries.json", {
        "schema": "material-lhcp-full-pool-ceiling-meetings-v1",
        "meetings": meetings,
    })
    receipt = {
        "schema": "material-lhcp-full-pool-ceiling-receipt-v1",
        "experiment_id": config["experiment_id"],
        "local_development_reference_reuses": 25,
        "new_source_reference_acquisitions": 0,
        "confirmation_access": 0,
        "embedding_calls": 0,
        "omni_calls": 0,
        "verdict": result["verdict"],
        "artifacts": {
            name: {"sha256": sha256_file(args.output_root / name), "bytes": (args.output_root / name).stat().st_size}
            for name in ("rows.jsonl", "meeting-summaries.json")
        },
    }
    write_json_exclusive(args.output_root / "receipt.json", receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "source_pool": result["source_pool"], "slice_ceiling": result["slice_ceiling"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
