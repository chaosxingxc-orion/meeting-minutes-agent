#!/usr/bin/env python3
"""One-shot LHCP development reference opportunity and power reader."""

from __future__ import annotations

import argparse
from collections import Counter
from difflib import SequenceMatcher
import hashlib
import json
import math
import os
from pathlib import Path
import re
from statistics import NormalDist
import sys
from typing import Any, Iterable

import editdistance


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from download_material_lhcp_development_audio import sha256_file  # noqa: E402


TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.casefold())


def contains_phrase(sequence: list[str], phrase: list[str]) -> bool:
    if not phrase or len(phrase) > len(sequence):
        return False
    width = len(phrase)
    return any(sequence[index : index + width] == phrase for index in range(len(sequence) - width + 1))


def required_pairs(effect: float, discordant_fraction: float, alpha: float = 0.05, power: float = 0.8) -> int:
    normal = NormalDist()
    z_sum = normal.inv_cdf(1 - alpha / 2) + normal.inv_cdf(power)
    return math.ceil((z_sum**2) * discordant_fraction / (effect**2))


def reference_span(
    opcodes: list[tuple[str, int, int, int, int]],
    hypothesis_start: int,
    hypothesis_end: int,
    hypothesis_length: int,
    reference_length: int,
    padding: int,
) -> tuple[int, int]:
    positions: list[int] = []
    for _, i1, i2, j1, j2 in opcodes:
        overlaps = i2 > hypothesis_start and i1 < hypothesis_end
        boundary_insertion = i1 == i2 and hypothesis_start <= i1 <= hypothesis_end
        if overlaps or boundary_insertion:
            positions.extend((j1, j2))
    if not positions:
        ratio_start = hypothesis_start / max(hypothesis_length, 1)
        center = round(ratio_start * reference_length)
        positions = [center, center]
    return max(0, min(positions) - padding), min(reference_length, max(positions) + padding)


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
    selected_candidates: list[dict[str, Any]],
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
    candidate_by_meeting: dict[str, list[dict[str, Any]]] = {}
    for row in selected_candidates:
        candidate_by_meeting.setdefault(str(row["meeting_id"]), []).append(row)
    if len(refs) != 25 or set(refs) != set(trace_by_meeting) or set(refs) != set(candidate_by_meeting):
        raise ValueError("meeting identity closure failed")
    if len(trace_rows) != 396 or len(selected_candidates) != 200:
        raise ValueError("trace or candidate count drift")
    candidate_ids = {
        meeting_id: {str(row["candidate_id"]) for row in rows}
        for meeting_id, rows in candidate_by_meeting.items()
    }
    for row in trace_rows:
        if str(row["decision"]["top1_candidate_id"]) not in candidate_ids[str(row["meeting_id"])]:
            raise ValueError(f"top1 candidate outside meeting inventory: {row['turn_id']}")

    padding = int(config["construction"]["reference_window_padding_tokens"])
    census: list[dict[str, Any]] = []
    meetings: list[dict[str, Any]] = []
    aggregate_errors = 0
    aggregate_reference_tokens = 0
    inventory_reference_supported = 0
    inventory_pass0_supported = 0
    inventory_opportunities = 0
    for meeting_id in sorted(refs):
        meeting_rows = sorted(trace_by_meeting[meeting_id], key=lambda row: int(str(row["turn_id"]).rsplit("slice", 1)[1]))
        reference_tokens = tokens(str(refs[meeting_id]["transcription"]))
        if not reference_tokens:
            raise ValueError(f"empty normalized reference: {meeting_id}")
        hypothesis_tokens: list[str] = []
        intervals: list[tuple[int, int]] = []
        for row in meeting_rows:
            start = len(hypothesis_tokens)
            hypothesis_tokens.extend(tokens(str(row["pass0"]["transcript_text"])))
            intervals.append((start, len(hypothesis_tokens)))
        matcher = SequenceMatcher(None, hypothesis_tokens, reference_tokens, autojunk=True)
        opcodes = matcher.get_opcodes()
        errors = int(editdistance.eval(reference_tokens, hypothesis_tokens))
        aggregate_errors += errors
        aggregate_reference_tokens += len(reference_tokens)

        meeting_inventory_supported = 0
        meeting_inventory_pass0 = 0
        meeting_inventory_opportunities = 0
        for candidate in candidate_by_meeting[meeting_id]:
            phrase = tokens(str(candidate["value"]["canonical"]))
            if not phrase:
                raise ValueError(f"empty candidate normalization: {candidate['candidate_id']}")
            ref_supported = contains_phrase(reference_tokens, phrase)
            hyp_supported = contains_phrase(hypothesis_tokens, phrase)
            meeting_inventory_supported += int(ref_supported)
            meeting_inventory_pass0 += int(hyp_supported)
            meeting_inventory_opportunities += int(ref_supported and not hyp_supported)
        inventory_reference_supported += meeting_inventory_supported
        inventory_pass0_supported += meeting_inventory_pass0
        inventory_opportunities += meeting_inventory_opportunities

        classification_counts: Counter[str] = Counter()
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
            canonical = str(row["decision"]["selected_value"]["canonical"])
            phrase = tokens(canonical)
            if not phrase:
                raise ValueError(f"empty top1 normalization: {row['turn_id']}")
            reference_support = contains_phrase(window, phrase)
            pass0_slice_tokens = tokens(str(row["pass0"]["transcript_text"]))
            pass0_support = contains_phrase(pass0_slice_tokens, phrase)
            if reference_support and pass0_support:
                classification = "retain"
            elif reference_support:
                classification = "wrong_to_correct_opportunity"
            else:
                classification = "unsupported_activation"
            classification_counts[classification] += 1
            census.append({
                "schema": "material-lhcp-development-opportunity-row-v1",
                "position": trace_positions[str(row["turn_id"])],
                "meeting_id": meeting_id,
                "turn_id": row["turn_id"],
                "speaker_labels": row["runtime_context"]["speaker_labels"],
                "potentially_truncated": bool(row["runtime_context"]["potentially_truncated"]),
                "candidate_id": row["decision"]["top1_candidate_id"],
                "canonical": canonical,
                "canonical_tokens": phrase,
                "reference_token_span": [ref_start, ref_end],
                "reference_window_sha256": hashlib.sha256(" ".join(window).encode("utf-8")).hexdigest(),
                "reference_support": reference_support,
                "pass0_support": pass0_support,
                "classification": classification,
            })
        meetings.append({
            "meeting_id": meeting_id,
            "split": refs[meeting_id]["split"],
            "reference_tokens": len(reference_tokens),
            "pass0_tokens": len(hypothesis_tokens),
            "wer_errors": errors,
            "wer": errors / len(reference_tokens),
            "inventory_keys": len(candidate_by_meeting[meeting_id]),
            "inventory_reference_supported": meeting_inventory_supported,
            "inventory_pass0_supported": meeting_inventory_pass0,
            "inventory_wrong_to_correct_opportunities": meeting_inventory_opportunities,
            "trace_rows": len(meeting_rows),
            "retain": classification_counts["retain"],
            "wrong_to_correct_opportunities": classification_counts["wrong_to_correct_opportunity"],
            "unsupported_activations": classification_counts["unsupported_activation"],
        })

    census.sort(key=lambda row: int(row["position"]))
    counts = Counter(str(row["classification"]) for row in census)
    opportunity_meetings = len({str(row["meeting_id"]) for row in census if row["classification"] == "wrong_to_correct_opportunity"})
    supported = counts["retain"] + counts["wrong_to_correct_opportunity"]
    support_rate = supported / len(census)
    power_table = [
        {
            "absolute_effect": effect,
            "discordant_fraction": discordance,
            "required_pairs": required_pairs(effect, discordance),
            "primary_opportunity_supply_sufficient": counts["wrong_to_correct_opportunity"] >= required_pairs(effect, discordance),
        }
        for effect in (0.05, 0.10, 0.15, 0.20)
        for discordance in (0.10, 0.20, 0.30)
    ]
    gates = {
        "minimum_primary_opportunities": counts["wrong_to_correct_opportunity"] >= int(config["gates"]["minimum_primary_opportunities"]),
        "minimum_opportunity_meetings": opportunity_meetings >= int(config["gates"]["minimum_opportunity_meetings"]),
        "minimum_local_reference_support_rate": support_rate >= float(config["gates"]["minimum_local_reference_support_rate"]),
    }
    if all(gates.values()):
        verdict = "LHCP_CORRECTION_OPPORTUNITY_POWER_READY"
    elif (
        counts["wrong_to_correct_opportunity"] >= int(config["gates"]["exploratory_minimum_opportunities"])
        and opportunity_meetings >= int(config["gates"]["exploratory_minimum_meetings"])
    ):
        verdict = "LHCP_CORRECTION_OPPORTUNITY_EXPLORATORY_ONLY"
    else:
        verdict = "LHCP_CORRECTION_OPPORTUNITY_INSUFFICIENT"
    strata: dict[str, dict[str, int | float]] = {}
    for label, rows in {
        "single_speaker_label": [row for row in census if len(row["speaker_labels"]) == 1],
        "multiple_speaker_labels": [row for row in census if len(row["speaker_labels"]) > 1],
    }.items():
        row_counts = Counter(str(row["classification"]) for row in rows)
        strata[label] = {
            "rows": len(rows),
            "retain": row_counts["retain"],
            "wrong_to_correct_opportunities": row_counts["wrong_to_correct_opportunity"],
            "unsupported_activations": row_counts["unsupported_activation"],
            "local_reference_support_rate": (
                (row_counts["retain"] + row_counts["wrong_to_correct_opportunity"]) / len(rows)
                if rows else 0.0
            ),
        }
    result = {
        "schema": "material-lhcp-development-opportunity-power-read-v1",
        "experiment_id": config["experiment_id"],
        "reference_access": {"development_meetings": 25, "confirmation_meetings": 0},
        "model_contact": {"embedding_calls": 0, "omni_calls": 0},
        "baseline": {
            "reference_tokens": aggregate_reference_tokens,
            "wer_errors": aggregate_errors,
            "micro_wer": aggregate_errors / aggregate_reference_tokens,
        },
        "material_inventory": {
            "keys": len(selected_candidates),
            "reference_supported_keys": inventory_reference_supported,
            "pass0_supported_keys": inventory_pass0_supported,
            "wrong_to_correct_candidate_opportunities": inventory_opportunities,
        },
        "primary_census": {
            "rows": len(census),
            "retain": counts["retain"],
            "wrong_to_correct_opportunities": counts["wrong_to_correct_opportunity"],
            "unsupported_activations": counts["unsupported_activation"],
            "local_reference_supported": supported,
            "local_reference_support_rate": support_rate,
            "opportunity_meetings": opportunity_meetings,
        },
        "strata": strata,
        "power": {
            "two_sided_alpha": 0.05,
            "target_power": 0.8,
            "primary_target": {"absolute_effect": 0.10, "discordant_fraction": 0.20, "required_pairs": 157},
            "table": power_table,
        },
        "gates": gates,
        "verdict": verdict,
        "claim_boundary": "Exact-canonical supply under a deterministic reference-span proxy; not timestamp gold, model correction, or deployment safety.",
    }
    return result, census, meetings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--reference-root", required=True, type=Path)
    parser.add_argument("--semantic-root", required=True, type=Path)
    parser.add_argument("--supply-root", required=True, type=Path)
    parser.add_argument("--pass0-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output_root.exists() or args.out.exists():
        parser.error("output exists; refusing to overwrite")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    bindings = {
        "semantic_trace_sha256": args.semantic_root / "trace.jsonl",
        "semantic_receipt_sha256": args.semantic_root / "receipt.json",
        "selected_candidates_sha256": args.supply_root / "selected-candidates.json",
        "pass0_index_sha256": args.pass0_root / "index.jsonl",
        "reader_sha256": Path(__file__).resolve(),
    }
    for field, path in bindings.items():
        if sha256_file(path) != config["inputs"][field]:
            raise ValueError(f"{field} mismatch")
    reference_receipt = json.loads((args.reference_root / "receipt.json").read_text(encoding="utf-8"))
    if (
        reference_receipt.get("verdict") != "LHCP_DEVELOPMENT_REFERENCES_ACQUIRED"
        or reference_receipt.get("development_references") != 25
        or reference_receipt.get("confirmation_access") != 0
        or reference_receipt.get("test_split_access") != 0
        or reference_receipt.get("audio_body_reads") != 0
        or reference_receipt.get("config_sha256") != sha256_file(args.config)
    ):
        raise ValueError("reference acquisition prerequisite failed")
    reference_artifact = reference_receipt.get("artifacts", {}).get("references.jsonl", {})
    reference_path = args.reference_root / "references.jsonl"
    if (
        reference_artifact.get("sha256") != sha256_file(reference_path)
        or reference_artifact.get("bytes") != reference_path.stat().st_size
    ):
        raise ValueError("reference artifact receipt mismatch")
    references = [json.loads(line) for line in reference_path.read_text(encoding="utf-8").splitlines()]
    trace_rows = [json.loads(line) for line in (args.semantic_root / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    selected_candidates = json.loads((args.supply_root / "selected-candidates.json").read_text(encoding="utf-8"))["candidates"]
    result, census, meetings = audit(config, references, trace_rows, selected_candidates)
    args.output_root.mkdir(parents=True)
    census_path = args.output_root / "census.jsonl"
    meetings_path = args.output_root / "meeting-summaries.json"
    write_jsonl_exclusive(census_path, census)
    write_json_exclusive(meetings_path, {"schema": "material-lhcp-development-opportunity-meetings-v1", "meetings": meetings})
    receipt = {
        "schema": "material-lhcp-development-opportunity-power-receipt-v1",
        "experiment_id": config["experiment_id"],
        "reference_reads": 25,
        "confirmation_access": 0,
        "embedding_calls": 0,
        "omni_calls": 0,
        "verdict": result["verdict"],
        "artifacts": {
            name: {"sha256": sha256_file(args.output_root / name), "bytes": (args.output_root / name).stat().st_size}
            for name in ("census.jsonl", "meeting-summaries.json")
        },
    }
    write_json_exclusive(args.output_root / "receipt.json", receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "primary_census": result["primary_census"], "gates": result["gates"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
