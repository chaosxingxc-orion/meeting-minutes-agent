#!/usr/bin/env python3
"""One-shot reference-blind reader for the sealed confirmation trace."""

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

from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402
from meeting_minutes_agent.state.material_trace import validate_trace_row  # noqa: E402


def read_gate(runtime: dict[str, Any], rows: list[dict[str, Any]], validation: dict[str, Any]) -> dict[str, Any]:
    if validation.get("verdict") != "TRACE_COMPLETE" or validation.get("rows") != 80:
        raise ValueError("complete confirmation trace prerequisite failed")
    if len(rows) != 80 or any(validate_trace_row(row) for row in rows):
        raise ValueError("confirmation trace row invariant failed")
    threshold = float(runtime["confirmation_threshold"])
    dispatched = [row for row in rows if float(row["decision"]["selector_gap"]) >= threshold]
    wins = sum(float(row["decision"]["top1_score"]) > float(row["deranged_control"]["score"]) for row in dispatched)
    deltas = [float(row["decision"]["top1_score"]) - float(row["deranged_control"]["score"]) for row in dispatched]
    meeting_ids = sorted({str(row["meeting_id"]) for row in rows})
    per_meeting = []
    for meeting_id in meeting_ids:
        local = [row for row in dispatched if str(row["meeting_id"]) == meeting_id]
        local_wins = sum(float(row["decision"]["top1_score"]) > float(row["deranged_control"]["score"]) for row in local)
        per_meeting.append({
            "meeting_id": meeting_id,
            "dispatched_turns": len(local),
            "attribution_wins": local_wins,
            "attribution_precision": local_wins / len(local) if local else 0.0,
        })
    meetings_over_floor = sum(
        float(row["attribution_precision"]) >= float(runtime["gate"]["per_meeting_precision_floor"])
        for row in per_meeting
    )
    totals = {
        "eligible_turns": len(rows),
        "dispatched_turns": len(dispatched),
        "dispatch_coverage": len(dispatched) / len(rows),
        "attribution_wins": wins,
        "attribution_precision": wins / len(dispatched) if dispatched else 0.0,
        "median_correct_minus_deranged_cosine": median(deltas) if deltas else 0.0,
        "meetings": len(meeting_ids),
        "meetings_over_precision_floor": meetings_over_floor,
    }
    gates = {
        "minimum_attribution_precision": totals["attribution_precision"] >= float(runtime["gate"]["minimum_attribution_precision"]),
        "minimum_coverage": totals["dispatch_coverage"] >= float(runtime["gate"]["minimum_coverage"]),
        "minimum_distributed_meetings": meetings_over_floor >= int(runtime["gate"]["minimum_meetings_over_precision_floor"]),
        "minimum_median_correct_minus_deranged": totals["median_correct_minus_deranged_cosine"] >= float(runtime["gate"]["minimum_median_correct_minus_deranged"]),
    }
    return {
        "schema": "material-new-surface-confirmation-gate-read-v1",
        "experiment_id": runtime["experiment_id"],
        "reference_access": "NONE",
        "threshold_source": runtime["inputs"]["development_read_sha256"],
        "confirmation_threshold": threshold,
        "totals": totals,
        "per_meeting": per_meeting,
        "gates": gates,
        "verdict": "CONFIRMATION_SIGNAL_PRESENT" if all(gates.values()) else "CONFIRMATION_SIGNAL_INSUFFICIENT",
        "claim_boundary": "Independent confirmation of semantic attribution only; no WER, abstention-value, or Omni correction claim.",
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
    expected = config_hash({key: value for key, value in runtime.items() if key != "content_hash"})
    if runtime.get("content_hash") != expected:
        raise ValueError("runtime content hash mismatch")
    rows = [json.loads(line) for line in args.trace.read_text(encoding="utf-8").splitlines()]
    validation = json.loads(args.validation.read_text(encoding="utf-8"))
    result = read_gate(runtime, rows, validation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": result["verdict"], "threshold": result["confirmation_threshold"], "totals": result["totals"], "gates": result["gates"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
