#!/usr/bin/env python3
"""Read the frozen LHCP query supply without references or model contact."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from build_material_lhcp_development_query_supply import (
    build_supply,
    derangement,
    sha256_file,
)


FORBIDDEN_OUTPUT_FIELDS = {"reference_text", "answer_text", "gold_text", "transcript_reference"}


def _field_names(value: Any) -> set[str]:
    fields: set[str] = set()
    if isinstance(value, dict):
        fields.update(str(key) for key in value)
        for nested in value.values():
            fields.update(_field_names(nested))
    elif isinstance(value, list):
        for nested in value:
            fields.update(_field_names(nested))
    return fields


def read_supply(
    config: dict[str, Any],
    cohort: dict[str, Any],
    source_pool: dict[str, Any],
    pass0_rows: list[dict[str, Any]],
    output_root: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    selected_document = json.loads((output_root / "selected-candidates.json").read_text(encoding="utf-8"))
    mapping_document = json.loads((output_root / "derangement.json").read_text(encoding="utf-8"))
    queries = [json.loads(line) for line in (output_root / "queries.jsonl").read_text(encoding="utf-8").splitlines()]
    receipt = json.loads((output_root / "receipt.json").read_text(encoding="utf-8"))
    expected_selected, expected_inventory, expected_mapping, expected_queries = build_supply(
        config, cohort, source_pool, pass0_rows
    )
    selected = selected_document.get("candidates", [])
    if selected != expected_selected:
        errors.append("selected candidate construction differs")
    if mapping_document.get("mapping") != expected_mapping or expected_mapping != derangement(expected_mapping):
        errors.append("deranged mapping differs")
    if queries != expected_queries:
        errors.append("query construction differs")
    meeting_ids = sorted(expected_mapping)
    if sorted(expected_mapping.values()) != meeting_ids or any(key == value for key, value in expected_mapping.items()):
        errors.append("deranged mapping is not a fixed-point-free bijection")
    width = int(config["construction"]["key_width"])
    selected_counts = Counter(str(row.get("meeting_id")) for row in selected)
    if selected_counts != Counter({meeting_id: width for meeting_id in meeting_ids}):
        errors.append("selected candidate width differs")
    if len({str(row.get("candidate_id")) for row in selected}) != len(selected):
        errors.append("candidate IDs are not unique")
    if len(queries) != int(config["passing_gates"]["queries"]):
        errors.append("query count differs")
    if [int(row.get("position", -1)) for row in queries] != list(range(len(queries))):
        errors.append("query positions differ")
    truncated = [row for row in queries if row.get("potentially_truncated")]
    expected_truncated = int(config["construction"]["length_limited_position"])
    if len(truncated) != 1 or int(truncated[0]["position"]) != expected_truncated:
        errors.append("length-limited marker differs")
    output_fields = _field_names([selected_document, mapping_document, queries, receipt])
    leaked_fields = sorted(output_fields & FORBIDDEN_OUTPUT_FIELDS)
    if leaked_fields:
        errors.append(f"forbidden output fields present: {','.join(leaked_fields)}")
    artifacts = receipt.get("artifacts", {})
    for name in ("selected-candidates.json", "derangement.json", "queries.jsonl"):
        path = output_root / name
        binding = artifacts.get(name, {})
        if binding.get("sha256") != sha256_file(path) or int(binding.get("bytes", -1)) != path.stat().st_size:
            errors.append(f"artifact binding differs: {name}")
    expected_totals = {
        "meetings": len(expected_inventory),
        "available_candidates": sum(int(row["available_candidates"]) for row in expected_inventory),
        "selected_candidates": len(expected_selected),
        "queries": len(expected_queries),
        "queries_with_prior_context": sum(bool(row["runtime_context"]["prior_turn_id"]) for row in expected_queries),
        "potentially_truncated_queries": 1,
    }
    if receipt.get("totals") != expected_totals or receipt.get("meeting_inventory") != expected_inventory:
        errors.append("receipt totals or inventory differ")
    if (
        receipt.get("reference_reads") != 0
        or receipt.get("confirmation_access") != 0
        or receipt.get("embedding_calls") != 0
        or receipt.get("omni_calls") != 0
    ):
        errors.append("execution firewall differs")
    return {
        "schema": "material-lhcp-development-query-supply-read-v1",
        "experiment_id": config["experiment_id"],
        "counts": expected_totals,
        "candidate_count_minimum": min(int(row["available_candidates"]) for row in expected_inventory),
        "candidate_count_median": sorted(int(row["available_candidates"]) for row in expected_inventory)[len(expected_inventory) // 2],
        "derangement_fixed_points": sum(key == value for key, value in expected_mapping.items()),
        "forbidden_output_fields": leaked_fields,
        "reference_access": "NONE",
        "confirmation_access": "NONE",
        "embedding_contact": "NONE",
        "omni_contact": "NONE",
        "errors": errors,
        "verdict": "LHCP_DEVELOPMENT_QUERY_SUPPLY_READY" if not errors else "LHCP_DEVELOPMENT_QUERY_SUPPLY_INVALID",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--supply-root", required=True, type=Path)
    parser.add_argument("--pass0-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error(f"output exists: {args.out}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    cohort = json.loads(args.cohort.read_text(encoding="utf-8"))
    source_pool = json.loads((args.supply_root / "candidate-pool.json").read_text(encoding="utf-8"))
    pass0_rows = [json.loads(line) for line in (args.pass0_root / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    result = read_supply(config, cohort, source_pool, pass0_rows, args.output_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0 if not result["errors"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
