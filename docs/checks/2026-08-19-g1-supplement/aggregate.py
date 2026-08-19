#!/usr/bin/env python3
"""Rebuild the G1 VAD supplement's summary over every per-meeting receipt.

The supplement runs as TWO `scripts/run_precomp.py` invocations (nine meetings
each). Each invocation's own in-process `PrecompBudget` is already cumulative
across both -- it is pre-charged natively from every receipt on disk
(`PrecompBudget.precharge` / `run_precomp.load_wave_receipts`) before its loop
starts, against the registered `g1-supplement` ceilings. What an invocation's
own `wave-summary.json` cannot carry is the OUTCOME list for meetings it never
ran; `build_wave_summary` sees only its own process's outcomes. This re-emits
the single summary artefact over the whole receipt set using the machinery's
own `build_wave_summary`/`write_wave_summary` -- never a hand-rolled shape.

Same contract as `docs/checks/2026-08-19-precomp-wave1/aggregate_resume.py`;
only the ceilings profile and the VAD-aware totals differ.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["REPO"] + "/src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ledger import PROFILE, load_receipts, totals  # noqa: E402

from meeting_minutes_agent.precomp.budget import ceilings_for_profile  # noqa: E402
from meeting_minutes_agent.precomp.receipts import build_wave_summary, write_wave_summary  # noqa: E402


def main() -> int:
    out_dir = Path(sys.argv[1])
    stopped_reason = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None

    receipts = load_receipts(out_dir)
    receipts.sort(key=lambda r: str(r.get("meeting_id")))
    used = totals(receipts)
    ceilings = ceilings_for_profile(PROFILE)
    budget_totals = {
        "ceilings": ceilings.to_dict(),
        "ceilings_profile": PROFILE,
        "diar_gpu_seconds_used": used["diar_gpu_seconds_used"],
        "encode_gpu_seconds_used": used["encode_gpu_seconds_used"],
        "cutting_wall_seconds_used": used["cutting_wall_seconds_used"],
        "encode_calls_used": used["encode_calls_used"],
        "accounting_note": (
            "Cumulative over every per-meeting receipt of the G1 VAD supplement (pass A + pass B). "
            "Each pass ran as one run_precomp.py --turn-sources vad --ceilings-profile g1-supplement "
            "invocation whose PrecompBudget was pre-charged natively from the receipts already on "
            "disk (PrecompBudget.precharge / load_wave_receipts), so the registered supplement "
            "ceilings were enforced fail-closed across both passes in-process. This file re-emits "
            "the summary over all receipts because build_wave_summary sees only the outcomes of the "
            "process that wrote it. Diar usage is 0 by construction: --turn-sources vad never "
            "contacts the pinned diar tool."
        ),
    }
    summary = build_wave_summary(receipts, wave=1, budget_totals=budget_totals, stopped_reason=stopped_reason)
    path = write_wave_summary(out_dir, summary)
    print(json.dumps({
        "wrote": str(path),
        "n_meetings": summary["n_meetings"],
        "n_ok": summary["n_ok"],
        "n_error": summary["n_error"],
        "stopped_reason": summary["stopped_reason"],
        "encode_calls_used": used["encode_calls_used"],
        "vad_slices": used["vad_slices"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
