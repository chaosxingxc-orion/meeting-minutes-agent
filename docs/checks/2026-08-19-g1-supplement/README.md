# G1 VAD supplement — Z-nodiar slice source (2026-08-19) — **COMPLETE 18/18**

> **Status: COMPLETE — all 18 dev-18 meetings carry a VAD slice set, a persisted `SlicePlan`
> manifest, and a warm feature cache. `n_error: 0`, `stopped_reason: null`, inside every
> registered ceiling.**

**Production operations only. This record renders no verdict.** The G1 floors campaign's
Z-nodiar arm slices each meeting with pure-VAD 90 s packing and no diarization at all
(`docs/readiness/2026-08-19-g1-floors-preregistration.md` §3: "Z-nodiar's slices are NOT
precomputed — either a small PRECOMP supplement (~370 slices, ≈0.6 GPU-h) runs first or the arm
pays lazy encode in-flight; the supplement is the default"). This pass is that supplement.

Registration: `docs/readiness/2026-08-19-g1-floors-preregistration.md` (REGISTERED, owner GO
2026-08-19). Ceilings profile: **`g1-supplement`** — 500 encode calls / 1.0 GPU-h encode / 1.0 h
CPU cutting, budgeted **separately** from PRECOMP wave-1's own ≤900-call ceiling (wave-1 alone
already used 738 of it).

Machinery flown: commit `f13ad6f2b77409e9728190a57564f0ecaa2637bd`, **unmodified**. The tree was
clean before the pass and carried only this receipt directory during it.

**No diarization contact.** `--turn-sources vad` structurally skips the pinned Arm B diar tool and
the NXT oracle resolution; `diar_gpu_seconds_used` is `0.0` by construction, and no `--arm-config`
was supplied or required.

**Encode-warm generation text was never read.** Unchanged from wave-1: the contact exists solely
to make the frozen core's audio encoder run over each slice, `precomp/encode_warm.py` structurally
discards the reply, receipts carry counts only, and no generation text was recovered from any log
at any point in this pass.

## Identity (hash-verified preflight, `preflight.log`)

| item | value | check |
|---|---|---|
| llama-server | `/home/chao/llama.cpp-featcache/build/bin/llama-server`, 17,920 B, sha256 `097c96ec…c68` | **OK vs pin** |
| llama.cpp build | commit `5d9dfcb58ea860295da8fc93c7b5bed9e2c71151`, clean tree, `version: 5 (5d9dfcb58)` | **OK vs pin** |
| core GGUF | `Qwen3-Omni-30B-A3B-Instruct-Q4_K_M.gguf`, sha256 `0751c279…66d` | **OK vs pin** |
| mmproj GGUF | `mmproj-Qwen3-Omni-30B-A3B-Instruct-bf16.gguf`, sha256 `f0dfe825…883` | **OK vs pin** |
| diar binary / checkpoint | not used — no diar contact at this turn source | n/a |
| feature cache | `/home/chao/feat-cache/ami-q4km` — the same warm per-dataset directory wave-1 and the P-ATTR/P-PROMPT flights used | never `q4km` / `slurp-q4km` / `audio2tool-q4km` |

Server argv (same pinned family as every prior flight):
`--host 127.0.0.1 --port 8080 -m <core> --mmproj <mmproj> -c 49152 -np 1 -fa on -ctk q8_0
-ctv q8_0 -ngl 999`. Full identity in `runtime-identity.json`.

## Preflight

- Repo clean at `f13ad6f`; full pytest **1,498 passed, 3 skipped** in 36.40 s, shared venv
  read-only with `PYTHONPATH` armor and `PYTHONDONTWRITEBYTECODE=1` throughout.
- `run_precomp.py --turn-sources vad --ceilings-profile g1-supplement --summary-only`: roster is
  the frozen dev-18 (18 meetings), the fail-closed exposure gate admitted all of them, and the
  ceilings resolve to the registered supplement profile (500 / 1.0 / 1.0), **not** wave-1's.
