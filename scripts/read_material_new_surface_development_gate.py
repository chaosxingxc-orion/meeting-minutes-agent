#!/usr/bin/env python3
"""Read the frozen development material trace without reference access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.state.material_trace import validate_trace_row  # noqa: E402
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402


def summarize(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    dispatched = [row for row in rows if float(row["decision"]["selector_gap"]) >= threshold]
    wins = sum(float(row["decision"]["top1_score"]) > float(row["deranged_control"]["score"]) for row in dispatched)
    meetings = sorted({str(row["meeting_id"]) for row in dispatched})
    deltas = [float(row["decision"]["top1_score"]) - float(row["deranged_control"]["score"]) for row in dispatched]
    return {
        "eligible_turns": len(rows),
        "dispatched_turns": len(dispatched),
        "dispatch_coverage": len(dispatched) / len(rows) if rows else 0.0,
        "attribution_wins": wins,
        "attribution_precision": wins / len(dispatched) if dispatched else 0.0,
        "represented_meetings": len(meetings),
        "meeting_ids": meetings,
        "median_correct_minus_deranged_cosine": median(deltas) if deltas else 0.0,
    }


def read_gate(runtime: dict[str, Any], rows: list[dict[str, Any]], validation: dict[str, Any]) -> dict[str, Any]:
    if validation.get("verdict") != "TRACE_COMPLETE" or validation.get("rows") != 40:
        raise ValueError("complete trace validation prerequisite failed")
    if len(rows) != 40 or any(validate_trace_row(row) for row in rows):
        raise ValueError("trace row invariant failed")
    grid = []
    selected = None
    for threshold in runtime["gate"]["threshold_grid"]:
        value = float(threshold)
        totals = summarize(rows, value)
        gates = {
            "minimum_attribution_precision": totals["attribution_precision"] >= float(runtime["gate"]["minimum_attribution_precision"]),
            "minimum_coverage": totals["dispatch_coverage"] >= float(runtime["gate"]["minimum_coverage"]),
            "minimum_represented_meetings": totals["represented_meetings"] >= int(runtime["gate"]["minimum_represented_meetings"]),
            "minimum_median_correct_minus_deranged": totals["median_correct_minus_deranged_cosine"] >= float(runtime["gate"]["minimum_median_correct_minus_deranged"]),
        }
        passed = all(gates.values())
        grid.append({"threshold": value, "totals": totals, "gates": gates, "passed": passed})
        if selected is None and passed:
            selected = value
    return {
        "schema": "material-new-surface-development-gate-read-v1",
        "experiment_id": runtime["experiment_id"],
        "reference_access": "NONE",
        "selected_threshold": selected,
        "grid": grid,
        "verdict": "DEVELOPMENT_SIGNAL_PRESENT" if selected is not None else "DEVELOPMENT_SIGNAL_INSUFFICIENT",
        "claim_boundary": "Development semantic attribution only; no confirmation, WER, or Omni correction claim.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output exists: {args.output}")
    runtime = json.loads(args.runtime.read_text(encoding="utf-8"))
    expected_content_hash = config_hash({key: value for key, value in runtime.items() if key != "content_hash"})
    if runtime.get("content_hash") != expected_content_hash:
        raise ValueError("runtime content hash mismatch")
    rows = [json.loads(line) for line in args.trace.read_text(encoding="utf-8").splitlines()]
    validation = json.loads(args.validation.read_text(encoding="utf-8"))
    result = read_gate(runtime, rows, validation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "selected_threshold": result["selected_threshold"], "grid": result["grid"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
