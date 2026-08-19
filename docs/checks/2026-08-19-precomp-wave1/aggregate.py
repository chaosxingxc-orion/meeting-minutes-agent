#!/usr/bin/env python3
"""Rebuild the WAVE-level summary from every per-meeting receipt.

The per-meeting invocation loop (yield protocol) makes each
`scripts/run_precomp.py` process write a `wave-summary.json` covering only the
one meeting it ran. This re-emits the registered wave artefact over the whole
set, using the machinery's own `build_wave_summary` / `write_wave_summary` (never
a hand-rolled shape), with the operator-side cumulative budget totals.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["REPO"] + "/src")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from budget_ledger import load_receipts, totals  # noqa: E402

from meeting_minutes_agent.precomp.budget import ceilings_for_wave  # noqa: E402
from meeting_minutes_agent.precomp.receipts import build_wave_summary, write_wave_summary  # noqa: E402


def main() -> int:
    wave = int(sys.argv[1])
    out_dir = Path(sys.argv[2])
    stopped_reason = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None

    receipts = load_receipts(out_dir)
    receipts.sort(key=lambda r: str(r.get("meeting_id")))
    used = totals(receipts)
    ceilings = ceilings_for_wave(wave)
    budget_totals = {
        "ceilings": ceilings.to_dict(),
        "diar_gpu_seconds_used": used["diar_gpu_seconds_used"],
        "encode_gpu_seconds_used": used["encode_gpu_seconds_used"],
        "cutting_wall_seconds_used": used["cutting_wall_seconds_used"],
        "encode_calls_used": used["encode_calls_used"],
        "accounting_note": (
            "wave-cumulative, re-derived from the per-meeting receipts by the operator-side "
            "ledger (scratchpad budget_ledger.py): the per-meeting invocation loop required by "
            "the yield protocol gives each run_precomp.py process its own fresh PrecompBudget, "
            "so the registered WAVE ceilings were re-applied fail-closed between meetings on "
            "these same totals."
        ),
    }
    summary = build_wave_summary(receipts, wave=wave, budget_totals=budget_totals, stopped_reason=stopped_reason)
    path = write_wave_summary(out_dir, summary)
    print(json.dumps({
        "wrote": str(path),
        "n_meetings": summary["n_meetings"],
        "n_ok": summary["n_ok"],
        "n_error": summary["n_error"],
        "stopped_reason": summary["stopped_reason"],
        "encode_calls_used": used["encode_calls_used"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
