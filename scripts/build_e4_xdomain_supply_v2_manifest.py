#!/usr/bin/env python3
"""Freeze Earnings-22 inputs for E4-XDOMAIN-SUPPLY-AUDIT-v2."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from meeting_minutes_agent.probes.e4_xdomain_supply_v2 import (  # noqa: E402
    build_input_manifest,
    select_inputs,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--earnings22-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        parser.error("manifest output exists; refusing overwrite")
    root = Path(args.earnings22_root)
    manifest = build_input_manifest(select_inputs(root), root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    counts = Counter(row["split"] for row in manifest["inputs"])
    print(json.dumps({"inputs": len(manifest["inputs"]), "splits": counts, "content_hash": manifest["content_hash"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
