# P-PROMPT template-and-arrangement sweep — flight record (2026-08-18)

**The registered 14-arm prompt-form sweep, FLOWN.** 14 arms × 24 slices = 336 requests, zero
failures, zero retries. Flight operations only: no reply text was read, and nothing here scores
anything. The one-shot read (winner cell, GRAMMAR-BLOCKED, CONTEXT-SENSITIVE/INERT verdicts) is a
separate mission that consumes the reply records named below.

Registration: `docs/readiness/2026-08-18-pprompt-preregistration.md` (grid, metrics, ceilings).
Binding manifest: `configs/probes/pprompt/2026-08-18-pprompt-binding.json`, sha256
`11ca048ead1c5f957000e9a93475d95d63764fcf3590ed050e5ca8883d0b27e0` — re-verified from disk bytes
before flight. Audio surface: the P-ATTR smoke's frozen 24-slice manifest
(`configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json`), reused verbatim.
Code commit flown: `132d984dbf4970d9a597d3c4041d27fe43523fe1`, clean tree (each of the 14 receipts
records `git.dirty = false` independently).

## Pre-flight (logs archived here)

- **Suite**: 987 passed, 3 skipped (`preflight-pytest.log`).
- **Identity pins** (`preflight.log`): binding-manifest sha256, llama-server binary sha256, llama.cpp
  build commit + clean tree, both GGUF sha256, and the X2 donor JSONL sha256
  (`68afc29c…8266`, the P-ATTR archive's own `run-dir-artefacts.sha256` fingerprint for
  `a-turn-responses.jsonl`) — all OK, fail-closed.
- **Audio integrity**: all 24 slice WAVs re-hashed from disk bytes against the frozen manifest's own
  pins — zero missing, zero mismatched; 2,345.373 s total, longest 110.347 s;
  `transport_bound_violations` = 0.
- **Counts**: launcher `--summary-only` confirmed 24 requests / 2,345.373 s per arm for every one of
  the 14 arms (= 336) before the server was started (`preflight-summary-only.log`). The X2
  summary pass also exercises the donor-tail sha256 verification (fail-closed, clean).
- **Feature cache**: `ami-q4km` WARM at exactly **879 entries** from the P-ATTR smoke (this sweep
  re-flies only those already-encoded 24 slice WAVs). `q4km` / `slurp-q4km` / `audio2tool-q4km`
  untouched throughout — verified by mtime after teardown (`teardown-shutdown.log`).
- **GPU**: idle P8, 180–202 MHz, no orphan `llama-server` (checked from both WSL and Windows).

## Server identity

Recorded in `runtime-identity.json`; every hash matches the P-ATTR flight archive's (SAEA-proven)
pins. Same binary, same GGUF pair, same serving args as the P-ATTR smoke.

| item | value |
|---|---|
| binary | `/home/chao/llama.cpp-featcache/build/bin/llama-server` (17,920 B) |
| binary sha256 | `097c96ec5a3f576f378d4d5e103928bf070647fdcc1f015eacb839503e121c68` |
| build commit | `5d9dfcb58ea860295da8fc93c7b5bed9e2c71151` (clean tree, `version: 5 (5d9dfcb58)`) |
| model | `Qwen3-Omni-30B-A3B-Instruct-Q4_K_M.gguf`, sha256 `0751c279…066d` |
| mmproj | `mmproj-Qwen3-Omni-30B-A3B-Instruct-bf16.gguf`, sha256 `f0dfe825…2883` |
| serving args | `-c 49152 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0`, `127.0.0.1:8080` |
| decoding | `temperature 0`, `seed 20260818`, `max_tokens` 1024, client timeout 420 s |

## What flew

Order: T1-A1 → … → T4-A3 → X1 → X2 (the `ARMS` order), sequentially against one slot,
2026-08-18 18:16:44Z → 18:37:35Z. Every arm: 24/24 ok, 0 errors, 0 retries, 2,345.373 metered
audio-seconds.

| arm | wall | mean latency | arm | wall | mean latency |
|---|---|---|---|---|---|
| T1-A1 | 101 s | 4.12 s | T3-A2 | 100 s | 4.12 s |
| T1-A2 | 74 s | 3.00 s | T3-A3 | 69 s | 2.81 s |
| T1-A3 | 74 s | 3.01 s | T4-A1 | 95 s | 3.89 s |
| T2-A1 | 96 s | 3.90 s | T4-A2 | 103 s | 4.18 s |
| T2-A2 | 103 s | 4.22 s | T4-A3 | 71 s | 2.85 s |
| T2-A3 | 71 s | 2.88 s | X1 | 93 s | 3.80 s |
| T3-A1 | 97 s | 3.96 s | X2 | 103 s | 4.16 s |

