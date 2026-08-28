#!/usr/bin/env python3
"""One-shot reader for LHCP full-pool semantic extraction rankings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from download_material_lhcp_development_audio import sha256_file  # noqa: E402


def evaluate(runtime: dict[str, Any], rankings: list[dict[str, Any]], oracle_rows: list[dict[str, Any]]) -> dict[str, Any]:
    oracle = {str(row["turn_id"]): row for row in oracle_rows}
    if len(rankings) != 396 or len(oracle) != 396:
        raise ValueError("ranking/oracle count drift")
    widths = [int(value) for value in runtime["evaluation"]["widths"]]
    oracle_slices = sum(bool(row["any_opportunity"]) for row in oracle_rows)
    table = []
    for width in widths:
        hits = 0
        meetings: set[str] = set()
        for position, row in enumerate(rankings):
            turn_id = str(row["turn_id"])
            if int(row["position"]) != position or int(oracle[turn_id]["position"]) != position:
                raise ValueError(f"ranking identity drift: {turn_id}")
            opportunity_ids = {str(value["candidate_id"]) for value in oracle[turn_id]["opportunities"]}
            ranked_ids = {str(value["candidate_id"]) for value in row["ranking"][:width]}
            if opportunity_ids.intersection(ranked_ids):
                hits += 1
                meetings.add(str(row["meeting_id"]))
        table.append({
            "width": width,
            "opportunity_hit_slices": hits,
            "oracle_opportunity_recall": hits / oracle_slices,
            "all_slice_coverage": hits / len(rankings),
            "opportunity_meetings": len(meetings),
        })
    primary = next(row for row in table if row["width"] == int(runtime["evaluation"]["primary_width"]))
    gates = runtime["gates"]
    if primary["opportunity_hit_slices"] >= int(gates["minimum_primary_opportunity_slices"]) and primary["opportunity_meetings"] >= int(gates["minimum_primary_opportunity_meetings"]):
        verdict = "FULL_POOL_SEMANTIC_EXTRACTION_POWER_READY"
    elif primary["opportunity_hit_slices"] >= int(gates["exploratory_minimum_opportunity_slices"]) and primary["opportunity_meetings"] >= int(gates["exploratory_minimum_opportunity_meetings"]):
        verdict = "FULL_POOL_SEMANTIC_EXTRACTION_EXPLORATORY_ONLY"
    else:
        verdict = "FULL_POOL_SEMANTIC_EXTRACTION_INSUFFICIENT"
    return {
        "schema": "material-lhcp-full-pool-semantic-extractor-read-v1",
        "experiment_id": runtime["experiment_id"],
        "evidence_status": "POST_REFERENCE_DEVELOPMENT_DISCOVERY",
        "reference_access": {"new_reference_reads": 0, "confirmation_meetings": 0},
        "model_contact": {"embedding_calls": int(runtime["embedding"]["maximum_calls"]), "omni_calls": 0},
        "oracle_opportunity_slices": oracle_slices,
        "width_table": table,
        "primary_metrics": primary,
        "verdict": verdict,
        "claim_boundary": "Post-reference development semantic extraction; not independent validation, dispatch safety, or transcription gain.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--flight-root", required=True, type=Path)
    parser.add_argument("--oracle-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error(f"output exists: {args.out}")
    runtime = json.loads(args.runtime.read_text(encoding="utf-8"))
    receipt = json.loads((args.flight_root / "receipt.json").read_text(encoding="utf-8"))
    if (
        receipt.get("verdict") != "LHCP_FULL_POOL_SEMANTIC_TRACE_COMPLETE"
        or receipt.get("embedding_calls") != int(runtime["embedding"]["maximum_calls"])
        or receipt.get("confirmation_access") != 0
        or receipt.get("omni_calls") != 0
    ):
        raise ValueError("flight receipt prerequisite failed")
    if receipt["artifacts"]["rankings.jsonl"]["sha256"] != sha256_file(args.flight_root / "rankings.jsonl"):
        raise ValueError("ranking receipt mismatch")
    if sha256_file(args.oracle_root / "receipt.json") != runtime["inputs"]["oracle_receipt_sha256"] or sha256_file(args.oracle_root / "rows.jsonl") != runtime["inputs"]["oracle_rows_sha256"]:
        raise ValueError("oracle binding mismatch")
    rankings = [json.loads(line) for line in (args.flight_root / "rankings.jsonl").read_text(encoding="utf-8").splitlines()]
    oracle_rows = [json.loads(line) for line in (args.oracle_root / "rows.jsonl").read_text(encoding="utf-8").splitlines()]
    result = evaluate(runtime, rankings, oracle_rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "primary_metrics": result["primary_metrics"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
