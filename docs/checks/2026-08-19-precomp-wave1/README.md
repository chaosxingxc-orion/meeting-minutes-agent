# PRECOMP wave-1 — pinned-diar + featcache production pass (2026-08-19) — **COMPLETE 18/18**

> **Status: wave-1 is COMPLETE — all 18 dev-18 meetings receipted, `n_error: 0`, inside every
> registered ceiling.** This record is cumulative and written in two parts. Everything down to
> "## Discipline" is the **first pass** (9/18, yielded on the operator stop-file, commit
> `b969add`) and is preserved unedited. The **resume pass** that finished the remaining nine
> meetings is appended at the end, from "## Resume pass" onward; it carries the final
> per-meeting table, the final wave totals, and the one interruption that had to be retried.
> Read the resume section for the wave's final state — the "Yield" section below is history.

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

---

# Resume pass — wave-1 **COMPLETE 18/18** (2026-08-19, 11:55–13:11Z)

**Production operations only. This record renders no verdict.** The nine meetings the first
pass left untouched (`IB4011`, `IS1008a–d`, `TS3004a–d`) completed the same registered pipeline
under the same pins. Wave-1 now carries 18 complete+verified receipts, `n_error: 0`, and no
ceiling was reached.

Machinery flown: commit `83cf4b6dd1f1589229e929f57230e970351c42d0`, unmodified. A concurrent,
unrelated session committed `fe64d00` (third-party cold-cache doc + a standalone featcache
builder) while this pass was in the air, so the transport receipts and
`runtime-identity-resume.json` record HEAD as `fe64d00`. That commit touches neither the
machinery nor this directory —
`git diff --name-only 83cf4b6 fe64d00 -- scripts/run_precomp.py src/meeting_minutes_agent/precomp/ docs/checks/2026-08-19-precomp-wave1/`
is empty — so the flown code is byte-identical to `83cf4b6` throughout.

**The first pass's "Deviation recorded for coordinator review" is retired.** Commit `e4e18c4`
ported the external per-meeting reconciliation into `PrecompBudget.precharge()` and added the
native `--stop-file` hook, so this pass ran as **one** `run_precomp.py --wave 1 --resume
--stop-file <PRECOMP_YIELD> --workers 8` invocation. The external `budget_ledger.py` was kept
only as an independent operator cross-check of the native precharge (the two agreed exactly),
never as the enforcing guard. The stop-file was absent throughout and was never created.

## Preflight (`preflight-resume.log`)

- Repo clean at `83cf4b6`; full pytest **1,257 passed, 3 skipped** in 65.42 s, shared venv
  read-only with `PYTHONPATH` armor and `PYTHONDONTWRITEBYTECODE=1`.
- All five hash pins **OK**: llama-server `097c96ec…`, core GGUF `0751c279…`, mmproj
  `f0dfe825…`, diar binary `1a3e3f4f…`, diar checkpoint `0679cfeb…`. llama.cpp at
  `5d9dfcb58`, clean tree. Arm B config `608230d6…`.
- `--summary-only`: roster is the frozen dev-18, fail-closed exposure gate admits all 18.
- Resume-skip proof: `already_done` skips exactly the nine receipted meetings and runs exactly
  the nine remaining ones.
- **Native budget pre-charge**, re-derived from the nine receipts on disk: 374 encode calls /
  2,284.87 encode GPU-s / 209.84 diar GPU-s / 31.15 cutting s → **ADMISSIBLE**. The runner's
  own startup precharge and the operator ledger produced identical figures.
- Feature cache before: **5,419 entries / 4,235,539,120 B**.

## What flew (the nine)

| meeting | ok | diar wall s | turns tool/oracle | slices tool/oracle (Δ) | cut wall s | encode calls | encode wall s | cache entries + | cache bytes + | bdisp med/max s |
|---|---|---|---|---|---|---|---|---|---|---|
| IB4011 | yes | 73.7 | 826 / 785 | 26 / 27 (−1) | 4.19 | 53 | 350.5 | 653 | 534,513,872 | 19.5 / 37.9 |
| IS1008a | yes | 28.0 | 182 / 176 | 9 / 10 (−1) | 1.61 | 19 | 129.8 | 243 | 199,577,392 | 29.8 / 47.8 |
| IS1008b | yes | 54.1 | 317 / 354 | 19 / 18 (+1) | 3.15 | 37 | 241.6 | 381 | 312,465,360 | 21.9 / 46.7 |
| IS1008c | yes | 48.6 | 358 / 372 | 16 / 18 (−2) | 3.14 | 34 | 254.5 | 420 | 342,817,344 | 4.3 / 38.7 |
| IS1008d | yes | 68.8 | 414 / 386 | 15 / 16 (−1) | 67.06 | 31 | 192.0 | 310 | 255,169,376 | 11.5 / 32.4 |
| TS3004a | yes | 58.7 | 430 / 404 | 14 / 15 (−1) | 34.47 | 29 | 201.3 | 357 | 294,147,664 | 30.4 / 44.9 |
| TS3004b | yes | 88.4 | 738 / 607 | 24 / 24 (0) | 62.67 | 48 | 332.3 | 509 | 418,537,424 | 0.1 / 15.0 |
| TS3004c | yes | 120.8 | 913 / 764 | 29 / 26 (+3) | 91.63 | 55 | 393.4 | 678 | 556,239,456 | 1.6 / 559.4 |
| TS3004d | yes | 107.7 | 1,024 / 919 | 29 / 29 (0) | 70.58 | 58 | 398.2 | 567 | 468,378,480 | 10.7 / 40.9 |
| **resume total** | **9/9** | **648.8** | — | **181 / 183** | **338.50** | **364** | **2,493.6** | **4,118** | **3,381,846,368** | — |

