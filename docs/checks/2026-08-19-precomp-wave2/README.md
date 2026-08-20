# PRECOMP wave-2 — pinned-diar + featcache production pass (2026-08-20) — **75/76, PARTIAL**

Registration: `docs/readiness/2026-08-19-precomp-preregistration.md` §2 wave-2 ("the
remaining usable-discovery meetings (~83)… night batch, resumable chunks").
Diarization adjudication: `docs/readiness/2026-08-19-diar-adjudication-TOOL-LOCKED-B.md`.
Predecessor: `docs/checks/2026-08-19-precomp-wave1/` (dev-18, COMPLETE 18/18).

This is a PRODUCTION pass, not a probe: it computes reusable derived assets so every
later experiment is decode-only. It renders **no verdicts** — every number below is
descriptive.

**Outcome.** All 76 roster meetings were attempted; **75 produced complete derived
assets**. One meeting, `ES2005d`, was refused fail-closed by the slicer's own transport
bound check and produced no slices — see *The one refused meeting* below. Every
registered ceiling held with wide margin.

## Roster — 76, not the registration's "~83"

The registration's "~83" was an estimate; the machine-derived roster is **76**.
`precomp.roster.wave2_roster` intersects two independent axes and then removes wave-1:

- `usable_discovery_exposable_roster()` = 87 meetings (usable-discovery MeetingQA
  questions **and** an audio-exposable `MeetingRole`);
- minus the 11 members of the frozen dev-18 that also carry usable-discovery
  questions → **76**.

`87 − 11 = 76`. The two axes are deliberately not collapsed, so the count is not
`87 − 18`. Cross-checks recorded in `preflight.log`: zero overlap with dev-18, all 76
carry the `glossary-discovery` role, `assert_wave_roster_admissible` passed for all 76,
and no eval-16 / `held-out-*` meeting appears. No roster meeting was missing audio.

## Identity (hash-verified preflight, `preflight.log`)

Byte-identical pins to wave-1 — same llama.cpp build, same q4km GGUF pair, same pinned
Arm B diar tool, same warm per-dataset feature cache `ami-q4km`. Full detail in
`runtime-identity.json`; all five preflight hash checks passed (`hash-pin fail flag: 0`).

| component | pin |
|---|---|
| llama.cpp build | `5d9dfcb58ea860295da8fc93c7b5bed9e2c71151` (clean tree), binary `097c96ec…c68` |
| core GGUF | `Qwen3-Omni-30B-A3B-Instruct-Q4_K_M.gguf` `0751c279…6d` |
| mmproj | `mmproj-…-bf16.gguf` `f0dfe825…83` |
| diar binary | `nemo-speech.cpp-cuda-q8_0` `1a3e3f4f…78` |
| diar checkpoint | `diar_streaming_sortformer_4spk-v2.q8_0.gguf` `0679cfeb…8d` |
| arm-config | `608230d6…58` (Arm B, TOOL-LOCKED(B)) |
| study repo | `3d5e2e12d32fef151627b588e9da11bad7bc7d49`, clean at launch |
| server flags | `-c 49152 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0` |

Preflight `pytest`: **1537 passed, 6 skipped**.

## How it flew — five short invocations

The harness reaps a background task at ~60 min, so the wave ran as repeated short
invocations rather than one long one. Each invocation started its **own** `llama-server`
as a child process (a child dies with its wrapper, so even a reap cannot orphan a server
holding VRAM), ran one `run_precomp.py --wave 2 --resume --stop-file …` invocation, tore
the server down, and exited. The runner's `--stop-file` hook (commit `e4e18c4`) is checked
before every meeting, and `PrecompBudget.precharge` re-derives wave-cumulative usage from
the receipts already on disk at every startup — so the registered **wave** ceilings were
enforced fail-closed across all five processes, with an operator-side `budget_ledger.py`
cross-check after each one. Receipts are fsynced per meeting, so a reap would have cost at
most one in-flight meeting.

| inv | n | meetings | encode calls | server start s | runner wall s | wrapper wall s | state | runnable remaining |
|---|---|---|---|---|---|---|---|---|
| 1 | 12 | ES2002a…ES2007d | 424 | 10 | 2013 | 2044 | SLICE-DONE | 65 |
| 2 | 21 | ES2008a…ES2015d | 789 | 16 | 2758 | 2778 | SLICE-DONE | 43 |
| 3 | 19 | ES2016a…IS1007a | 698 | 10 | 2722 | 2781 | SLICE-DONE | 24 |
| 4 | 15 | IS1007b…TS3008d | 745 | 15 | 2758 | 2826 | SLICE-DONE | 9 |
| 5 | 9 | TS3009b…TS3012d | 407 | 47 | 2357 | 2421 | WAVE-COMPLETE | 0 |

Per-invocation meeting lists: `meetings-2.txt` … `meetings-5.txt`. Full per-meeting
table: `per-meeting-table.txt`. No invocation was reaped; every one reported `FLY-DONE`
and a clean `llama-server stopped`.

## Budget spend against the registered wave-2 ceilings

| axis | used | ceiling | used |
|---|---|---|---|
| encode calls | 3,063 | 4,500 | 68.1 % |
| encode-warm GPU-h | 1.313 | 8.0 | 16.4 % |
| diar GPU-h | 0.192 | 2.0 | 9.6 % |
| CPU cutting wall-h | 0.423 | *(none registered)* | n/a |

`breaches: []` at every checkpoint (`budget-ledger-final.json`). Wall clock: diar 2,976.0 s,
encode 6,905.1 s, cutting 1,523.0 s. Total wave wall ≈ 3.6 h across the five wrappers.

Encode throughput ran ≈ 3.4× faster per call than wave-1 (≈ 1.9 s/call vs ≈ 6.7 s/call).
The difference is the GPU clock state, not the workload: wave-1 spent part of its run at a
depressed SM clock, whereas this wave held the 1200 MHz floor throughout
(`gpu-health-*.log`). Samples between 600–1740 MHz under `SW Power Cap` at ~68 W are the
laptop 5090's normal power-limited behaviour, not the pathological stuck-P-state case.

## Descriptive metrics (prereg §5 — no verdicts)

- turns: tool 46,167 / oracle 38,806
- slices: tool 1,525 / oracle 1,538; per-meeting count delta min −3, median 0, max +2
  (sum −13)
- boundary displacement, per-meeting medians: min 0.6 s, median 22.0 s, max 44.3 s
- boundary displacement, per-meeting maxima: min 12.4 s, median 46.5 s, max 194.0 s
- feature cache added by wave-2: **37,747 entries / 31,052,388,144 bytes (28.92 GiB)**,
  taking `ami-q4km` from 14,324 entries to **52,071 entries / 42,538,636,912 bytes
  (39.62 GiB)**

The positional packing-change fraction stays RETIRED as saturated, per the smoke read.

## The one refused meeting — `ES2005d`

`ES2005d`'s pinned-diar turns produce a transport slice of **120.00000000000011 s**
against the hard cap `TRANSPORT_SLICE_MAX_S = 120.0`, so
`slicer.TransportBoundViolation` refused the whole plan and the meeting produced no
slices. The overrun is 1.1 × 10⁻¹³ s — pure floating-point accumulation, not a real
over-length slice. `src/meeting_minutes_agent/chunking/slicer.py:248` compares with a
strict `>` and no epsilon tolerance, so a slice landing exactly on the cap is refused.

**The guard behaved correctly**: it is fail-closed, it fired before any audio was sent,
and nothing the transport would have refused was transmitted. The receipt
(`receipts/ES2005d-receipt.json`) carries the full error and the diar contact that
preceded it; its diar time is counted in the ledger above.

**No repair was attempted in this pass, deliberately.** Slicer constants and algorithm are
a registered cache-invalidation axis (prereg §1): changing them would cold-start every
slice already built and split the wave across two slicer identities. The defect is handed
to the coordinator instead. It is deterministic — the diar tool is deterministic, so the
turns and therefore the plan are too — so `ES2005d` will fail identically until the slicer
is repaired, and any repair must be sequenced as its own change with its own
re-computation of the affected meetings.

### Deviation recorded for coordinator review — explicit `--meetings` from invocation 2 on

Invocations 2–5 used `script-fly2.sh`, which computes the meeting list itself and passes
it as `--meetings` instead of relying on the default roster. Reason: `already_done`
requires `ok: true`, so a plain `--resume` would have re-run `ES2005d`'s ~40 s diar
contact on **every** later invocation, spent real GPU time, and then overwritten its own
receipt — which would also have made the receipt-derived ledger **under-count** the diar
time actually spent. Excluding a structurally-refused meeting after its first attempt
keeps wave accounting exact. The list is derived from the receipts themselves (never a
hand-typed id: any receipt with `ok: false` whose error names `TransportBoundViolation`),
and the fail-closed exposure gate still runs unconditionally on the resulting list —
`assert_wave_roster_admissible` is applied by the runner to an operator-supplied
`--meetings` override exactly as it is to the default roster.

## Yield

The coordinator's stop-file appeared at **05:26:57Z**, during invocation 5. The wrapper's
yield bridge observed it within 15 s and mirrored it into the invocation's own stop-file;
the runner then stopped at the next meeting boundary. The two meetings already in flight
(`TS3012b`, `TS3012d`) completed and were receipted, which exhausted the roster — so the
yield cost no work. The coordinator's file was **read only, never created or deleted** by
this operator; clearing it is the coordinator's call.

## Discipline

- Encode-warm generation text was **never read**: the runner discards it and the receipts
  carry counts only. The contact exists solely to populate the feature cache.
- NXT oracle turns fed the **slicer only** — boundaries and labels, never a prompt.
  Scoring-side conventions unchanged; no gold in any prompt path.
- eval-16 and every `held-out-*` meeting were untouched; the exposure gate was applied
  unconditionally to every meeting list, default or operator-supplied.
- Derived bytes (RTTM, slice WAVs, feature-cache entries) stay on the data root under
  `$SPEECHRL_DATA_DIR/derived/meeting-minutes/precomp`. Only hashes, counts, and manifests
  are committed (prereg §5). Both counts below are for that **shared** derived root, so
  they span wave-1 and wave-2 together: `rttm-artefacts.sha256` carries **94** RTTMs
  (wave-1's 18 + wave-2's 76 — `ES2005d`'s diar contact *succeeded*, only its slice plan
  was refused, so it too has an RTTM), and `slice-wav-count.txt` reports **4,192** slice
  WAVs.
- `server-errors.log` contains only five benign `W common_fit_params: … n_gpu_layers
  already set by user to 999, abort` warnings — one per invocation, emitted at model load
  because `-ngl 999` is explicit. No error, OOM, assert, or abort occurred in 421,832
  lines of server log.
- Per-contact logging throughout; every model contact carries its transport ledger under
  `transport-receipts/inv-*.json`.
- AMI CC BY 4.0.
- `wave-summary.json` is re-emitted over **all** receipts by `aggregate2.py`, because
  `build_wave_summary` sees only the outcomes of the process that wrote it and `--resume`
  skips are not outcomes.

## Files

`receipts/` — 76 per-meeting receipts (75 `ok: true`). `wave-summary.json` — the wave
artefact over all of them. `transport-receipts/inv-{1..5}.json` — per-invocation transport
ledgers. `runtime-identity.json` — hash-pinned runtime identity. `preflight.log`,
`fly-{1..5}.log`, `progress-{1..5}.log`, `runner-{1..5}.log`, `gpu-health-{1..5}.log`,
`server-errors.log` — operational logs. `per-meeting-table.txt`,
`budget-ledger-final.json`, `roster-state.json`, `readme-stats.txt` — descriptive reads.
`meetings-{2..5}.txt` — per-invocation computed lists. `script-*.sh`, `*.py` — the
operator scripts and helpers that drove the pass. `MANIFEST.sha256` — hashes of every
file here.
