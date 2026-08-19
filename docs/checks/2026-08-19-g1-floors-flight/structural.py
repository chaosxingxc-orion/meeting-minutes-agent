#!/usr/bin/env python3
"""G1 STRUCTURAL validation (path2 / floors). Renders no metric and no result
verdict.

What this checks, and only this (structural counts, never scores):

1. completion per (meeting, arm): the item receipt exists, is schema-versioned,
   and records ok/error;
2. PLAN CONFORMANCE per (meeting, arm, HEAD): the per-contact log's own `kind`
   counts (transcribe / minutes / qa) against the CHUNK PLAN's own
   n_transcribe / n_minutes / n_qa for that exact item -- for the QA head this
   is the live verification of the 8aedcb9 per-meeting routing fix: a meeting
   may only be asked its OWN routed questions, and a zero-question meeting
   (IS1008a under the registered cap) must dispatch zero qa calls;
3. REAL GPU ACCOUNTING (the fix's second half): every ok receipt with >=1
   call must carry gpu_seconds > 0 (run_item used to record 0.0
   unconditionally), and the chunk receipts' budget_after.gpu_seconds_used
   must be nonzero and within the GPU-hour ceiling;
4. budget adherence: every chunk receipt's own `budget_after` against its own
   recorded fail-closed ceilings;
5. dispatch-chain health, per arm's OWN head: for the two ATTRIBUTION arms
   (Z-turn, Z-oracle) whether each transcribe reply parses, with the pinned
   `parse_transcribe_attribute_response`, into the >=1-segment shape the
   minutes head consumes downstream -- the exact call `run_item` itself makes
   in flight. The two TRANSCRIBE-ONLY arms (Z-free, Z-nodiar) carry NO
   attribution grammar and are reported by non-empty-reply count only.
   A PLUMBING flag throughout, never a grammar-compliance SCORE: no arm is
   compared to another, no reference is consulted, and no reply text is
   printed, hashed, or otherwise surfaced;
6. reply-cap disclosure: how many replies hit their own `max_tokens`
   (prereg SS4 "capped-reply counts disclosed per arm") -- a count, not a
   score;
7. request-id uniqueness and the sink/receipt call-count reconciliation.

Reply text is read ONLY by the parser, in-process, to produce integer counts.
Nothing derived from reply content leaves this script except those counts.

Usage: structural.py <out-dir> <chunkplan.json>
"""

from __future__ import annotations

import collections
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["REPO"] + "/src")

from meeting_minutes_agent.heads.transcribe_attribute import parse_transcribe_attribute_response  # noqa: E402
from meeting_minutes_agent.probes import g1, g1_campaign  # noqa: E402