Audio covered by these nine: **17,468.7 s (4.85 h)**, completing the dev-18 total of 34,801.8 s
(9.67 h). The full 18-meeting table is `per-meeting-table-final.txt`; per-meeting
boundary-displacement distributions are in each `receipts/<meeting>-receipt.json`.

Two descriptive observations, recorded without a causal claim because this pass did not
investigate either: `TS3004c` carries a boundary-displacement **max of 559.4 s** against a
median of 1.6 s (an isolated far-from-oracle tool boundary, not a shifted distribution), and
CPU-cutting wall splits sharply between the first six resume meetings (1.6–4.2 s) and
`IS1008d` plus the four `TS3004*` meetings (34–92 s) at identical worker count. Neither
affects any derived byte, and cutting used 5.1 % of its ceiling either way.

## Final wave-1 totals (all 18 meetings)

| meeting count | diar wall s | slices tool/oracle | cut wall s | encode calls | encode wall s |
|---|---|---|---|---|---|
| 18 / 18 ok | 1,186.0 | 367 / 371 | 369.65 | 738 | 4,955.1 |

| axis | used | ceiling | share |
|---|---|---|---|
| encode calls | 738 | 900 | 82.0 % |
| encode GPU-hours | 1.009 (3,633.15 s) | 2.0 | 50.5 % |
| diar GPU-hours | 0.075 (270.82 s) | 0.5 | 15.0 % |
| CPU-cutting wall-hours | 0.103 (369.65 s) | 2.0 | 5.1 % |

`PrecompBudgetExceeded` never fired and `stopped_reason` is `null`. The first pass's projection
(~751 of 900 calls) landed within 2 % of the realized 738. GPU-hour figures remain the
machinery's coarse single-sample proxy (`estimate_gpu_seconds`: wall × sampled utilization), not
an integrated account; the diar figure still under-reads because its sample is taken after the
subprocess exits (six of the nine resume diar runs sampled exactly 0.0).

Derived state at wave end: **18 RTTMs** (`rttm-artefacts-final.sha256`), **738 slice WAVs**
(`slice-wav-count-final.txt`) — exactly 367 tool + 371 oracle, a 1:1 slice-to-contact ratio with
no repeats — and a feature cache of **9,685 entries / 7,739,858,256 B**, up from the 879 entries
/ 502,249,200 B the wave started at.

## The interruption, and the one meeting that was retried

Eight of the nine meetings completed in a single invocation (11:55:09Z → 12:54:20Z, runner wall
3,550 s). `TS3004d` then failed with
`URLError: <urlopen error [Errno 104] Connection reset by peer>`: **the harness reaps a
background job at 60 minutes, and the `llama-server` this pass depended on was one** — started
11:54:10Z, killed 12:54:10Z, mid-encode. Nothing about the pins, the data, the machinery or the
budget was involved; only the server process died. The runner behaved exactly as designed: it
wrote a complete `ok: false` receipt for `TS3004d`, finished cleanly (`rc=0`), and left the
other seventeen untouched.

The retry (`script-fly-retry.sh`, 12:57:30Z → 13:10:55Z, runner wall 681 s) started its own
`llama-server` **as a child of the retry script**, so server and work share one harness window,
and re-ran `--resume` — which by construction selected `TS3004d` alone, the only receipt that
was not `ok`. It completed: 58 calls, 29/29 slices, 398.2 s encode.

The superseded first attempt is archived as `TS3004d-aborted-attempt-receipt.json` (sha256
`5f339d28…`) because the retry overwrote it on disk and because it spent real resources that the
receipt-derived ledger can no longer see:

