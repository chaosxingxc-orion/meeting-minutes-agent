#!/usr/bin/env python3
"""Operator-side cumulative ledger for the G1 VAD supplement.

An independent cross-check of the runner's OWN native precharge
(`PrecompBudget.precharge` / `run_precomp.load_wave_receipts`, which already
enforces the registered ceilings fail-closed in-process across both passes).
This never enforces anything and never relaxes a ceiling: it re-derives
cumulative usage from the receipts on disk and re-applies the SAME registered
`g1-supplement` profile the runner carries, so the two figures can be compared.

Ported from `docs/checks/2026-08-19-precomp-wave1/budget_ledger.py`, with two
changes the VAD turn source requires: the encode-GPU sum includes the `"vad"`
source key (wave-1 had only `"tool"`/`"oracle"`), and the ceilings come from
`ceilings_for_profile("g1-supplement")` rather than `ceilings_for_wave`.

Exit code 0 = admissible, 3 = a ceiling already reached (stop and land).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["REPO"] + "/src")

from meeting_minutes_agent.precomp.budget import ceilings_for_profile  # noqa: E402

PROFILE = "g1-supplement"
SOURCES = ("tool", "oracle", "vad")


def load_receipts(out_dir: Path) -> list[dict]:
    receipts_dir = Path(out_dir) / "receipts"
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
            for key in SOURCES
            for o in (r.get("encode_warm", {}).get(key) or [])
        ),
        "encode_wall_seconds": sum(num(r.get("encode_warm", {}).get("wall_seconds")) for r in receipts),
        "vad_slices": sum(
            int(((r.get("slice_plans") or {}).get("vad") or {}).get("n_slices") or 0) for r in receipts
        ),
    }


def main() -> int:
    out_dir = Path(sys.argv[1])
    ceilings = ceilings_for_profile(PROFILE)
    used = totals(load_receipts(out_dir))

    breaches = []
    if used["encode_calls_used"] >= ceilings.max_encode_calls:
        breaches.append(f"encode call-count ceiling reached: {used['encode_calls_used']} of {ceilings.max_encode_calls}")
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

    print(json.dumps({"profile": PROFILE, "used": used, "ceilings": ceilings.to_dict(), "breaches": breaches}, sort_keys=True))
    return 3 if breaches else 0


if __name__ == "__main__":
    raise SystemExit(main())