- `missing_required_args` for a vad-only real run confirms `--arm-config` is not required.
- Crude projection from meeting durations: ~387 encode calls against the 500-call ceiling.
- Feature cache before the pass: **9,685 entries / 7,739,858,256 B** (wave-1's end state).

## Invocation shape

Two invocations, nine meetings each, each one a single `run_precomp.py … --resume --stop-file
<G1SUP_YIELD> --workers 8` process that **starts and tears down its own `llama-server` as a direct
child** — so server and work share one harness window and the server can never outlive, or be
killed independently of, the work depending on it (the wave-1 resume-pass lesson, where a
separately-backgrounded server was reaped mid-encode at 60 minutes). Each invocation ran ~6.5
minutes, far inside the ~50-minute cap.

The stop-file was absent throughout and was never created. The wave-1 first pass's external
per-meeting budget-ledger workaround is **not** repeated: `PrecompBudget.precharge` re-derived
cumulative usage from the receipts on disk at the start of pass B, and `ledger.py` was kept only
as an independent operator cross-check of that native precharge (the two agreed exactly).

## What flew

| meeting | ok | vad slices | plan content_hash | manifest | cut wall s | encode calls | encode wall s | cache entries + | cache bytes + |
|---|---|---|---|---|---|---|---|---|---|
| ES2011a | yes | 13 | `31fc0b340269` | yes | 0.98 | 13 | 21.1 | 149 | 119,916,880 |
| ES2011b | yes | 18 | `e8c3a5872989` | yes | 1.44 | 18 | 29.5 | 211 | 170,077,488 |
| ES2011c | yes | 18 | `1c51aad49dc8` | yes | 1.32 | 18 | 31.3 | 215 | 173,911,408 |
| ES2011d | yes | 22 | `451e9df860c9` | yes | 1.81 | 22 | 37.4 | 264 | 213,422,208 |
| IB4001 | yes | 20 | `af4cccc841b3` | yes | 1.79 | 20 | 34.8 | 237 | 191,696,592 |
| IB4002 | yes | 21 | `68c00374fc3a` | yes | 1.59 | 21 | 36.2 | 251 | 202,665,904 |
| IB4003 | yes | 23 | `8b670c01766f` | yes | 1.79 | 23 | 40.4 | 270 | 217,895,136 |
| IB4004 | yes | 27 | `40441d21d8c6` | yes | 2.21 | 27 | 47.7 | 319 | 257,405,936 |
| IB4010 | yes | 33 | `75d8edd5ff77` | yes | 2.87 | 33 | 58.2 | 395 | 318,748,848 |
| IB4011 | yes | 27 | `8bfb7b41aacb` | yes | 2.18 | 27 | 48.0 | 322 | 260,174,880 |
| IS1008a | yes | 11 | `53bb3452ce43` | yes | 0.89 | 11 | 18.1 | 126 | 101,599,200 |
| IS1008b | yes | 20 | `105e71ab96da` | yes | 1.62 | 20 | 34.4 | 235 | 190,312,112 |
| IS1008c | yes | 17 | `44f9e6fd4bf9` | yes | 1.39 | 17 | 30.2 | 206 | 166,456,544 |
| IS1008d | yes | 17 | `ac855ff29ad1` | yes | 1.35 | 17 | 29.0 | 198 | 159,427,680 |
| TS3004a | yes | 15 | `928206e713f0` | yes | 1.39 | 15 | 25.0 | 179 | 144,837,424 |
| TS3004b | yes | 25 | `e451797e0884` | yes | 2.02 | 25 | 43.3 | 299 | 241,857,200 |
| TS3004c | yes | 33 | `9533d436e776` | yes | 2.93 | 33 | 55.9 | 396 | 319,813,824 |
| TS3004d | yes | 31 | `16dbc0900c6d` | yes | 2.66 | 31 | 52.2 | 367 | 296,171,248 |
| **total** | **18/18** | **391** | — | **18/18** | **32.24** | **391** | **672.9** | **4,639** | **3,746,390,512** |

Pass A (`ES2011a`–`IB4010`): 17:17:19Z → 17:24:01Z, runner wall 379 s, 195 calls.
Pass B (`IB4011`–`TS3004d`): 17:24:38Z → 17:31:14Z, runner wall 380 s, 196 calls.
Audio covered: the full dev-18 34,801.8 s (9.67 h). 391 slice WAVs were cut, one encode-warm
contact each — a 1:1 call-to-slice ratio with no repeats (`vad-slice-wav-count.txt`).
Throughput: 672.9 s of encode wall over 391 contacts, **1.72 s per contact**.

### Slice-count comparison against wave-1's own two turn sources (descriptive, no verdict)

| source | slices |
|---|---|
| pure VAD (this supplement) | **391** |
| pinned tool diar (wave-1) | 367 |
| oracle NXT turns (wave-1) | 371 |

VAD packing yields slightly more slices in aggregate (391 vs 367 / 371). Per meeting it is at or
above the tool count on all 18, and at or above the oracle count on 17 of 18 — the single
exception is `IS1008c` (VAD 17, tool 16, oracle 18). This is recorded as an observation, not a
finding: no causal claim is made and nothing here is scored. Per-meeting figures are in
`per-meeting-table.txt` and each `receipts/<meeting>-receipt.json`.

## Budget spend against the registered `g1-supplement` ceilings

| axis | used | ceiling | share |
|---|---|---|---|
| encode calls | 391 | 500 | 78.2 % |
| encode GPU-hours | 0.166 (598.72 s) | 1.0 | 16.6 % |
| diar GPU-hours | 0.000 (0.0 s) | 0.1 | 0.0 % |
| CPU-cutting wall-hours | 0.009 (32.24 s) | 1.0 | 0.9 % |

`PrecompBudgetExceeded` never fired and `stopped_reason` is `null`. The preflight projection
(~387 calls) landed within 1 % of the realized 391. GPU-hour figures remain the machinery's coarse
single-sample proxy (`estimate_gpu_seconds`: wall × sampled utilization), not an integrated
account.

Feature cache after the pass: **14,324 entries / 11,486,248,768 B** (+4,639 entries,
+3,746,390,512 B). Derived slice WAVs on the data root now total **1,129** = 367 tool + 371 oracle
+ 391 VAD (`all-slice-wav-count.txt`).

## What G1's Z-nodiar arm consumes

Each meeting's built `SlicePlan` is persisted as `SlicePlan.to_dict()`-shaped JSON at
`$SPEECHRL_DATA_DIR/derived/meeting-minutes/precomp/slices/vad-manifest/<meeting_id>.json`
(18 files, sha256 list in `vad-manifests.sha256`). That directory is exactly what
`scripts/run_g1.py --vad-manifest-dir` must be pointed at:
`probes/g1.load_vad_slice_plan` reads `<dir>/<meeting_id>.json` and fails closed
(`G1VadSupplementMissingError`) if it is absent. The slice WAVs themselves live under
`…/slices/vad/<meeting_id>/` and are named by the same deterministic
`<meeting_id>-slice<index:04d>.wav` convention every other source uses.

## Discipline

- Every meeting passed the fail-closed exposure gate (`assert_wave_roster_admissible`) before any
  contact; eval-16 and held-out-reserve meetings were never named or touched.
- **No gold text and no diarization output entered any prompt path.** The VAD source consults
  neither; the encode-warm request is the zero-supply transcribe-only head with `max_tokens=1`.
- All derived bytes (391 slice WAVs, 18 `SlicePlan` manifests, 4,639 feature-cache entries) live
  on the data root and are **not** committed; Git carries hashes, counts and manifests only.
- The machinery (`scripts/run_precomp.py`, `src/meeting_minutes_agent/precomp/`) was **not
  modified** by this pass.
- Both servers were torn down inside their own invocation; no orphan `llama-server` process
  survived either pass, and none was running when this record was written.
- **PRECOMP wave-1 prior-file integrity**: all **88** files of the committed
  `docs/checks/2026-08-19-precomp-wave1/MANIFEST.sha256` were re-hashed after this pass —
  **88 byte-intact, 0 changed, 0 missing** (`wave1-prior-file-integrity.txt`). This supplement
  writes to its own separate directory and touched nothing of wave-1's.

## Operational note — GPU power cap (unchanged)

The SM clock floor (`-lgc 1200,2500`) held: 21 of 26 samples across both passes sat at 1,200 MHz,
with dips to 630–697 MHz. Power draw ranged 12.55–73.26 W under the same platform-enforced SW
power cap wave-1 recorded (`clocks_throttle_reasons.active` showed `0x4`, SW power cap, in a
minority of samples). Observed throughput (1.72 s per encode-warm contact) was **materially better
than wave-1's** 6.6–6.8 s; the clock floor was already applied when this pass started, whereas
wave-1's first samples swung 350–1,700 MHz. This is recorded as an environmental observation, not
a fault, and affects no derived byte.

## Files

- `wave-summary.json` — the summary artefact over all 18 receipts (schema 1.1.0, `n_ok: 18`,
  `n_error: 0`, `stopped_reason: null`), rebuilt by `aggregate.py` using the machinery's own
  `build_wave_summary`, since each invocation's own summary sees only its own outcomes.
- `receipts/<meeting>-receipt.json` — the 18 per-meeting receipts.
- `transport-receipts/passA-2026-08-19.json`, `…passB-….json` — per-pass content-hashed transport
  ledgers.
- `runtime-identity.json` — binaries, GGUFs, server argv, cache state at the end of the pass.
- `preflight.log`, `fly-pass{A,B}-wrapper.log`, `progress-pass{A,B}.log`,
  `gpu-health-pass{A,B}.log`, `runner-pass{A,B}.log` — the pass's logs.
- `per-meeting-table.txt`, `ledger-final.json` — the descriptive table and the final operator
  ledger cross-check.
- `vad-manifests.sha256`, `vad-slice-wav-count.txt`, `all-slice-wav-count.txt` — hashes and counts
  standing in for the derived bytes that stay on the data root.
- `wave1-prior-file-integrity.txt` — the re-hash of every committed wave-1 file.
- `script-*.sh`, `ledger.py`, `aggregate.py`, `table.py` — every operator script that drove the
  pass, archived verbatim.
- `MANIFEST.sha256` — sha256 of every file in this directory.

Layout note: this directory is flat (top-level `*.log` / `script-*.sh`, plus `receipts/` and
`transport-receipts/`) to match every prior flight receipt directory — a `logs/` subdirectory is
gitignored repository-wide (`.gitignore:15`).
