#!/usr/bin/env python3
"""Descriptive numbers for the wave-2 receipt README (this pass renders no verdicts).

Emits: the per-invocation batch table (which meetings each invocation completed, its
encode calls and walls, taken from the archived progress logs' receipt ordering), the
wave totals against the registered wave-2 ceilings, and the boundary-displacement /
slice-count-delta distributions the registration asks for (prereg SS5).
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, os.environ["REPO"] + "/src")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from budget_ledger import load_receipts, totals  # noqa: E402

from meeting_minutes_agent.precomp.budget import ceilings_for_wave  # noqa: E402


def invocation_batches(logs: Path) -> list[dict]:
    """Which meetings each invocation completed, read back from its own progress log's
    'meetings completed by THIS invocation' block (the wrapper wrote it at teardown)."""
    out = []
    for prog in sorted(logs.glob("progress-*.log"), key=lambda p: int(re.findall(r"\d+", p.name)[0])):
        n = int(re.findall(r"\d+", prog.name)[0])
        text = prog.read_text(encoding="utf-8", errors="replace")
        meetings = re.findall(r"^\s{2}(\S+)\s+ok=(\S+)\s+calls=(\S+)\s+enc_wall=([\d.]+)s\s+diar_wall=([\d.]+)s",
                              text, re.M)
        # fly2.sh's FLY-DONE carries an extra ` refused=<n>` field that fly.sh's does not.
        done = re.search(r"FLY-DONE state=(\S+) remaining=(\S+)(?: refused=(\S+))? wall=(\d+)s", text)
        srv = re.search(r"server healthy after (\d+) s", text)
        run = re.search(r"runner rc=(\S+) wall=(\d+)s", text)
        out.append({
            "invocation": n,
            "meetings": [m[0] for m in meetings],
            "n_meetings": len(meetings),
            "calls": sum(int(m[2]) for m in meetings if m[2].isdigit()),
            "encode_wall_s": sum(float(m[3]) for m in meetings),
            "diar_wall_s": sum(float(m[4]) for m in meetings),
            "all_ok": all(m[1] == "True" for m in meetings),
            "state": done.group(1) if done else "NO-FLY-DONE",
            "remaining_after": done.group(2) if done else "?",
            "wrapper_wall_s": int(done.group(4)) if done else None,
            "server_start_s": int(srv.group(1)) if srv else None,
            "runner_rc": run.group(1) if run else None,
            "runner_wall_s": int(run.group(2)) if run else None,
        })
    return out


def main() -> int:
    out_dir = Path(sys.argv[1])
    logs = Path(sys.argv[2])
    receipts = load_receipts(out_dir)
    used = totals(receipts)
    ceil = ceilings_for_wave(2)

    batches = invocation_batches(logs)
    print("## Per-invocation batch table\n")
    print("| inv | meetings | n | encode calls | server start s | runner wall s | wrapper wall s | state | remaining after |")
    print("|---|---|---|---|---|---|---|---|---|")
    for b in batches:
        print("| %d | %s | %d | %d | %s | %s | %s | %s | %s |" % (
            b["invocation"], " ".join(b["meetings"]) or "-", b["n_meetings"], b["calls"],
            b["server_start_s"], b["runner_wall_s"], b["wrapper_wall_s"], b["state"], b["remaining_after"]))

    print("\n## Wave totals vs registered ceilings\n")
    rows = [
        ("encode calls", used["encode_calls_used"], ceil.max_encode_calls, ""),
        ("encode GPU-h", used["encode_gpu_seconds_used"] / 3600.0, ceil.max_encode_gpu_hours, ""),
        ("diar GPU-h", used["diar_gpu_seconds_used"] / 3600.0, ceil.max_diar_gpu_hours, ""),
        ("CPU cutting wall-h", used["cutting_wall_seconds_used"] / 3600.0,
         ceil.max_cutting_wall_hours, "(wave-2 registers no ceiling on this axis)"),
    ]
    print("| axis | used | ceiling | headroom |")
    print("|---|---|---|---|")
    for name, u, c, note in rows:
        if c is None:
            print("| %s | %.3f | none %s | n/a |" % (name, u, note))
        else:
            pct = 100.0 * u / c if c else 0.0
            print("| %s | %s | %s | %.1f%% used |" % (
                name, ("%.0f" % u) if name == "encode calls" else ("%.3f" % u), c, pct))

    print("\nwall clock: diar %.1f s, encode %.1f s, cutting %.1f s" % (
        used["diar_wall_seconds"], used["encode_wall_seconds"], used["cutting_wall_seconds_used"]))
    print("receipts: %d (ok %d)" % (used["n_receipts"], used["n_ok"]))

    print("\n## Descriptive distributions (prereg SS5)\n")
    deltas, meds, maxes, tool_s, orc_s, tool_t, orc_t = [], [], [], 0, 0, 0, 0
    cache_entries = cache_bytes = 0
    for r in receipts:
        m = r.get("metrics") or {}
        sc = m.get("slice_counts") or {}
        bd = m.get("boundary_displacement") or {}
        cd = (m.get("cache") or {}).get("delta") or {}
        tc = m.get("turn_counts") or {}
        if isinstance(sc.get("delta"), int):
            deltas.append(sc["delta"])
        tool_s += int(sc.get("tool_slices") or 0); orc_s += int(sc.get("oracle_slices") or 0)
        tool_t += int(tc.get("tool_turns") or 0); orc_t += int(tc.get("oracle_turns") or 0)
        if isinstance(bd.get("median_s"), (int, float)):
            meds.append(float(bd["median_s"]))
        if isinstance(bd.get("max_s"), (int, float)):
            maxes.append(float(bd["max_s"]))
        cache_entries += int(cd.get("entries_added") or 0)
        cache_bytes += int(cd.get("bytes_added") or 0)
    def q(xs):
        if not xs:
            return "-"
        xs = sorted(xs)
        return "min %.1f / med %.1f / max %.1f" % (xs[0], statistics.median(xs), xs[-1])
    print("- turns: tool %d, oracle %d" % (tool_t, orc_t))
    print("- slices: tool %d, oracle %d (sum of per-meeting deltas %d; per-meeting delta %s)" % (
        tool_s, orc_s, sum(deltas), q([float(d) for d in deltas]) if deltas else "-"))
    print("- boundary displacement, per-meeting medians: %s" % q(meds))
    print("- boundary displacement, per-meeting maxima:  %s" % q(maxes))
    print("- feature cache added by wave-2: %d entries / %d bytes (%.2f GiB)" % (
        cache_entries, cache_bytes, cache_bytes / (1 << 30)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
