# P-ATTR capability smoke — flight record (2026-08-18)

**This repository's first core contact.** Three arms, 498 requests, zero failures. Flight
operations only: no reply text was read, and nothing here scores anything. Scoring is a separate
mission that consumes the reply records named below.

Registration: `docs/readiness/2026-08-18-g1-preregistration-draft.md` §0 + its BOUND block.
Frozen manifest: `configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json` (schema 1.0.0,
seed 20260818, meetings ES2011b / IS1008b / IS1008d / TS3004b, asr-eval role).
Code commit flown: `9ad5d956a78eb92f436e2f1baee4323f20c92b74`, clean tree (each receipt records
`git.dirty = false` independently).

## Pre-flight

- **Manifest integrity**: all **474** pinned files re-hashed from disk bytes — 24 slices
  (2,345.373 s, longest 110.347 s, inside the 120 s transport guard) and 450 turn clips
  (2,138.579 s). Zero missing, zero mismatched. WAV durations agree with the manifest's own
  seconds to the millisecond. `transport_bound_violations` = 0.
- **Counts** confirmed independently by the launcher's `--summary-only` before the server was
  started: A-grid 24 / A-free 24 / A-turn 450 = **498**.
- **Feature cache**: a NEW per-dataset directory `/home/chao/feat-cache/ami-q4km`
  (`LLAMA_MTMD_FEAT_CACHE_DIR`, the name the llama.cpp mtmd patch reads), created COLD at 0
  entries. The `q4km`, `slurp-q4km` and `audio2tool-q4km` caches were never touched — verified by
  mtime after teardown.
- **GPU**: idle P8/180 MHz, 444 MiB used, no orphan `llama-server`.

## Server identity

Recorded in `runtime-identity.json`; all three hashes match the pins the SAEA study flew against.

| item | value |
|---|---|
| binary | `/home/chao/llama.cpp-featcache/build/bin/llama-server` (17,920 B) |
| binary sha256 | `097c96ec5a3f576f378d4d5e103928bf070647fdcc1f015eacb839503e121c68` |
| build commit | `5d9dfcb58ea860295da8fc93c7b5bed9e2c71151` (clean tree, `version: 5 (5d9dfcb58)`) |
| model | `Qwen3-Omni-30B-A3B-Instruct-Q4_K_M.gguf`, sha256 `0751c279…066d` |
| mmproj | `mmproj-Qwen3-Omni-30B-A3B-Instruct-bf16.gguf`, sha256 `f0dfe825…2883` |
| serving args | `-c 49152 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0`, `127.0.0.1:8080` |
| decoding | `temperature 0`, `seed 20260818`, `max_tokens` 1024 (slice arms) / 512 (A-turn), client timeout 420 s |

Model load to `/health` 200 took ~14 s (page cache warm from the identity hashing pass); resident
VRAM 23,594 MiB of 24,463 MiB.

## What flew

| arm | requests | errors | retries | wall | mean latency | metered audio |
|---|---|---|---|---|---|---|
| A-grid | 24 / 24 | 0 | 0 | 140 s | 4.78 s | 2,345.373 s |
| A-free | 24 / 24 | 0 | 0 | 119 s | 4.25 s | 2,345.373 s |
| A-turn | 450 / 450 | 0 | 0 | 258 s | 0.44 s | 2,138.579 s |
| **total** | **498 / 498** | **0** | **0** | **517 s** | — | **6,829.326 s** |

Order flown: A-grid → A-free → A-turn, sequentially against one slot.

## Budget vs the registered ceilings

| ceiling | registered | used | headroom |
|---|---|---|---|
| requests | ≤ 550 | 498 | 52 |
| metered audio-seconds | ≤ 7,500 | 6,829.326 | 670.674 |
| GPU-hours | ≤ 2.0 | 0.115 (sum of request latency) / 0.096 (utilisation-integrated) / ~0.2 (server-resident wall) | ≥ 1.8 |

Per-arm `CallBudget` caps were set below the global ceiling and were never approached
(A-grid/A-free 24 of 26 calls, A-turn 450 of 470).

## Feature cache behaviour (AMI cold → warm)

0 → **879 entries / 502 MB**. A-grid encoded the 24 slices cold (0 → 302 entries). A-free re-flew
the **same** slice WAVs and the cache stayed at exactly 302 entries with the server log's
`encoding` line count unchanged — a clean cache-hit proof, and the reason A-free ran 21 s faster
than A-grid on identical audio. A-turn's 450 clips are distinct audio and encoded cold
(302 → 879).

## GPU health

Sampled every 30 s (`gpu-health.log`). Clocks sat at 232 MHz / P2–P4 under load with 87–96 %
utilisation, `clocks_throttle_reasons.active = 0x4`, peak 62 °C, returning to 180 MHz/P8 between
arms. This is the known benign reading on this machine: the failure mode it can indicate is a
*slowdown*, and there was none (4–5 s per 100 s slice; 0.44 s per turn clip), so no clock override
was applied. The single `error`-matching line in the server log is the startup warning
`common_fit_params: failed to fit params to free device memory: n_gpu_layers already set by user
to 999` — expected with `-ngl 999`, not a fault. Teardown returned the GPU to 252 MiB.

## Handoff to the scoring mission

Reply records (raw traces — deliberately NOT in Git, per CLAUDE.md) live under
`$SPEECHRL_DATA_DIR/derived/meeting-minutes/pattr-smoke/runs/2026-08-18-pattr-smoke/`:

- `a-grid-responses.jsonl`, `a-free-responses.jsonl`, `a-turn-responses.jsonl` — one JSON object
  per request carrying `arm`, `meeting_id`, `slice_index`, `turn_index`, `known_speaker`,
  `audio_relpath`, `audio_seconds`, `template_id`, `text`, `usage`, `attempts`. That is exactly
  the metadata `probes/pattr_scoring.py` needs to rebuild per-speaker hypothesis streams
  (A-turn attribution stays by construction: `known_speaker` comes from the manifest, never from
  a reply).
- `server.log` and the three JSONLs are fingerprinted in `run-dir-artefacts.sha256`.

Two operational flags for that mission, both derived from counters only — no reply was read:

1. **One truncated reply**: `pattr-grid-TS3004b-slice0000` returned exactly 1,024 completion
   tokens, i.e. it hit the generation cap. Every other request finished well inside it (A-free max
   485, A-turn max 167). Treat that one record as truncated rather than as a short answer. The cap
   is what kept a single runaway generation from consuming the GPU-hour ceiling; it was introduced
   with the launcher patch, not by the registration.
2. **No empty replies anywhere** (min reply length: A-grid 87, A-free 345, A-turn 2 characters),
   so the meeteval empty-hypothesis assertion `pattr_scoring.score_arm` documents should not be
   reachable on this data. A-turn replies are short by nature (median 29 characters; 183 of 450
   under 20) because the median turn clip is a few seconds long.

## Files here

`runtime-identity.json` (server/model/binary identity + repo commit) · `flight-summary.json`
(per-arm counters, budgets, GPU accounting) · `{a-grid,a-free,a-turn}-receipt.json` (FlightReceipt:
server identity, full request ledger, budget totals, content hash) ·
`{a-grid,a-free,a-turn}-launcher.log` · `gpu-health.log` · `run-dir-artefacts.sha256` ·
`MANIFEST.sha256`.
