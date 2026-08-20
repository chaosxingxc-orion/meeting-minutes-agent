#!/usr/bin/env python3
"""Rebuild the WAVE-2 summary over every per-meeting receipt of the night batch.

Wave-2 runs as a sequence of short `scripts/run_precomp.py --wave 2 --resume
--stop-file ...` invocations (the ~60 min harness reap makes one long invocation
unsafe). Each invocation's in-process `PrecompBudget` is already wave-cumulative
-- it is pre-charged natively from every receipt on disk (`PrecompBudget.precharge`
/ `run_precomp.load_wave_receipts`, commit e4e18c4) before its loop starts -- so
the registered WAVE ceilings hold across all of them fail-closed. What each
invocation's own `wave-summary.json` cannot carry is the OUTCOME list for the
meetings it skipped via `--resume` (`build_wave_summary` sees only that process's
outcomes). This re-emits the registered wave artefact over the WHOLE receipt set
using the machinery's own `build_wave_summary` / `write_wave_summary` -- never a
hand-rolled shape.

Same contract as `docs/checks/2026-08-19-precomp-wave1/aggregate_resume.py`; only
the wave number and the accounting note differ.
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
    n_invocations = sys.argv[4] if len(sys.argv) > 4 else "?"

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
            "wave-cumulative over every per-meeting receipt of PRECOMP wave-2, produced by "
            f"{n_invocations} short run_precomp.py invocations (the ~60 min harness reap makes one "
            "long invocation unsafe; each invocation started its own llama-server as a child, ran "
            "--wave 2 --resume --stop-file, and tore the server down). Every invocation's "
            "PrecompBudget was pre-charged natively from the receipts already on disk "
            "(PrecompBudget.precharge / load_wave_receipts, commit e4e18c4), so the registered "
            "WAVE ceilings were enforced fail-closed across the whole batch in-process, and an "
            "operator-side budget_ledger.py cross-check ran after every invocation. This file "
            "re-emits the wave artefact over ALL receipts because build_wave_summary sees only "
            "the outcomes of the process that wrote it, and --resume skips are not outcomes."
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
