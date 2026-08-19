#!/usr/bin/env python3
"""Per-meeting completion table for the G1 VAD supplement (descriptive only).

Mirrors `docs/checks/2026-08-19-precomp-wave1/table.py`, retargeted at the VAD
turn source: the tool/oracle columns are structurally absent from a
`--turn-sources vad` receipt, and the manifest path is the artefact G1's
Z-nodiar arm actually consumes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledger import load_receipts, totals  # noqa: E402


def main() -> int:
    out_dir = Path(sys.argv[1])
    receipts = sorted(load_receipts(out_dir), key=lambda r: str(r.get("meeting_id")))
    print("| meeting | ok | vad slices | plan content_hash | manifest written | cut wall s | encode calls | encode wall s | cache entries + | cache bytes + |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in receipts:
        m = r.get("metrics") or {}
        cd = (m.get("cache") or {}).get("delta") or {}
        vad_plan = (r.get("slice_plans") or {}).get("vad") or {}
        cut = r.get("cutting") or {}
        enc = r.get("encode_warm") or {}
        manifest = vad_plan.get("manifest_path")

        def f(v, spec=".1f"):
            return format(v, spec) if isinstance(v, (int, float)) else "-"

        chash = str(vad_plan.get("content_hash") or "-")
        print(
            f"| {r.get('meeting_id')} | {'yes' if r.get('ok') else 'NO'} "
            f"| {vad_plan.get('n_slices','-')} "
            f"| {chash[:12]} "
            f"| {'yes' if manifest else 'NO'} "
            f"| {f(cut.get('wall_seconds'), '.2f')} "
            f"| {enc.get('n_calls','-')} "
            f"| {f(enc.get('wall_seconds'))} "
            f"| {cd.get('entries_added','-')} "
            f"| {cd.get('bytes_added','-')} |"
        )
        if not r.get("ok"):
            print(f"|   error | {str(r.get('error'))[:300]} | | | | | | | | |")

    used = totals(receipts)
    print()
    print(json.dumps(used, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