**Total: 336/336, 0 errors, 0 retries, 1,251 s of arm wall-clock (3.72 s/request)** — faster than
the P-ATTR slice-arm precedent (4.25–4.78 s/request) on the same audio.

## Budget vs the registered ceilings

| ceiling | registered | used | headroom |
|---|---|---|---|
| core calls | ≤ 380 | 336 | 44 |
| metered audio-seconds | ≤ 35,000 | 32,835.229 | 2,164.771 |
| GPU-hours | ≤ 1.0 | 0.339 (sum of request latency) / 0.286 (utilisation-integrated) / ~0.37 (server-resident wall) | ≥ 0.63 |

Per-arm `CallBudget` caps (26 calls / 2,500 audio-s, summing to 364 / 35,000 under the global
ceilings) were never approached: every arm used 24 of 26 and 2,345.373 of 2,500.

## Feature cache behaviour (WARM, as registered)

`ami-q4km` stayed at exactly **879 entries / 502,249,200 bytes** through all 336 requests
(recorded before/after every arm in each launcher log), and the server log carries **zero**
`encoding` lines — against 879 on the P-ATTR flight's cold pass of the same cache. The sweep's
encoder cost was fully cache-served, exactly the registered expectation. Sibling caches' mtimes
unchanged (`teardown-shutdown.log`).

## GPU health

Sampled every 30 s (`gpu-health.log`, 43 samples). Clocks sat at 232 MHz under load with the known
benign `0x4` throttle-reason reading on this machine, peak 64 °C, returning to 180 MHz/P8 idle.
The failure mode that reading can indicate is a *slowdown*, and there was none (throughput beat the
P-ATTR slice-arm precedent), so no clock override was applied. Teardown returned the GPU to
493 MiB / P8.

## Handoff to the read mission

Reply records (raw traces — deliberately NOT in Git, per CLAUDE.md) live under
`$SPEECHRL_DATA_DIR/derived/meeting-minutes/pprompt-sweep/runs/2026-08-18-pprompt-sweep/`:

- `{arm}-responses.jsonl` for each of the 14 arms — one JSON object per request carrying
  `request_id`, `arm`, `meeting_id`, `slice_index`, `audio_relpath`, `audio_seconds`, `roster`,
  `content_sha256`, `text`, `usage`, `attempts`. `server.log` and all 14 JSONLs are fingerprinted
  in `run-dir-artefacts.sha256`.

Operational flags for that mission, derived from counters only — no reply was read:

1. **Eight truncated replies**, all on the SAME slice `TS3004b-slice0000` (the slice whose A-grid
   reply also hit the cap on the P-ATTR flight), one per arm in T1-A2, T1-A3, T2-A2, T2-A3, T3-A2,
   T3-A3, T4-A2, T4-A3: exactly 1,024 completion tokens. Every A1 cell and both corrupt arms
   finished under the cap everywhere (max 537 completion tokens). Treat those eight records as
   truncated rather than short.
2. **No empty replies anywhere** (min reply length 22 chars; zero replies under 20 chars), so the
   meeteval empty-hypothesis assertion should not be reachable on this data.
3. T1's three cells render byte-identical requests (binding manifest, documented consequence of the
   registered 4×3 grid). Counter totals for T1-A2 and T1-A3 are identical to each other but differ
   from T1-A1's — same-request resends are not bit-deterministic on this server; the read mission
   should compare T1 cells knowing that.

## Files here

`runtime-identity.json` (server/model/binary identity + repo commit + binding pin) ·
`flight-summary.json` (per-arm counters, budgets, GPU accounting, featcache + encoding-line
evidence) · 14 × `{arm}-receipt.json` (FlightReceipt: server identity, full request ledger, budget
totals, content hash) · 14 × `{arm}-launcher.log` · `fly-wrapper.log` · `gpu-health.log` ·
`preflight.log` · `preflight-pytest.log` · `preflight-summary-only.log` · `teardown-shutdown.log` ·
`script-{env,serve,fly-all,gpu-sampler}.sh` (the wrapper scripts flown) ·
`run-dir-artefacts.sha256` · `MANIFEST.sha256`.
