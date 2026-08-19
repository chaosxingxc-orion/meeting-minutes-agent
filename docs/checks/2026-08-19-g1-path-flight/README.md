# G1-PATH pathfinder — FLOWN 2026-08-19 — **STRUCTURAL NOT-PASS**

> **Verdict: NOT-PASS.** Every part of the campaign runner that this flight exercised end-to-end
> passed structurally — 8/8 (meeting, arm) work items, all four arms, all three heads, budget
> adhered, receipts reconciled, no orphan server. **One structural defect blocks the floors
> campaign and is the reason for NOT-PASS: `scripts/run_g1.py::run_item` dispatches the WHOLE
> capped QA question set to EVERY (meeting, arm), instead of the questions attached to that
> meeting.** The defect was proven at PLANNING time, at zero call cost, and no repair was
> attempted here.

**This record renders no metric and no result verdict.** G1-PATH is structural only
(`docs/readiness/2026-08-19-g1-floors-preregistration.md` §5: "validates plumbing, budgets,
receipts, and the per-slice dispatch chain. Structural pass/fail only; NO metric conclusions").
Nothing here is scored, no reply text is quoted or summarised anywhere in this directory, no arm
is compared to another, and no reference transcript was consulted. The G1 read is a separately
gated mission.

Registration: `docs/readiness/2026-08-19-g1-floors-preregistration.md` (REGISTERED, owner GO
2026-08-19). Machinery flown: commit `38fce4ecb5fd06b5624d0a38e8df8e611c473af8`, **unmodified**,
clean tree throughout.

---

## 1. The structural finding (the NOT-PASS)

`run_item` builds a meeting's QA requests with

```python
qa_specs = g1.build_qa_requests_for_meeting(item.arm, item.meeting_id, plan, qa_questions, ...)
```

where `qa_questions` is the campaign-wide capped set — every one of the 200 questions selected by
`select_capped_qa_questions` over all 489 dev-18 usable-discovery questions. It is never filtered
to the questions attached to `item.meeting_id`. `build_qa_requests_for_meeting` then anchors all
of them on that meeting's own first slice, so a question about `IB4010` is asked of `ES2011a`'s
audio.

Consequences, measured with `run_g1.py --list-chunks` at the registered cap (`preflight.log`,
`chunkplan-registered-cap.json` — CPU-only, zero model contact, zero calls spent):

| | planned QA calls | planned total calls |
|---|---|---|
| **G1-PATH as the runner plans it** (2 meetings × 2 QA arms × 200) | **800** | **892** in 2 chunks |
| registered PATH size (prereg §5) | — | **~250 requests, ≤0.5 GPU-h** |
| **floors as the runner would plan it** (18 × 2 × 200) | **7,200** | — |
| registered floors arithmetic (prereg §6) | **≈400** = 200 questions × 2 arms | ≈2,100, ceiling ≤2,900 |

Two independent failures follow. **Semantically**, 193 of the 200 questions are not attached to
either PATH meeting (only 7 are: `ES2011a` 7, `IS1008a` 0), so the overwhelming majority of QA
contacts would ask a meeting about a different meeting. **Budget-wise**, the floors campaign's QA
head alone would need 7,200 calls against a registered ≤2,900-call campaign ceiling, so
`G1Budget` would fire `G1BudgetExceeded` partway through and the campaign could not complete as
registered.

The registered design is unambiguous (prereg §2: "the usable-discovery questions attached to
dev-18, seeded cap N=200"; §6: "QA ≈400"): each capped question is asked once per QA-bearing arm,
on its own meeting. Note also that `IS1008a` carries zero capped questions, so a correct
per-meeting implementation must handle an empty question set for a meeting —
`build_qa_requests_for_meeting` currently raises `G1Error` on an empty list, and `run_item`'s
`if qa_questions:` guard is campaign-wide, not per meeting.

**No repair was attempted.** Per the flight's own instruction, the failure is landed as evidence
with a diagnosis and nothing beyond receipts was changed.

## 2. What was flown, and why it was bounded

Flying PATH as the runner plans it would have cost 892 calls against a registered ~250-request
pathfinder — a 3.6× overrun of the registered envelope — and written 800 semantically invalid QA
contacts. That is not an operator's call to make, so PATH was flown at its registered size with
the QA head reduced to a **machinery-probe cap of 3 questions per (meeting, arm)**. The runner
prints its own warning for a non-registered cap —

> `WARNING: --qa-cap/--qa-seed override the registered N=200/seed=20260818 (floors prereg SS2) --
> only for machinery testing, never for a registered flight`

— which is exactly this invocation's status: structural machinery testing whose replies are never
scored. This buys full dispatch-chain coverage of the QA head for 12 calls while staying inside
the registered envelope. The flight's own ceilings were additionally tightened to PATH's
registered size and enforced fail-closed: **≤250 calls / ≤0.5 GPU-h / ≤2 h wall**, instead of the
whole campaign's 2,900 / 6.0 / 8.0 — a pathfinder must not be able to spend the floors campaign's
ceiling.

Flight plan (`chunkplan-flight.json`): **104 calls, 8 work items, 1 chunk**.

## 3. Identity (hash-verified preflight, `preflight.log`)

| item | value | check |
|---|---|---|
| llama-server | `/home/chao/llama.cpp-featcache/build/bin/llama-server`, sha256 `097c96ec…c68` | **OK vs pin** |
| llama.cpp build | commit `5d9dfcb58ea860295da8fc93c7b5bed9e2c71151`, clean tree | **OK vs pin** |
| core GGUF | `Qwen3-Omni-30B-A3B-Instruct-Q4_K_M.gguf`, sha256 `0751c279…66d` | **OK vs pin** |
| mmproj GGUF | `mmproj-Qwen3-Omni-30B-A3B-Instruct-bf16.gguf`, sha256 `f0dfe825…883` | **OK vs pin** |
| feature cache | `/home/chao/feat-cache/ami-q4km`, 14,324 entries at takeoff | never `q4km` / `slurp-q4km` / `audio2tool-q4km` |

Server argv unchanged from every prior flight: `--host 127.0.0.1 --port 8080 -m <core>
--mmproj <mmproj> -c 49152 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0`. Full identity in
`runtime-identity.json`.

**Server ownership**: the `llama-server` was started and torn down by
`g1_campaign.ManagedLlamaServer` as a **direct child of the `run_g1.py` chunk invocation**, so
server and work shared one harness window. The whole invocation took 429 s, far inside the
60-minute reap. No orphan `llama-server` survived the chunk.

## 4. Preflight — all four arms resolve from cache, zero model contact

`--list-chunks` and the arm/plan cross-check rebuild every (meeting, arm) slice plan from
PRECOMP's on-disk cache. All eight resolved, with **every cached slice WAV present**:

| meeting | arm | plan mode | turn provenance | slices | slice dir | missing WAVs |
|---|---|---|---|---|---|---|
| ES2011a | Z-turn | turn_aware | tool-diar | 12 | `…/slices/tool` | none |
| ES2011a | Z-oracle | turn_aware | oracle-turn | 12 | `…/slices/oracle` | none |
| ES2011a | Z-free | turn_aware | tool-diar | 12 | `…/slices/tool` | none |
| ES2011a | Z-nodiar | **vad** | **none** | 13 | `…/slices/vad` | none |
| IS1008a | Z-turn | turn_aware | tool-diar | 9 | `…/slices/tool` | none |
| IS1008a | Z-oracle | turn_aware | oracle-turn | 10 | `…/slices/oracle` | none |
| IS1008a | Z-free | turn_aware | tool-diar | 9 | `…/slices/tool` | none |
| IS1008a | Z-nodiar | **vad** | **none** | 11 | `…/slices/vad` | none |

Z-nodiar loaded its `SlicePlan` from the VAD supplement landed the same day
(`docs/checks/2026-08-19-g1-supplement/`, commit `38fce4e`) — the fail-closed
`G1VadSupplementMissingError` path was never taken, and the arm's declared `mode=vad` /
`turn_provenance=None` contract held.

## 5. Completion per (meeting, arm, head) — `structural-report.txt`

| meeting | arm | receipt | ok | n_calls | transcribe | minutes | qa | wall s |
|---|---|---|---|---|---|---|---|---|
| ES2011a | Z-turn | yes | yes | 16 | 12 | 1 | 3 | 70.6 |
| ES2011a | Z-oracle | yes | yes | 16 | 12 | 1 | 3 | 68.5 |
| ES2011a | Z-free | yes | yes | 12 | 12 | 0 | 0 | 40.3 |
| ES2011a | Z-nodiar | yes | yes | 13 | 13 | 0 | 0 | 42.3 |
| IS1008a | Z-turn | yes | yes | 13 | 9 | 1 | 3 | 63.6 |
| IS1008a | Z-oracle | yes | yes | 14 | 10 | 1 | 3 | 62.2 |
| IS1008a | Z-free | yes | yes | 9 | 9 | 0 | 0 | 31.0 |
| IS1008a | Z-nodiar | yes | yes | 11 | 11 | 0 | 0 | 29.5 |
| **total** | — | **8/8** | **8/8** | **104** | **88** | **4** | **12** | **408.0** |

`items ok=8 error=0 missing=0`. Every arm's transcribe-call count equals its own rebuilt plan's
slice count. **Head-set conformance vs the registered arm table: PASS** — minutes and qa appear on
exactly Z-turn and Z-oracle, and on neither transcribe-only arm.

## 6. Budget adherence — `chunks/chunk0000-receipt.json`

| axis | used | this flight's ceiling | breach |
|---|---|---|---|
| calls | 104 | 250 | none |
| wall seconds | 408.0 | 7,200 | none |
| GPU seconds | 0.0 (never sampled by this runner) | 1,800 | none |

`n_items=8, n_ok=8, n_error=0, stopped_reason=null`. `G1BudgetExceeded` never fired. Note that
`run_item` records `gpu_seconds=0.0` unconditionally, so the campaign's GPU-hour ceiling is
structurally inert on this runner — recorded here as an observation for the floors campaign, not
as a defect of this flight.

## 7. Dispatch-chain health (plumbing flags, not scores)

104 sink records against 104 receipted calls — **MATCH**. **0 duplicate request IDs. 0 empty
replies. 0 replies at `max_tokens`** (prereg §4's capped-reply disclosure: none).

The attribution arms' replies were re-parsed with the same
`parse_transcribe_attribute_response` call `run_item` itself makes to feed the minutes head:

| meeting | arm | replies parsing to ≥1 segment | parse-failed |
|---|---|---|---|
| ES2011a | Z-turn | 12 / 12 | 0 |
| ES2011a | Z-oracle | 12 / 12 | 0 |
| IS1008a | Z-turn | 9 / 9 | 0 |
| IS1008a | Z-oracle | 10 / 10 | 0 |

**43 of 43 — parse-chain health PASS.** The transcribe-only arms (Z-free, Z-nodiar) use
`build_transcribe_only_request`, whose head carries no attribution grammar and whose replies
`run_item` never parses; they are reported by presence only, and all 45 were non-empty. Segment
counts exist in `structural-report.txt` as integers only. No score, no reference, no comparison.

## 8. What PASSES structurally

Everything this flight touched except QA question routing:

- resumable (meeting, arm) work items, receipts (schema `1.0.0`), and chunk receipts, all fsynced;
- deterministic slice-plan rebuilding from PRECOMP's cache for all four arms, including the
  Z-nodiar VAD-manifest path and its fail-closed contract;
- the per-slice transcribe dispatch chain, on every arm;
- the minutes head, including the transcribe→segments→minutes hand-off on both QA-bearing arms;
- the QA head's own dispatch chain (request build → transport → sink → receipt), at probe scale;
- the T1-A1 locked prompt form, applied by construction (`build_transcribe_request_for_arm`);
- fail-closed budget guarding and chunk planning;
- reap-safe server ownership as a child of the chunk invocation, with clean teardown.

## 9. Discipline

- Only `ES2011a` and `IS1008a` were contacted; eval-16 and held-out-reserve meetings were never
  named or touched.
- **No gold text entered any prompt path.** Oracle NXT turns fed the slicer only, via the plan
  PRECOMP already built; the NXT reference is scoring-side and no scoring ran.
- The per-contact response sink is a **raw trace** and stays on the data root at
  `$SPEECHRL_DATA_DIR/derived/meeting-minutes/g1/runs/2026-08-19-g1-path/responses/`
  (`chunk0000-responses.jsonl`, 104 lines, 161,421 B, sha256 `7d0b9fc7…5173`). Git carries its
  hash and line count only. That directory is what `scripts/g1_read.py --responses-dir` must be
  pointed at when the read is gated.
- Archived receipts were machine-checked to carry no reply text.
- The machinery (`scripts/run_g1.py`, `src/meeting_minutes_agent/probes/g1*.py`) was **not
  modified**.
- GPU ran under the same platform SW power cap as prior flights: with the SM clock floor
  `-lgc 1200,2500` applied, 11 of 14 samples sat at 1,200 MHz and three dipped (652 / 907 /
  1,140 MHz), power 15.22–83.47 W (`gpu-health-chunk0.log`). Throughput was ~3.9 s per contact
  (408.0 s over 104 calls), close to the registered 3.7 s/request planning basis.

## 10. Files

- `structural-report.txt` — the full structural validation output (the authority for §5–§7).
- `receipts/<meeting>-<arm>-receipt.json` — the eight text-free per-item receipts.
- `chunks/chunk0000-receipt.json` — the chunk receipt with `budget_after`.
- `chunkplan-registered-cap.json` — the 892-call plan at the registered N=200 cap (**the
  NOT-PASS evidence**).
- `chunkplan-flight.json` — the 104-call plan this flight ran.
- `runtime-identity.json` — binaries, GGUFs, server argv, ceilings, sink hash.
- `preflight.log`, `fly-chunk0-wrapper.log`, `progress-chunk0.log`, `gpu-health-chunk0.log`,
  `runner-chunk0.log` — the flight's logs.
- `response-sinks.sha256`, `response-sink-counts.txt` — hash and line count standing in for the
  raw trace that stays on the data root.
- `script-*.sh`, `structural.py` — every operator script that drove the flight, archived verbatim.
- `MANIFEST.sha256` — sha256 of every file in this directory.
