#!/usr/bin/env python3
"""Per-meeting completion table from the PRECOMP receipts (descriptive only)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from budget_ledger import load_receipts, totals  # noqa: E402


def main() -> int:
    out_dir = Path(sys.argv[1])
    receipts = sorted(load_receipts(out_dir), key=lambda r: str(r.get("meeting_id")))
    header = (
        "| meeting | ok | diar wall s | turns tool/oracle | slices tool/oracle (delta) | "
        "cut wall s | encode calls | encode wall s | cache entries +/bytes + | bdisp med/max s |"
    )
    print(header)
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in receipts:
        m = r.get("metrics") or {}
        tc = m.get("turn_counts") or {}
        sc = m.get("slice_counts") or {}
        cd = (m.get("cache") or {}).get("delta") or {}
        bd = m.get("boundary_displacement") or {}
        diar = r.get("diar") or {}
        cut = r.get("cutting") or {}
        enc = r.get("encode_warm") or {}

        def f(v, spec=".1f"):
            return format(v, spec) if isinstance(v, (int, float)) else "-"

        print(
            f"| {r.get('meeting_id')} | {'yes' if r.get('ok') else 'NO'} "
            f"| {f(diar.get('wall_seconds'))} "
            f"| {tc.get('tool_turns','-')}/{tc.get('oracle_turns','-')} "
            f"| {sc.get('tool_slices','-')}/{sc.get('oracle_slices','-')} ({sc.get('delta','-')}) "
            f"| {f(cut.get('wall_seconds'), '.2f')} "
            f"| {enc.get('n_calls','-')} "
            f"| {f(enc.get('wall_seconds'))} "
            f"| {cd.get('entries_added','-')} / {cd.get('bytes_added','-')} "
            f"| {f(bd.get('median_s'), '.1f')}/{f(bd.get('max_s'), '.1f')} |"
        )
        if not r.get("ok"):
            print(f"|   error | {str(r.get('error'))[:300]} | | | | | | | | |")

    used = totals(receipts)
    print()
    print(json.dumps(used, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
