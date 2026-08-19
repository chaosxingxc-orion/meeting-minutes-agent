#!/usr/bin/env python3
"""Token-COUNT profile of the PATH2 sink (structural throughput diagnosis).

Reads ONLY numeric usage fields and identifiers from the response sink --
never the reply text. Purpose: identify which contact kind produced the
~10-minute single-decode stall observed in the progress watcher, to size
the floors campaign's chunks safely. Counts only; no content, no scoring.
"""
import json
from pathlib import Path

SINK = Path("/mnt/e/chao_workspace/exploring-l4-intelligence/speechrl-data/derived/meeting-minutes/g1/runs/2026-08-19-g1-path2/responses/chunk0000-responses.jsonl")

rows = []
for line in SINK.open(encoding="utf-8"):
    rec = json.loads(line)
    usage = rec.get("usage") or {}
    rows.append((
        rec.get("meeting_id"), rec.get("arm"), rec.get("kind"),
        int(usage.get("completion_tokens") or 0),
        int(usage.get("prompt_tokens") or 0),
        rec.get("max_tokens"),
    ))

rows.sort(key=lambda r: -r[3])
print("top 12 by completion_tokens (counts only):")
for r in rows[:12]:
    print("  %-9s %-9s %-10s completion=%6d prompt=%6d max_tokens=%s" % r)
print()
by_kind = {}
for r in rows:
    by_kind.setdefault(r[2], []).append(r[3])
for kind, vals in sorted(by_kind.items()):
    vals.sort()
    print("kind=%-10s n=%3d completion tokens min=%d median=%d max=%d" %
          (kind, len(vals), vals[0], vals[len(vals)//2], vals[-1]))
