#!/usr/bin/env python3
"""Count retried contacts in the FLOORS sinks so far (identifiers/counts only,
never reply text): records whose succeeding response_request_id differs from
the planned request_id (the transport's derived -rN retry ids)."""
import json
import sys
from pathlib import Path

RESP = Path("/mnt/e/chao_workspace/exploring-l4-intelligence/speechrl-data/derived/meeting-minutes/g1/runs/2026-08-19-g1-floors/responses")

total = 0
retried = []
for sink in sorted(RESP.glob("chunk*-responses.jsonl")):
    n = 0
    for line in sink.open(encoding="utf-8"):
        rec = json.loads(line)
        total += 1
        if rec.get("request_id") != rec.get("response_request_id"):
            n += 1
            retried.append((sink.name, rec.get("meeting_id"), rec.get("arm"), rec.get("kind"),
                            rec.get("response_request_id")))
    print(f"{sink.name}: retried this sink = {n}")
print("total records:", total, " total retried:", len(retried))
for r in retried:
    print("  RETRIED %-28s %-9s %-9s %-10s -> %s" % r)
