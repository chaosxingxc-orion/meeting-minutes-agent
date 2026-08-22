#!/usr/bin/env python3
"""Freeze the Earnings-22 reserve-only inputs for E4-XDOMAIN-SUPPLY-AUDIT-v3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from meeting_minutes_agent.probes.e4_xdomain_supply_v3 import build_reserve_manifest  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--earnings22-root", required=True)
    parser.add_argument("--parent-manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        parser.error("reserve manifest output exists; refusing overwrite")
    parent = json.loads(Path(args.parent_manifest).read_text(encoding="utf-8"))
    manifest = build_reserve_manifest(parent, Path(args.earnings22_root))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"reserve_inputs": len(manifest["inputs"]), "content_hash": manifest["content_hash"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
