# G1 floors campaign — FLOWN 2026-08-19 — COMPLETE, no result read

> **The registered floors campaign is fully flown.** All **72 (meeting, arm) work items**
> (dev-18 × four arms) completed ok across **5 resumable chunks**, **1,932 flight calls** against
> the ≤2,900 ceiling, **2.55 GPU-h** against ≤6.0 (real per-attempt accounting, 8aedcb9),
> **2.64 h** cumulative work wall against ≤8. QA flew at the registered N=200/seed=20260818 cap,
> **routed per meeting** (400 QA calls = 200 × 2 arms, exactly as preregistered). Sink↔receipt
> reconciliation 1,932/1,932, plan conformance exact on every (meeting, arm, head), zero
> breaches, zero orphan servers, feature cache byte-identical before and after. **Nothing here
> is scored**: the read is a separately gated mission (`scripts/g1_read.py`).

**This record renders no metric and no result verdict.** No reply text is quoted or summarised
anywhere in this directory, no arm is compared to another, and no reference transcript was
consulted. Segment/token figures below are plumbing counts, never scores.

Registration: `docs/readiness/2026-08-19-g1-floors-preregistration.md` (REGISTERED, owner GO
2026-08-19). Gate sequence honored: G1-PATH (NOT-PASS, `docs/checks/2026-08-19-g1-path-flight/`)
→ repair `8aedcb9` → G1-PATH2 re-run (**PASS**, `docs/checks/2026-08-19-g1-path2-flight/`,
commit `9dd7aa0`) → this campaign. Machinery flown: the `8aedcb9` runner and probe modules,
**unmodified** (HEAD at `9dd7aa0` during flight — a docs-only delta over `8aedcb9`; tree clean
throughout). Preflight suite evidence: `1512 passed, 6 skipped` at `8aedcb9`
(`docs/checks/2026-08-19-g1-path2-flight/pytest-preflight.log`, same day, machinery unchanged
since).

## 1. What flew

Dev-18 (all 18 meetings; eval-16 and reserved untouched) × the four registered arms:

| arm | slices | heads flown |
|---|---|---|
| Z-turn (deployment) | cached tool-diar turn-aware 90 s | transcribe-attribute + minutes + qa |
| Z-oracle (ceiling) | cached oracle-NXT turn-aware 90 s | transcribe-attribute + minutes + qa |
| Z-free | same tool-turn slices, no turn metadata | transcribe only |
| Z-nodiar | pure-VAD 90 s (PRECOMP supplement manifests) | transcribe only |

Call inventory (receipts = plan, exact): **1,496 transcribe + 36 minutes + 400 qa = 1,932**.
Per-meeting QA routing (both QA arms combined): ES2011a 14, ES2011b 30, ES2011c 36, ES2011d 46,
IB4001 34, IB4002 40, IB4003 38, IB4010 90, IS1008b 18, IS1008d 16, TS3004b 38; the seven
meetings the cap drew no questions for (IB4004, IB4011, IS1008a, IS1008c, TS3004a, TS3004c,
TS3004d) dispatched **zero** QA calls while completing transcribe+minutes — the 8aedcb9
routing behaving under campaign load exactly as G1-PATH2 validated.

## 2. Chunks (resumable, server child-owned per chunk)

One `run_g1.py --run-chunk N --resume` invocation per chunk; the pinned llama-server started
and torn down by `ManagedLlamaServer` as a **direct child** of each invocation (60-minute
harness-reap rule); `--stop-file` checked before every item, and the operator checked it
between chunks (it never appeared; the campaign ran to completion, not to yield).

| chunk | items | calls | runner wall | cumulative calls | cumulative gpu s | cumulative work-wall s |
|---|---|---|---|---|---|---|
| 0 | 18/18 ok | 480 | 2,555 s (42.6 min) | 480 | 2,301.5 | 2,412.8 |
| 1 | 15/15 ok | 478 | 2,783 s (46.4 min) | 958 | 4,506.1 | 4,672.2 |
| 2 | 20/20 ok | 481 | 2,819 s (47.0 min) | 1,439 | 7,107.9 | 7,343.7 |
| 3 | 18/18 ok | 462 | 2,773 s (46.2 min) | 1,901 | 9,078.2 | 9,406.3 |
| 4 | 1/1 ok | 31 | 772 s (12.9 min) | **1,932** | **9,172.1** | **9,505.7** |

