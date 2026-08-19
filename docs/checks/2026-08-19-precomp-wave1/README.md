# PRECOMP wave-1 — pinned-diar + featcache production pass (2026-08-19) — **YIELDED 9/18**

**Production operations only. This record renders no verdict.** Nine of the eighteen dev-18
meetings completed the full registered pipeline (pinned Arm B diar → tool + oracle slice plans →
CPU slice cutting → featcache encode-warm). The pass then **yielded on the operator stop-file**
before `IB4011`, per the ready-first rule: the remaining nine meetings are untouched and resume
at meeting granularity with `--resume`.

Registration: `docs/readiness/2026-08-19-precomp-preregistration.md` (REGISTERED).
Tool lock: `docs/readiness/2026-08-19-diar-adjudication-TOOL-LOCKED-B.md` (TOOL-LOCKED(B)).
Machinery flown: commit `86e1595c6cc91d545f774ac9b8489096413cc42a`, unmodified; the tree was
clean before the pass and carried only this receipt directory during it
(`runtime-identity.json`, `logs/fly-wrapper.log`).

**Encode-warm generation text was never read.** The contact exists solely to make the frozen
core's audio encoder run over each slice; `precomp/encode_warm.py` structurally discards the
reply (`text` is never bound, hashed, logged, or printed), the receipts carry counts only, and
no generation text was recovered from any log at any point in this pass.

## Identity (hash-verified preflight, `logs/preflight.log`)

| item | value | check |
|---|---|---|
| llama-server | `/home/chao/llama.cpp-featcache/build/bin/llama-server`, 17,920 B, sha256 `097c96ec…c68` | **OK vs pin** |
| llama.cpp build | commit `5d9dfcb58ea860295da8fc93c7b5bed9e2c71151`, clean tree, `version: 5 (5d9dfcb58)` | OK |
| core GGUF | `Qwen3-Omni-30B-A3B-Instruct-Q4_K_M.gguf`, sha256 `0751c279…66d` | **OK vs pin** |
| mmproj GGUF | `mmproj-Qwen3-Omni-30B-A3B-Instruct-bf16.gguf`, sha256 `f0dfe825…883` | **OK vs pin** |
| diar binary | `nemo-speech.cpp/build/cuda-diar/bin/nemo-speech`, sha256 `1a3e3f4f…a78` | **OK vs pin** |
| diar checkpoint | `diar_streaming_sortformer_4spk-v2.q8_0.gguf`, sha256 `0679cfeb…98a` | **OK vs pin** |
| Arm B config | diar-smoke tooling `arm-config.json`, sha256 `608230d6…158` | pinned here |
| feature cache | `/home/chao/feat-cache/ami-q4km` — the same warm per-dataset directory the P-ATTR/P-PROMPT meeting flights used | never `q4km` / `slurp-q4km` / `audio2tool-q4km` |

Server argv (same pinned family as the P-ATTR/P-PROMPT flights):
`--host 127.0.0.1 --port 8080 -m <core> --mmproj <mmproj> -c 49152 -np 1 -fa on -ctk q8_0
-ctv q8_0 -ngl 999`. Full identity in `runtime-identity.json`.

## Preflight

- Full repo pytest at `86e1595`: **1,234 passed, 3 skipped** in 47.95 s (`logs/preflight.log`),
  shared venv read-only with `PYTHONPATH` armor and `PYTHONDONTWRITEBYTECODE=1` throughout.
- `run_precomp.py --summary-only`: resolved roster is exactly the frozen dev-18 (18 meetings),
  the fail-closed exposure gate admitted all of them, and the ceilings match the registration
  (0.5 GPU-h diar, 2.0 GPU-h encode, 2 h CPU cutting, 900 encode calls).
- Feature cache before the pass: **879 entries / 502,249,200 B** (the P-ATTR/P-PROMPT state).

## What flew

