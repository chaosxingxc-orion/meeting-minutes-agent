#!/usr/bin/env python3
"""Operator-side cumulative wave ledger for a PER-MEETING invocation loop.

`scripts/run_precomp.py` builds a fresh `PrecompBudget` per process, so a
meeting-by-meeting loop (needed for the yield protocol -- the runner exposes no
in-flight stop hook) would reset the WAVE-level ceilings every invocation. This
helper re-derives the wave-cumulative usage from the committed per-meeting
receipts and re-applies the SAME registered ceilings the runner carries
(`meeting_minutes_agent.precomp.budget.ceilings_for_wave`), fail-closed, before
the next meeting starts. It never relaxes a ceiling: it is a strict addition on
top of the in-process guard, matching `PrecompBudget.check_before_*` semantics
("refuse to START another step once usage has reached the ceiling").

Exit code 0 = admissible, 3 = a wave ceiling already reached (stop and land).
Prints a one-line JSON usage summary either way.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["REPO"] + "/src")

from meeting_minutes_agent.precomp.budget import ceilings_for_wave  # noqa: E402


def load_receipts(out_dir: Path) -> list[dict]:
    receipts_dir = out_dir / "receipts"
    if not receipts_dir.is_dir():
        return []
    out = []
    for path in sorted(receipts_dir.glob("*-receipt.json")):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except ValueError:
            continue
    return out


def totals(receipts: list[dict]) -> dict:
    def num(value) -> float:
        return float(value) if isinstance(value, (int, float)) else 0.0

    return {
        "n_receipts": len(receipts),
        "n_ok": sum(1 for r in receipts if r.get("ok")),
        "encode_calls_used": sum(int(r.get("encode_warm", {}).get("n_calls") or 0) for r in receipts),
        "cutting_wall_seconds_used": sum(num(r.get("cutting", {}).get("wall_seconds")) for r in receipts),
        "diar_gpu_seconds_used": sum(num(r.get("diar", {}).get("gpu_seconds_estimate")) for r in receipts),
        "encode_gpu_seconds_used": sum(
            num(o.get("gpu_seconds_estimate"))
            for r in receipts
            for key in ("tool", "oracle")
            for o in (r.get("encode_warm", {}).get(key) or [])
        ),
        "diar_wall_seconds": sum(num(r.get("diar", {}).get("wall_seconds")) for r in receipts),
        "encode_wall_seconds": sum(num(r.get("encode_warm", {}).get("wall_seconds")) for r in receipts),
    }


def main() -> int:
    wave = int(sys.argv[1])
    out_dir = Path(sys.argv[2])
    ceilings = ceilings_for_wave(wave)
    used = totals(load_receipts(out_dir))

    breaches = []
    if used["encode_calls_used"] >= ceilings.max_encode_calls:
        breaches.append(
            f"encode call-count ceiling reached: {used['encode_calls_used']} of {ceilings.max_encode_calls}"
        )
    if used["encode_gpu_seconds_used"] >= ceilings.max_encode_gpu_hours * 3600.0:
        breaches.append(
            f"encode GPU-hour ceiling reached: {used['encode_gpu_seconds_used']:.1f}s of "
            f"{ceilings.max_encode_gpu_hours * 3600.0:.1f}s"
        )
    if used["diar_gpu_seconds_used"] >= ceilings.max_diar_gpu_hours * 3600.0:
        breaches.append(
            f"diar GPU-hour ceiling reached: {used['diar_gpu_seconds_used']:.1f}s of "
            f"{ceilings.max_diar_gpu_hours * 3600.0:.1f}s"
        )
    if (
        ceilings.max_cutting_wall_hours is not None
        and used["cutting_wall_seconds_used"] >= ceilings.max_cutting_wall_hours * 3600.0
    ):
        breaches.append(
            f"CPU-cutting wall-hour ceiling reached: {used['cutting_wall_seconds_used']:.1f}s of "
            f"{ceilings.max_cutting_wall_hours * 3600.0:.1f}s"
        )

    print(json.dumps({"used": used, "ceilings": ceilings.to_dict(), "breaches": breaches}, sort_keys=True))
    return 3 if breaches else 0


if __name__ == "__main__":
    raise SystemExit(main())