Every chunk landed inside the 50-minute window. Chunk plan: 1,800 s estimated cap
(`chunkplan-flight.json`; the registered ≤50-min cap tightened operator-side after G1-PATH2's
stall observation — see §4). `stopped_reason=null` on all five; `G1BudgetExceeded` never fired.

## 3. Spend vs registered ceilings

| axis | used | ceiling | margin |
|---|---|---|---|
| flight calls (this campaign) | 1,932 | 2,900 | 968 |
| flight calls incl. PATH (104) + PATH2 (106) | 2,142 | 2,900 (campaign total incl. PATH, prereg §6) | 758 |
| GPU hours (real per-attempt accounting) | 2.55 | 6.0 | 3.45 |
| work-wall hours | 2.64 | 8.0 | 5.36 |

## 4. Dispatch-chain health and throughput

- **1,932 sink records vs 1,932 receipted calls — MATCH**; 0 duplicate request ids; 0 empty
  replies; **0 replies at max_tokens** (prereg §4 capped-reply disclosure: none, any arm).
- Attribution arms: **730/730** transcribe replies parse to ≥1 segment with the exact parser
  `run_item` feeds the minutes head (parse-chain PASS). Transcribe-only arms: 766/766 non-empty.
- **5 retried contacts of 1,932** (0.26%, all Z-oracle: 2 minutes + 3 transcribe;
  `diag-retry-counts.txt`) — each a degenerate unbounded generation burning the 300-s
  per-attempt transport timeout, then succeeding on its `-r1` retry (the same failure-and-
  recovery signature G1-PATH2 diagnosed; per-attempt timeout lowered 600→300 s for this flight
  to halve stall cost — operator transport parameter, not registered protocol). The five
  affected receipts carry the stall in their own gpu_seconds; receipts, budget, and sink all
  held. Excluding stalls, throughput ≈ 4.0 s/contact (planning basis 3.7).
- GPU healthy throughout (`gpu-health-chunk*.log`): 91–99% util, ~1,000–1,200 MHz under the SW
  power cap, no 232-MHz clock-stick episode, VRAM steady ~23.6 GB.

## 5. Discipline

- **No gold text entered any prompt path**: oracle NXT turns fed the slicer only (plans rebuilt
  from PRECOMP's cache); the NXT reference is scoring-side and no scoring ran.
- **Feature cache fully warm, byte-identical**: `ami-q4km` 14,324 entries / 11,486,248,768 bytes
  before chunk 0 and after every chunk; **0 encode lines** across all five server.log segments
  (204,420 lines total) — all three slice sets served from cache; never
  `q4km`/`slurp-q4km`/`audio2tool-q4km`.
- Response sinks are **raw traces** and stay on the data root, at the directory
  `scripts/g1_read.py --responses-dir` must be pointed at when the read is gated:
  `$SPEECHRL_DATA_DIR/derived/meeting-minutes/g1/runs/2026-08-19-g1-floors/responses/`
  (five files, 1,932 lines, 3,024,952 bytes; per-file sha256 in `response-sinks.sha256`).
  Git carries hashes and counts only.
- Archived receipts machine-checked to carry no reply text. No orphan `llama-server` survived
  any chunk. The repo tree stayed clean for the campaign's whole duration.
- AMI CC BY 4.0; MeetingQA CC BY-NC-SA carried on any future QA-derived numbers.

## 6. Files

- `structural-report.txt` — full-campaign structural validation (the authority for §1–§4):
  completion, plan conformance, gpu accounting, budget, reconciliation, parse health.
- `chunkplan-flight.json` — the deterministic 5-chunk/1,932-call plan every invocation rebuilt.
- `receipts/` (72), `chunks/` (5) — text-free per-item and per-chunk receipts.
- `runtime-identity.json` — binaries, GGUFs, server argv, ceilings, sink hashes (pins identical
  to every prior G1 pass: llama-server `097c96ec…c68`, build `5d9dfcb5…151`, core GGUF
  `0751c279…66d`, mmproj `f0dfe825…883`).
- `preflight.log` — pins, 72-item plan resolution (zero missing WAVs), cache-before state.
- `fly-chunk[0-4]-wrapper.log`, `progress-chunk[0-4].log`, `gpu-health-chunk[0-4].log`,
  `runner-chunk[0-4].log` — per-chunk flight logs.
- `response-sinks.sha256`, `response-sink-counts.txt` — stand-ins for the raw traces.
- `script-*.sh`, `structural.py`, `diag-sink-retry-count.py`, `diag-retry-counts.txt` — every
  operator script, archived verbatim.
- `MANIFEST.sha256` — sha256 of every file in this directory.