HEADS = ("transcribe", "minutes", "qa")


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main() -> int:
    out_dir = Path(sys.argv[1])
    chunkplan_path = Path(sys.argv[2])

    print("=== G1 structural validation (no metric, no result read) ===")
    print("out-dir:", out_dir)
    print("chunk plan:", chunkplan_path)

    plan_doc = load_json(chunkplan_path)
    if plan_doc is None:
        print("FATAL: chunk plan unreadable")
        return 1
    expected = {}  # (meeting, arm) -> {n_transcribe, n_minutes, n_qa}
    for chunk in plan_doc["chunks"]:
        for it in chunk["items"]:
            expected[(it["meeting_id"], it["arm"])] = it
    print(f"planned items: {len(expected)}  planned calls: {sum(it['n_calls'] for it in expected.values())}"
          f"  planned qa calls: {sum(it['n_qa'] for it in expected.values())}")

    # ---- 1/2. per (meeting, arm) completion + per-head PLAN CONFORMANCE ----
    receipts = {}
    for (meeting, arm) in expected:
        path = g1_campaign.item_receipt_path(out_dir, meeting, arm)
        receipts[(meeting, arm)] = load_json(path) if path.is_file() else None

    print()
    print("| meeting | arm | receipt | ok | schema | n_calls | transcribe | minutes | qa | gpu s | wall s | error |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    n_items_ok = 0
    n_items_missing = 0
    n_items_error = 0
    conforms = True
    gpu_ok = True
    gpu_total = 0.0
    for (meeting, arm), r in sorted(receipts.items()):
        if r is None:
            n_items_missing += 1
            print(f"| {meeting} | {arm} | MISSING | - | - | - | - | - | - | - | - | - |")
            continue
        kinds = collections.Counter(c.get("kind") for c in (r.get("contacts") or []))
        ok = bool(r.get("ok"))
        n_items_ok += 1 if ok else 0
        n_items_error += 0 if ok else 1
        err = str(r.get("error"))[:120] if not ok else ""
        gpu_s = float(r.get("gpu_seconds") or 0.0)
        gpu_total += gpu_s
        if ok and int(r.get("n_calls") or 0) >= 1 and gpu_s <= 0.0:
            gpu_ok = False
            err = (err + " GPU-SECONDS-ZERO").strip()
        print(
            f"| {meeting} | {arm} | yes | {'yes' if ok else 'NO'} "
            f"| {r.get('schema_version')} | {r.get('n_calls')} "
            f"| {kinds.get('transcribe', 0)} | {kinds.get('minutes', 0)} | {kinds.get('qa', 0)} "
            f"| {gpu_s:.1f} | {float(r.get('wall_seconds') or 0.0):.1f} | {err} |"
        )
    print()
    print(f"items ok={n_items_ok} error={n_items_error} missing={n_items_missing} of {len(expected)} planned (meeting x arm)")
    print(f"gpu_seconds receipt total: {gpu_total:.1f}s  every-ok-item-nonzero: {'PASS' if gpu_ok else 'FAIL'}")

    print()
    print("--- per-head PLAN CONFORMANCE (incl. the per-meeting QA routing fix) ---")
    for (meeting, arm), r in sorted(receipts.items()):
        want = expected[(meeting, arm)]
        if r is None:
            conforms = False
            print(f"  {meeting:9s} {arm:9s} MISSING (wanted t={want['n_transcribe']} m={want['n_minutes']} q={want['n_qa']})")
            continue
        kinds = collections.Counter(c.get("kind") for c in (r.get("contacts") or []))
        problems = []
        for head, key in (("transcribe", "n_transcribe"), ("minutes", "n_minutes"), ("qa", "n_qa")):
            if kinds.get(head, 0) != want[key]:
                problems.append(f"{head}={kinds.get(head, 0)} want {want[key]}")
        status = "OK" if not problems else "PROBLEM: " + "; ".join(problems)
        if problems:
            conforms = False
        print(f"  {meeting:9s} {arm:9s} t={kinds.get('transcribe',0):3d}/{want['n_transcribe']:3d} "
              f"m={kinds.get('minutes',0)}/{want['n_minutes']} q={kinds.get('qa',0):3d}/{want['n_qa']:3d} {status}")
    print("plan conformance (per meeting, arm, head):", "PASS" if conforms else "FAIL")

    # ---- 4. budget adherence ----------------------------------------------
    print()
    print("--- budget adherence (chunk receipts) ---")
    chunk_dir = out_dir / "chunks"
    chunk_files = sorted(chunk_dir.glob("chunk*-receipt.json")) if chunk_dir.is_dir() else []
    budget_ok = True
    budget_gpu_nonzero = False
    for cf in chunk_files:
        c = load_json(cf)
        if c is None:
            print(f"  {cf.name}: UNREADABLE")
            budget_ok = False
            continue
        b = c.get("budget_after") or {}
        ceil = b.get("ceilings") or {}
        breach = []
        if int(b.get("calls_used") or 0) > int(ceil.get("max_calls") or 0):
            breach.append("calls")
        if float(b.get("wall_seconds_used") or 0.0) > float(ceil.get("max_wall_hours") or 0.0) * 3600.0:
            breach.append("wall")
        if float(b.get("gpu_seconds_used") or 0.0) > float(ceil.get("max_gpu_hours") or 0.0) * 3600.0:
            breach.append("gpu")
        if breach:
            budget_ok = False
        if float(b.get("gpu_seconds_used") or 0.0) > 0.0:
            budget_gpu_nonzero = True
        print(f"  {cf.name}: n_items={c.get('n_items')} n_ok={c.get('n_ok')} n_error={c.get('n_error')} "
              f"stopped_reason={c.get('stopped_reason')!r}")
        print(f"    calls {b.get('calls_used')}/{ceil.get('max_calls')}  "
              f"wall {float(b.get('wall_seconds_used') or 0.0):.1f}s/{float(ceil.get('max_wall_hours') or 0.0) * 3600.0:.0f}s  "
              f"gpu {float(b.get('gpu_seconds_used') or 0.0):.1f}s/{float(ceil.get('max_gpu_hours') or 0.0) * 3600.0:.0f}s  "
              f"breaches={breach or 'none'}")
    if not chunk_files:
        print("  (no chunk receipt on disk)")
        budget_ok = False
    print("budget adherence:", "PASS" if budget_ok else "FAIL")
    print("budget gpu_seconds_used nonzero:", "PASS" if budget_gpu_nonzero else "FAIL")

    # ---- 5/6/7. sink reconciliation + dispatch-chain parse health ---------
    print()
    print("--- response sink: reconciliation + dispatch-chain parse health ---")
    sinks = sorted((out_dir / "responses").glob("chunk*-responses.jsonl")) if (out_dir / "responses").is_dir() else []
    per_key = collections.Counter()
    parse_ok = collections.Counter()
    parse_fail = collections.Counter()
    seg_total = collections.Counter()
    nonempty_only = collections.Counter()
    empty_reply = collections.Counter()
    capped_reply = collections.Counter()
    request_ids = collections.Counter()
    total_records = 0
    for sp in sinks:
        with sp.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    print(f"  {sp.name}: UNPARSABLE JSONL line")
                    continue
                total_records += 1
                key = (rec.get("meeting_id"), rec.get("arm"), rec.get("kind"))
                per_key[key] += 1
                request_ids[rec.get("request_id")] += 1
                text = rec.get("text")
                if not text:
                    empty_reply[key] += 1
                usage = rec.get("usage") or {}
                max_tokens = rec.get("max_tokens")
                completion = usage.get("completion_tokens", usage.get("completion"))
                if isinstance(max_tokens, int) and isinstance(completion, int) and completion >= max_tokens:
                    capped_reply[key] += 1
                if rec.get("kind") != "transcribe":
                    continue
                arm = rec.get("arm")
                k = (rec.get("meeting_id"), arm)
                if arm not in g1.ARMS_WITH_ATTRIBUTION:
                    # Transcribe-ONLY head: no attribution grammar, and run_item
                    # never parses these replies. Reported by presence only.
                    if text:
                        nonempty_only[k] += 1
                    continue
                try:
                    parsed = parse_transcribe_attribute_response(text or "")
                    n_seg = len(parsed.segments)
                except Exception:
                    parse_fail[k] += 1
                    continue
                if n_seg >= 1:
                    parse_ok[k] += 1
                    seg_total[k] += n_seg
                else:
                    parse_fail[k] += 1
    print(f"  sink files: {[p.name for p in sinks]}  records: {total_records}")
    dupes = [rid for rid, n in request_ids.items() if n > 1]
    print(f"  duplicate request_ids: {len(dupes)}" + (f" e.g. {dupes[:3]}" if dupes else ""))
    print()
    print("| meeting | arm | head | sink records | empty replies | replies at max_tokens |")
    print("|---|---|---|---|---|---|")
    for key in sorted(per_key, key=lambda k: (str(k[0]), str(k[1]), str(k[2]))):
        print(f"| {key[0]} | {key[1]} | {key[2]} | {per_key[key]} | {empty_reply.get(key, 0)} | {capped_reply.get(key, 0)} |")
    print()
    print(f"attribution arms {g1.ARMS_WITH_ATTRIBUTION} -- the parse run_item itself performs to feed the minutes head:")
    print("| meeting | arm | transcribe replies parsed >=1 segment | parse-failed | segments (count only) |")
    print("|---|---|---|---|---|")
    parse_chain_ok = True
    for k in sorted(set(list(parse_ok) + list(parse_fail)), key=lambda k: (str(k[0]), str(k[1]))):
        if parse_fail.get(k, 0):
            parse_chain_ok = False
        print(f"| {k[0]} | {k[1]} | {parse_ok.get(k, 0)} | {parse_fail.get(k, 0)} | {seg_total.get(k, 0)} |")
    print()
    print(f"transcribe-only arms {g1.ARMS_TRANSCRIBE_ONLY} -- no attribution grammar, never parsed in flight:")
    print("| meeting | arm | non-empty transcribe replies |")
    print("|---|---|---|")
    for k in sorted(nonempty_only, key=lambda k: (str(k[0]), str(k[1]))):
        print(f"| {k[0]} | {k[1]} | {nonempty_only[k]} |")
    print()
    print("(counts only -- no reply text is surfaced, no reference is consulted, no arm is compared)")
    print("parse-chain health:", "PASS" if parse_chain_ok else "FAIL")

    # ---- receipt/sink call reconciliation ---------------------------------
    receipt_calls = sum(int(r.get("n_calls") or 0) for r in receipts.values() if r)
    print()
    print(f"reconciliation: receipt n_calls total={receipt_calls}  sink records={total_records}  "
          f"{'MATCH' if receipt_calls == total_records else 'MISMATCH'}")

    verdict_inputs = {
        "items_ok": n_items_ok,
        "items_error": n_items_error,
        "items_missing": n_items_missing,
        "plan_conformance": conforms,
        "gpu_seconds_every_ok_item_nonzero": gpu_ok,
        "gpu_seconds_receipt_total": round(gpu_total, 1),
        "budget_adherence": budget_ok,
        "budget_gpu_nonzero": budget_gpu_nonzero,
        "sink_receipt_reconciled": receipt_calls == total_records,
        "duplicate_request_ids": len(dupes),
        "parse_chain_health": parse_chain_ok,
        "empty_replies": sum(empty_reply.values()),
        "replies_at_max_tokens": sum(capped_reply.values()),
    }
    print()
    print("STRUCTURAL-INPUTS " + json.dumps(verdict_inputs, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
