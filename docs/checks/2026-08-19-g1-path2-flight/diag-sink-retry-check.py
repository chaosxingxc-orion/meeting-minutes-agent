#!/usr/bin/env python3
"""Count retried contacts in the PATH2 sink: records whose succeeding
response_request_id differs from the planned request_id (the transport's
derived -rN retry ids). Identifiers and counts only -- no reply text."""
import json
from pathlib import Path

SINK = Path("/mnt/e/chao_workspace/exploring-l4-intelligence/speechrl-data/derived/meeting-minutes/g1/runs/2026-08-19-g1-path2/responses/chunk0000-responses.jsonl")

n = 0
for line in SINK.open(encoding="utf-8"):
    rec = json.loads(line)
    rid, rrid = rec.get("request_id"), rec.get("response_request_id")
    if rid != rrid:
        n += 1
        print("RETRIED: %-9s %-9s %-10s request_id=%s response_request_id=%s"
              % (rec.get("meeting_id"), rec.get("arm"), rec.get("kind"), rid, rrid))
print("retried contacts:", n)