| meeting | ok | diar wall s | turns tool/oracle | slices tool/oracle (Δ) | cut wall s | encode calls | encode wall s | cache entries + | cache bytes + | bdisp med/max s |
|---|---|---|---|---|---|---|---|---|---|---|
| ES2011a | yes | 31.6 | 341 / 263 | 12 / 12 (0) | 1.81 | 24 | 151.9 | 298 | 246,330,016 | 14.9 / 30.5 |
| ES2011b | yes | 47.6 | 436 / 358 | 17 / 17 (0) | 2.75 | 34 | 216.7 | 333 | 274,658,512 | 4.5 / 15.1 |
| ES2011c | yes | 49.0 | 516 / 447 | 17 / 17 (0) | 2.80 | 34 | 224.0 | 418 | 345,053,728 | 17.7 / 47.1 |
| ES2011d | yes | 60.7 | 628 / 563 | 21 / 21 (0) | 3.46 | 42 | 273.3 | 519 | 425,459,824 | 31.5 / 60.9 |
| IB4001 | yes | 54.6 | 687 / 571 | 19 / 19 (0) | 3.09 | 38 | 254.6 | 478 | 391,060,960 | 20.4 / 28.1 |
| IB4002 | yes | 57.4 | 776 / 653 | 20 / 21 (−1) | 3.53 | 41 | 267.3 | 503 | 413,106,032 | 30.0 / 47.6 |
| IB4003 | yes | 64.1 | 498 / 422 | 22 / 22 (0) | 3.71 | 44 | 296.8 | 546 | 448,569,888 | 15.8 / 53.7 |
| IB4004 | yes | 76.0 | 688 / 625 | 26 / 27 (−1) | 4.95 | 53 | 355.8 | 655 | 539,945,200 | 30.4 / 46.1 |
| IB4010 | yes | 96.3 | 1,088 / 1,007 | 32 / 32 (0) | 5.05 | 64 | 421.0 | 790 | 649,105,760 | 12.4 / 38.1 |
| **total** | **9/9** | **537.2** | — | **186 / 188** | **31.15** | **374** | **2,461.5** | **4,540** | **3,733,289,920** | — |

`bdisp` = the registered boundary-displacement distribution (nearest-neighbour distance, in
seconds, from each tool-plan interior boundary to the closest oracle-plan interior boundary).
Descriptive only; the retired positional packing-change fraction was not computed. Full
per-meeting distributions are in `receipts/<meeting>-receipt.json`.

Audio covered: **17,333.3 s (4.82 h)** of the dev-18 total 34,801.8 s (9.67 h) — 49.8 %.
Loop wall clock 09:37:59Z → 10:31:28Z (53 min 29 s), zero errored meetings, zero retries.

Feature cache after the pass: **5,419 entries / 4,235,539,120 B** (+4,540 entries,
+3,733,289,920 B). 374 slice WAVs were cut, one encode-warm contact each — a 1:1
call-to-slice ratio with no repeats (`logs/slice-wav-count.txt`).

### Diar reproducibility (incidental, worth recording)

`ES2011a.rttm` (`1f80d8be…3d3e2`) and `ES2011b.rttm` (`449e27c6…049fd7`) are **byte-identical**
to the DIAR-SMOKE flight's own Arm B outputs for those meetings
(`docs/checks/2026-08-18-diar-smoke-flight/MANIFEST.sha256`). The pinned streaming-geometry
tool reproduced its earlier bytes exactly across flights, one day apart.

## Budget spend against the registered wave-1 ceilings

| axis | used | ceiling | share |
|---|---|---|---|
| encode calls | 374 | 900 | 41.6 % |
| encode GPU-hours | 0.635 (2,284.9 s) | 2.0 | 31.7 % |
| diar GPU-hours | 0.058 (209.8 s) | 0.5 | 11.7 % |
| CPU-cutting wall-hours | 0.009 (31.2 s) | 2.0 | 0.4 % |

No ceiling was approached and `PrecompBudgetExceeded` never fired. Extrapolating the observed
0.0216 calls per audio-second, the nine remaining meetings (17,468.6 s) need roughly **377 more
encode calls**, for a projected wave total near **751 of 900** — the wave completes inside its
registered ceiling on resume.

GPU-hour figures use the machinery's own coarse single-sample proxy
(`estimate_gpu_seconds`: wall × sampled utilization), not an integrated account; the diar figure
in particular under-reads because its sample is taken after the subprocess exits.

## Yield

