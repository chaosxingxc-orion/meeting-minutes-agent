# G1-PATH2 pathfinder re-run — FLOWN 2026-08-19 — **STRUCTURAL PASS**

> **Verdict: PASS.** This is the structural re-validation of the G1-PATH NOT-PASS repair
> (commit `8aedcb9443bf59edecf18679a972b4969f390e02`, "fix(g1): per-meeting QA routing + real gpu
> accounting"), flown at the **registered N=200/seed=20260818 QA cap with no override**. Both
> halves of the fix verified live: (1) QA calls route per meeting — ES2011a received exactly its
> own 7 capped questions on each QA-bearing arm (14 QA calls) and IS1008a, which the registered
> cap draws zero questions for, dispatched **zero** QA calls while still completing its
> transcribe+minutes heads; (2) `gpu_seconds` is real — every receipt carries a nonzero value,
> 991.9 s total, and the GPU-hour ceiling now binds on real spend. 8/8 (meeting, arm) items ok,
> 106/106 sink↔receipt reconciliation, plan conformance exact on every (meeting, arm, head),
> parse-chain 43/43, budget adhered with zero breaches. **The floors campaign is cleared to fly.**

**This record renders no metric and no result verdict.** G1-PATH is structural only
(`docs/readiness/2026-08-19-g1-floors-preregistration.md` §5). Nothing here is scored, no reply
text is quoted or summarised anywhere in this directory, no arm is compared to another, and no
reference transcript was consulted. The G1 read is a separately gated mission.

Registration: `docs/readiness/2026-08-19-g1-floors-preregistration.md` §5 (REGISTERED, owner GO
2026-08-19). Machinery flown: commit `8aedcb9443bf59edecf18679a972b4969f390e02` (the repair
commit itself), **unmodified**, clean tree throughout. Prior evidence: the NOT-PASS record in
`docs/checks/2026-08-19-g1-path-flight/`.

---

## 1. Preflight (all green before first model contact)

- **pytest at 8aedcb9**: `1512 passed, 6 skipped` in 45.6 s, rc=0, tree still clean
  (`pytest-preflight.log`) — exactly the repair commit's own recorded suite state.
- **Hash pins** (`preflight.log`): llama-server sha256 `097c96ec…c68` OK; core GGUF
  `0751c279…66d` OK; mmproj `f0dfe825…883` OK; llama.cpp build commit
  `5d9dfcb58ea860295da8fc93c7b5bed9e2c71151`, clean tree — all identical to every prior G1 pass.
- **Planning-time fix verification** (CPU-only, zero model contact): the registered-cap plan is
  now **106 calls in 1 chunk** (est 392.2 s) — vs the 892-call/2-chunk plan the same flags
  produced at `38fce4e` (the NOT-PASS evidence). Per-meeting routing over the capped 200:
  ES2011a 7, IS1008a 0; floors-scale QA total 400 = 200 × 2 arms.
- All 8 (meeting, arm) slice plans rebuilt from PRECOMP cache, every cached slice WAV present,
  Z-nodiar via the VAD supplement manifest (fail-closed path never taken).

## 2. Identity and ownership

Same pinned identity as G1-PATH (`runtime-identity.json`): server argv unchanged
(`-c 49152 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0`), server started and torn down by
`g1_campaign.ManagedLlamaServer` as a **direct child of the single `run_g1.py --run-chunk 0`
invocation** (1,046 s total, far inside the 60-minute reap), no orphan `llama-server` after.
Flight ceilings enforced fail-closed at PATH's own envelope: **≤250 calls / ≤0.5 GPU-h /
≤2 h wall** — never the floors campaign's. Fresh run dir
(`…/g1/runs/2026-08-19-g1-path2/`): the first PATH flight's receipts could not satisfy
`--resume`.

## 3. Completion and plan conformance — `structural-report.txt`

| meeting | arm | ok | n_calls | transcribe | minutes | qa | gpu s | wall s |
|---|---|---|---|---|---|---|---|---|
| ES2011a | Z-turn | yes | 20 | 12 | 1 | **7** | 71.6 | 72.1 |
| ES2011a | Z-oracle | yes | 20 | 12 | 1 | **7** | 75.2 | 75.8 |
| ES2011a | Z-free | yes | 12 | 12 | 0 | 0 | 41.9 | 42.1 |
| ES2011a | Z-nodiar | yes | 13 | 13 | 0 | 0 | 35.8 | 36.2 |
| IS1008a | Z-turn | yes | 10 | 9 | 1 | **0** | 53.1 | 53.4 |
| IS1008a | Z-oracle | yes | 11 | 10 | 1 | **0** | 656.7 | 657.3 |
| IS1008a | Z-free | yes | 9 | 9 | 0 | 0 | 29.1 | 29.3 |
| IS1008a | Z-nodiar | yes | 11 | 11 | 0 | 0 | 28.6 | 28.9 |
| **total** | — | **8/8** | **106** | 88 | 4 | **14** | 991.9 | 995.1 |

Every (meeting, arm, head) contact count equals the chunk plan's own
`n_transcribe`/`n_minutes`/`n_qa` **exactly** (plan conformance PASS) — including IS1008a's two
zero-QA items, the empty-question-set tolerance the fix added. The QA-routing defect is
repaired in flight, not just at planning time.

## 4. Real GPU accounting (fix half 2)

Every ok receipt carries nonzero `gpu_seconds` (PASS); chunk `budget_after` records
`gpu 991.9 s / 1,800 s` — the GPU-hour ceiling is no longer structurally inert. Budget:
calls 106/250, wall 995.1 s/7,200 s, zero breaches, `stopped_reason=null`.

## 5. Dispatch-chain health

106 sink records vs 106 receipted calls — **MATCH**. 0 duplicate request ids, 0 empty replies,
0 replies at `max_tokens` (prereg §4 capped-reply disclosure: none). Attribution arms: 43/43
transcribe replies parse to ≥1 segment with the exact parser `run_item` feeds the minutes head
(parse-chain PASS); transcribe-only arms: 45/45 non-empty (presence only, never parsed).

## 6. Throughput observation (structural, feeds floors chunk sizing)

One contact — `g1-Z-oracle-IS1008a-transcribe-slice0008` — consumed ~600 s on its first attempt
(the transport's per-attempt timeout at this flight's `--timeout-seconds 600`), then its
**bounded retry succeeded** as `…-r1` (`diag-sink-retry-check.py`: 1 retried contact of 106).
GPU stayed 91–97 % busy at normal clocks throughout the stall (`gpu-health-chunk0.log` — not the
232 MHz clock-stick failure mode), and no reply in the sink exceeds 790 completion tokens
(`diag-sink-usage-counts.py`, counts only): i.e. one degenerate unbounded generation
(`max_tokens=None`) burned the timeout window and was cleanly retried. Receipts, budget, and
sink all held — this is the retry machinery working as designed. Consequence carried into the
floors flight: per-attempt timeout 300 s (the `TransportConfig` default) and 1,800 s estimated
chunk cap, so a stall-bearing chunk still lands well inside the 60-minute reap window.
Excluding that single stall, throughput was ~3.7 s/contact, on the registered planning basis.

## 7. Discipline

- Only `ES2011a` and `IS1008a` contacted; eval-16 and reserved meetings never named or touched.
- **No gold text entered any prompt path**; oracle NXT turns fed the slicer only; no scoring ran.
- Feature cache fully warm: **0 encode lines** in `server.log`; `ami-q4km` entries 14,324
  before → 14,324 after, bytes unchanged (never `q4km`/`slurp-q4km`/`audio2tool-q4km`).
- The response sink is a raw trace and stays on the data root:
  `$SPEECHRL_DATA_DIR/derived/meeting-minutes/g1/runs/2026-08-19-g1-path2/responses/chunk0000-responses.jsonl`,
  106 lines, 161,925 B, sha256 `3959de4d…6d7d`. Git carries hash and counts only.
- Archived receipts machine-checked to carry no reply text. Machinery not modified.

## 8. Files

- `structural-report.txt` — the authority for §3–§5 (plan-conformance + gpu-accounting checks).
- `chunkplan-flight.json` — the 106-call registered-cap plan (the fix's planning-time evidence).
- `receipts/`, `chunks/` — text-free per-item and per-chunk receipts.
- `runtime-identity.json`, `preflight.log`, `pytest-preflight.log`, flight logs, `script-*.sh`,
  `structural.py`, `diag-sink-*.py` (count-only diagnostics), `response-sinks.sha256`,
  `response-sink-counts.txt`, `MANIFEST.sha256`.
