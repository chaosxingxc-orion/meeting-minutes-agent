#!/usr/bin/env python3
"""Mechanically assemble primary and supplemental E4 direction responses."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.probes.e4_disjoint_direction import build_requests, load_runtime_binding


def _records(paths: list[Path]) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                record = json.loads(line)
                request_id = str(record.get("request_id"))
                if request_id in records:
                    raise ValueError(f"duplicate request {request_id} in {path}:{line_number}")
                records[request_id] = record
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", required=True)
    parser.add_argument("--primary-responses", required=True)
    parser.add_argument("--supplement-response", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        parser.error("assembled output exists; refusing overwrite")
    requests = build_requests(load_runtime_binding(args.binding))
    records = _records([Path(args.primary_responses), Path(args.supplement_response)])
    expected_ids = {request.request_id for request in requests}
    if set(records) != expected_ids:
        parser.error(f"response set mismatch: missing={sorted(expected_ids - set(records))}, extra={sorted(set(records) - expected_ids)}")
    for request in requests:
        record = records[request.request_id]
        if record.get("outcome") != "ok" or record.get("target_id") != request.target.target_id or record.get("arm") != request.arm:
            parser.error(f"response metadata mismatch: {request.request_id}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as sink:
        for request in requests:
            sink.write(json.dumps(records[request.request_id], ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"calls": len(requests), "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