The stop-file `PRECOMP_YIELD` was present at the pre-meeting check before `IB4011`
(10:31:28Z). The loop finished nothing further, wrote the wave summary, and the server was shut
down cleanly with SIGTERM (`logs/teardown-shutdown.log`; the cache was byte-identical before
and after shutdown, so nothing was in flight). Remaining wave-1 roster, untouched:

`IB4011, IS1008a, IS1008b, IS1008c, IS1008d, TS3004a, TS3004b, TS3004c, TS3004d`

Resume with the archived `scripts/script-fly.sh` — `--resume` skips the nine complete+verified
receipts and continues at `IB4011`.

## Operational note — GPU power cap

Throughout the pass the GPU ran under a platform-enforced **35 W** SW power cap (device default
95 W, max 175 W; `nvidia-smi -pl` is unsupported on this device, machine on AC power, Windows
"High performance" scheme active). SM clocks swung 350–1,700 MHz at 96–100 % utilization
(`logs/gpu-health.log`). An SM clock floor was locked (`-lgc 1200,2500`) before the pass per the
known-issue playbook; the power cap still dominates. Observed throughput nevertheless matched
the P-ATTR precedent (~6.6 s per encode-warm contact over ~93 s slices), so this is recorded as
an environmental condition, not a fault. Nothing in it affects the derived bytes.

## Discipline

- Every meeting passed the fail-closed exposure gate (`assert_wave_roster_admissible`) before
  any contact; eval-16 and held-out-reserve meetings were never named or touched.
- Oracle NXT turns fed the **slicer only**. No gold text entered any prompt path; the
  encode-warm request is the zero-supply transcribe-only head with `max_tokens=1`.
- All derived bytes (RTTM, 374 slice WAVs, 4,540 feature-cache entries) live on the data root
  and are **not** committed; Git carries hashes, counts and manifests only
  (`logs/rttm-artefacts.sha256`, `receipts/`, `MANIFEST.sha256`).
- Per-contact diar logging (tool id, version, checkpoint sha256, full argv, wall, return code)
  is on every receipt. Per-meeting transport ledgers are under `transport-receipts/`.
- The machinery (`scripts/run_precomp.py`, `src/meeting_minutes_agent/precomp/`) was **not
  modified**.

### Deviation recorded for coordinator review — per-meeting invocation loop

The runner exposes no in-flight stop hook, so the yield protocol required wrapping it as one
invocation per meeting (`--meetings <one> --resume`, `scripts/script-fly.sh`). Each process
builds a **fresh** `PrecompBudget`, which would have reset the WAVE-level ceilings between
meetings. To close that hole, `scripts/budget_ledger.py` re-derives wave-cumulative usage from
the committed receipts and re-applies the same registered `ceilings_for_wave(1)` values,
fail-closed, before each meeting starts (its check is logged in `logs/progress.log` ahead of
every meeting). This is strictly additive — it never relaxes a ceiling, and the in-process guard
stayed active underneath it. `scripts/aggregate.py` likewise rebuilds the single registered
`wave-summary.json` over all receipts using the machinery's own `build_wave_summary`, since each
per-meeting process would otherwise leave a summary covering one meeting.

## Files

- `wave-summary.json` — the wave artefact (9 outcomes, cumulative budget, yield reason).
- `receipts/<meeting>-receipt.json` — the nine per-meeting receipts (schema 1.0.0).
- `transport-receipts/<meeting>.json` — per-meeting content-hashed transport ledgers.
- `runtime-identity.json` — binaries, GGUFs, diar pin, server argv, cache state.
- `preflight.log`, `fly-wrapper.log`, `progress.log`, `gpu-health.log`,
  `teardown-shutdown.log`, `<meeting>-runner.log` — the pass's logs.
- `rttm-artefacts.sha256`, `slice-wav-count.txt` — hashes and counts standing in for the
  derived bytes that stay on the data root.
- `script-*.sh`, `budget_ledger.py`, `aggregate.py`, `table.py` — every operator script that
  drove the pass, archived verbatim.
- `MANIFEST.sha256` — sha256 of every file in this directory.

Layout note: this directory is flat (top-level `*.log` / `script-*.sh`, plus `receipts/` and
`transport-receipts/`) to match every prior flight receipt directory — a `logs/` subdirectory
is gitignored repository-wide (`.gitignore:15`, openJiuwen runtime log output).
