#!/usr/bin/env python3
"""Run the sole reserve read for E4-XDOMAIN-SUPPLY-AUDIT-v3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from meeting_minutes_agent.probes.e4_xdomain_supply_v2 import Earnings22AuditError  # noqa: E402
from meeting_minutes_agent.probes.e4_xdomain_supply_v3 import (  # noqa: E402
    assert_reserve_manifest_matches,
    build_reserve_manifest,
    build_verdict,
    render_report,
    reserve_inputs,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--earnings22-root", required=True)
    parser.add_argument("--parent-manifest", required=True)
    parser.add_argument("--reserve-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output_dir)
    if output.exists():
        parser.error("audit output directory exists; refusing overwrite")
    root = Path(args.earnings22_root)
    parent = json.loads(Path(args.parent_manifest).read_text(encoding="utf-8"))
    expected = json.loads(Path(args.reserve_manifest).read_text(encoding="utf-8"))
    actual = build_reserve_manifest(parent, root)
    assert_reserve_manifest_matches(expected, actual)
    verdict = build_verdict(reserve_inputs(actual, root), actual)
    output.mkdir(parents=True, exist_ok=False)
    (output / "verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "report.txt").write_text(render_report(verdict), encoding="utf-8")
    print(json.dumps({"decision": verdict["decision"], "model_calls": 0, "discovery_files_read": 0}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Earnings22AuditError as exc:
        print(f"INVALID-AUDIT: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
