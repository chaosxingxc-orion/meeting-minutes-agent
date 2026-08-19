#!/usr/bin/env python3
"""Rebuild the WAVE-level summary over every per-meeting receipt (resume pass).

The resume pass runs the whole remaining roster inside ONE
`scripts/run_precomp.py` invocation (`--resume --stop-file ...`), so the
runner's in-process `PrecompBudget` is already wave-cumulative: it is
pre-charged natively from every receipt on disk (`PrecompBudget.precharge` /
`run_precomp.load_wave_receipts`, commit e4e18c4) before the loop starts. What
that invocation's own `wave-summary.json` cannot carry is the OUTCOME list for
the meetings it skipped via `--resume` (`build_wave_summary` sees only this
process's outcomes). This re-emits the registered wave artefact over the whole
receipt set using the machinery's own `build_wave_summary` /
`write_wave_summary` -- never a hand-rolled shape -- so the single committed
`wave-summary.json` describes all completed meetings of the wave.

Same contract as the predecessor's `aggregate.py`; only the accounting note
differs, because the external per-meeting reconciliation it described is
retired.
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
            "wave-cumulative over every per-meeting receipt of the wave (initial pass + resume "
            "pass). The resume pass ran the remaining roster in a single run_precomp.py "
            "invocation whose PrecompBudget was pre-charged natively from the receipts already "
            "on disk (PrecompBudget.precharge / load_wave_receipts, commit e4e18c4), so the "
            "registered WAVE ceilings were enforced fail-closed across both passes in-process. "
            "This file re-emits the wave artefact over all receipts because build_wave_summary "
            "sees only the outcomes of the process that wrote it, and --resume skips are not "
            "outcomes."
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