- **13 frozen-core contacts** (transport ledger `transport-receipts/resume-2026-08-19.json`
  records 319 calls against 306 receipted for the eight meetings that completed). True wave
  contacts are therefore **751**, of which **738** are receipted; the 13-call gap is exactly this
  aborted attempt.
- **131.19 s of CPU cutting** and **111.17 s of diar wall** (its diar GPU estimate was 0.0, so the
  GPU-hour ledger is unaffected). Real cutting spend across the wave is ~500.8 s (0.139 h)
  against the 2.0 h ceiling.
- **148 feature-cache entries** (~122 MB). These are not orphans: the pinned diar reproduced
  1,024 turns and 29/29 slices identically on both attempts, so the retry's byte-identical slices
  hit those entries rather than recreating them — the arithmetic closes exactly
  (3,699 + 567 measured cache growth = 4,118 receipted + 148 from the aborted attempt).

No ceiling is affected by any of this: even counting every superseded contact, the wave used 751
of 900 calls.

## Discipline (resume pass)

- **Encode-warm generation text was never read.** Unchanged from the first pass: the contact
  exists solely to run the frozen core's audio encoder over each slice, `precomp/encode_warm.py`
  structurally discards the reply, receipts carry counts only, and no generation text was
  recovered from any log at any point — including from the aborted attempt.
- Every meeting passed the fail-closed exposure gate before any contact; eval-16 and
  held-out-reserve meetings were never named or touched.
- Oracle NXT turns fed the **slicer only**. No gold text entered any prompt path; the encode-warm
  request is the zero-supply transcribe-only head with `max_tokens=1`.
- All derived bytes stay on the data root and are **not** committed; Git carries hashes, counts
  and manifests only.
- The machinery (`scripts/run_precomp.py`, `src/meeting_minutes_agent/precomp/`) was **not
  modified** by this pass.
- The server was shut down cleanly with SIGTERM (`teardown-resume-retry.log`; GPU memory back to
  0 MiB).
- **Prior-file integrity**: every one of the 48 files the first pass landed was re-hashed against
  the committed `MANIFEST.sha256` after this pass (`prior-file-integrity-resume.txt`): **47
  byte-intact, 1 changed** — `wave-summary.json`, which by construction must describe the whole
  wave and is the single registered wave artefact. `MANIFEST.sha256` and this `README.md` are
  likewise updated for the completed wave; nothing else from the first pass was touched.

## Operational note — GPU power cap (unchanged)

The SM clock floor (`-lgc 1200,2500`) was re-applied before the pass and held: 79 of 115 resume
samples sat at 1,200 MHz, with excursions to 1,515 MHz and dips as low as 180 MHz. Power draw ranged
10.32–56.99 W under the same platform-enforced SW cap the first pass recorded. Throughput again
matched the P-ATTR precedent (~6.8 s per encode-warm contact), so this remains an environmental
condition, not a fault, and affects no derived byte.

## Files added by the resume pass

- `receipts/<meeting>-receipt.json` — the nine new per-meeting receipts (schema 1.0.0).
- `wave-summary.json` — **updated**: now the 18-outcome wave artefact, `n_ok: 18`,
  `n_error: 0`, `stopped_reason: null`, rebuilt over all receipts by `aggregate_resume.py`
  using the machinery's own `build_wave_summary`.
- `transport-receipts/resume-2026-08-19.json`, `…-retry.json` — content-hashed transport
  ledgers for the resume invocation (319 calls) and the retry (58 calls).
- `runtime-identity-resume.json` — binaries, GGUFs, diar pin, server argv, cache state at the
  end of the pass.
- `TS3004d-aborted-attempt-receipt.json` — the superseded attempt, kept as evidence, **not** a
  wave outcome.
- `preflight-resume.log`, `fly-resume-wrapper.log`, `progress-resume.log`,
  `gpu-health-resume.log`, `resume-runner.log`, `fly-retry-wrapper.log`, `progress-retry.log`,
  `gpu-health-retry.log`, `retry-runner.log`, `teardown-resume-retry.log` — the pass's logs.
- `per-meeting-table-final.txt` — the descriptive table over all 18 receipts.
- `rttm-artefacts-final.sha256`, `slice-wav-count-final.txt` — hashes and counts standing in for
  the derived bytes that stay on the data root.
- `prior-file-integrity-resume.txt` — the re-hash of every first-pass file.
- `script-*-resume.sh`, `script-fly-retry.sh`, `script-wait-retry.sh`, `aggregate_resume.py` —
  every operator script that drove this pass, archived verbatim. `script-env.sh` and
  `script-serve.sh` were restored byte-identical from this directory and are unchanged.
- `MANIFEST.sha256` — **regenerated** over the completed directory.
