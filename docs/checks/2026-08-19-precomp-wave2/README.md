# PRECOMP wave-2 — pinned-diar + featcache production pass (2026-08-20) — **76/76, COMPLETE**

Registration: `docs/readiness/2026-08-19-precomp-preregistration.md` §2 wave-2 ("the
remaining usable-discovery meetings (~83)… night batch, resumable chunks").
Diarization adjudication: `docs/readiness/2026-08-19-diar-adjudication-TOOL-LOCKED-B.md`.
Predecessor: `docs/checks/2026-08-19-precomp-wave1/` (dev-18, COMPLETE 18/18).

This is a PRODUCTION pass, not a probe: it computes reusable derived assets so every
later experiment is decode-only. It renders **no verdicts** — every number below is
descriptive.

**Outcome.** All 76 roster meetings were attempted; **all 76 produced complete derived
assets.** The first five invocations below landed 75/76 PARTIAL: one meeting,
`ES2005d`, was refused fail-closed by the slicer's own transport-bound check and
produced no slices. A sixth, supplemental invocation completed the wave after a
coordinator-directed repair (commit `baaf41c`, `fix(chunking): float-epsilon tolerance
at the transport bound`) landed a float-accumulation tolerance at that check — and, once
that plan-level refusal cleared, at a second, previously-latent gate one call-site
downstream in `client/transport.py` that shared the exact same defect shape. See *The
one supplemented meeting — ES2005d* below for the full account, including the aborted
first attempt that discovered the second gate. Every registered ceiling held with wide
margin, including after the supplement.

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
| study repo | `3d5e2e12d32fef151627b588e9da11bad7bc7d49` (invocations 1-5), clean at launch |
| server flags | `-c 49152 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0` |

Preflight `pytest`: **1537 passed, 6 skipped**.

**Invocation 6 (the ES2005d supplement) ran at study repo commit
`baaf41c394db340ddf4c4c16ae190b6c24f459c5`**, clean at launch, `pytest`: **1550
passed, 6 skipped**.
Every other pin above (llama.cpp build, both GGUFs, diar binary/checkpoint,
arm-config, server flags) is byte-identical to invocations 1-5 — only
`src/meeting_minutes_agent/chunking/{constants,slicer}.py` and
`src/meeting_minutes_agent/client/transport.py` changed between the two commits, and
that change is scoped to the transport-bound acceptance check only (no packing/
slicing algorithm, no other constant): every one of the other 75 meetings' plans and
slices are geometrically identical regardless of which of the two commits computed
them, which the unchanged `tool` slice-plan `content_hash` for `ES2005d` itself
across both attempts (`e8de98e0…51`) also demonstrates directly.

## How it flew — six short invocations (plus one aborted attempt)

The harness reaps a background task at ~60 min, so the wave ran as repeated short
invocations rather than one long one. Each invocation started its **own** `llama-server`
as a child process (a child dies with its wrapper, so even a reap cannot orphan a server
holding VRAM), ran one `run_precomp.py --wave 2 --resume --stop-file …` invocation, tore
the server down, and exited. The runner's `--stop-file` hook (commit `e4e18c4`) is checked
before every meeting, and `PrecompBudget.precharge` re-derives wave-cumulative usage from
the receipts already on disk at every startup — so the registered **wave** ceilings were
enforced fail-closed across all seven processes (five original invocations plus
invocation 6's two attempts), with an operator-side `budget_ledger.py` cross-check
after each one. Receipts are fsynced per meeting, so a reap would have cost at most one
in-flight meeting. Invocations 1-5 landed the original 75/76 PARTIAL pass, in one
continuous night-batch session; invocation 6 is a separate, later supplemental session
that ran after the coordinator-directed repair below, driven by its own wrapper
(`script-fly6.sh`) rather than `script-fly2.sh`'s computed-list pattern.

| inv | n | meetings | encode calls | server start s | runner wall s | wrapper wall s | state | runnable remaining |
|---|---|---|---|---|---|---|---|---|
| 1 | 12 | ES2002a…ES2007d | 424 | 10 | 2013 | 2044 | SLICE-DONE | 65 |
| 2 | 21 | ES2008a…ES2015d | 789 | 16 | 2758 | 2778 | SLICE-DONE | 43 |
| 3 | 19 | ES2016a…IS1007a | 698 | 10 | 2722 | 2781 | SLICE-DONE | 24 |
| 4 | 15 | IS1007b…TS3008d | 745 | 15 | 2758 | 2826 | SLICE-DONE | 9 |
| 5 | 9 | TS3009b…TS3012d | 407 | 47 | 2357 | 2421 | WAVE-COMPLETE | 0 |
| 6a (aborted) | 1 | ES2005d | 0 | 15 | 110 | 137 | SLICE-DONE (refused at transport) | 1 |
| 6b (final) | 1 | ES2005d | 36 | 22 | 123 | 157 | WAVE-COMPLETE | 0 |

Per-invocation meeting lists: `meetings-2.txt` … `meetings-5.txt` (invocation 6 has an
explicit single-meeting target, `ES2005d`, in its own wrapper script rather than a
computed list file). Full per-meeting table: `per-meeting-table.txt`. No invocation was
reaped; every one reported `FLY-DONE` and a clean `llama-server stopped` — including
6a, whose "abort" is the transport-layer refusal described below being reported (a
controlled outcome, not a crash or a reap).

Total wrapper wall across all seven server starts (five original invocations plus
invocation 6's two attempts): 2044+2778+2781+2826+2421+137+157 = 13,144 s ≈ **3.65 h**.

`readme_stats.py`'s own table (`readme-stats.txt`, archived verbatim, tool output not
hand-edited) shows invocation 6 as `wrapper wall s: None`, `state: NO-FLY-DONE`,
`remaining after: ?` — a cosmetic artefact, not a real gap: `script-fly6.sh`'s
`FLY-DONE` line prints an extra `todo=[...]` token
(`remaining=0 todo=[] wall=157s`) that `readme_stats.py`'s regex, written for
`fly.sh`/`fly2.sh`'s `remaining=<n> wall=...s` shape, does not match. The real values
(`state=WAVE-COMPLETE`, `wall=157s`) are in `fly-6.log` and `progress-6.log` directly,
and are what the invocation table above and the wave-totals/descriptive-distribution
numbers throughout this README use — the wave-totals and descriptive-distribution
halves of `readme_stats.py`'s output are unaffected (`budget_ledger.load_receipts`
reads receipts, not progress-log text).

## Budget spend against the registered wave-2 ceilings

Final totals, after invocation 6 (`budget-ledger-final.json`, re-derived natively from
all 76 receipts by `PrecompBudget.precharge` at every invocation start — never
hand-summed):

| axis | used | ceiling | used |
|---|---|---|---|
| encode calls | 3,099 | 4,500 | 68.9 % |
| encode-warm GPU-h | 1.322 | 8.0 | 16.5 % |
| diar GPU-h | 0.192 | 2.0 | 9.6 % |
| CPU cutting wall-h | 0.425 | *(none registered)* | n/a |

`breaches: []` at every checkpoint. Wall clock: diar 2,966.0 s, encode 6,978.2 s,
cutting 1,528.7 s. Total wrapper wall ≈ 3.65 h across the six invocations (seven server
starts; see the invocation table above).

The pre-supplement (75/76) totals were: encode calls 3,063/4,500 (68.1 %), encode-warm
1.313 GPU-h (16.4 %), diar 0.192 GPU-h (9.6 %, `ES2005d`'s own first diar contact
already counted, since diarization succeeded before the slice plan was refused),
cutting 0.423 wall-h. The supplement (invocation 6, both attempts together) added 36
encode calls (all in 6b; 6a never reached the encode-warm phase) and two more diar
contacts for `ES2005d` (one per attempt, `--force`-regenerating its RTTM each time).
The diarizer is deterministic, so both reproduced the byte-identical RTTM already on
disk — confirmed by `rttm-artefacts.sha256` staying at 94 entries with unchanged
hashes throughout. `diar_gpu_seconds_used` rounds to the same 0.192 GPU-h before and
after at three decimal places; the un-rounded ledger values (`budget-ledger-final.json`
vs the invocation-5 land) carry the small increase from the two extra contacts.

Encode throughput ran ≈ 3.4× faster per call than wave-1 (≈ 1.9 s/call vs ≈ 6.7 s/call).
The difference is the GPU clock state, not the workload: wave-1 spent part of its run at a
depressed SM clock, whereas this wave held the 1200 MHz floor throughout
(`gpu-health-*.log`). Samples between 600–1740 MHz under `SW Power Cap` at ~68 W are the
laptop 5090's normal power-limited behaviour, not the pathological stuck-P-state case.

## Descriptive metrics (prereg §5 — no verdicts)

Final, over all 76 meetings (`readme_stats.py`, re-run after invocation 6 — never
hand-summed):

- turns: tool 46,727 / oracle 39,291
- slices: tool 1,543 / oracle 1,556; per-meeting count delta min −3, median 0, max +2
  (sum −13)
- boundary displacement, per-meeting medians: min 0.6 s, median 22.1 s, max 44.3 s
- boundary displacement, per-meeting maxima: min 12.4 s, median 46.5 s, max 194.0 s
- feature cache added by wave-2 (receipt-attributed, 75 original meetings plus
  `ES2005d`'s successful supplement): **37,856 entries / 31,141,846,528 bytes
  (29.00 GiB)**, taking `ami-q4km` from 14,324 entries to **52,180 entries**
  receipt-attributed
- **actual on-disk cache after invocation 6: 52,529 entries / 42,915,320,592 bytes
  (39.97 GiB)** (`runtime-identity.json`) — 349 entries / 349 more than the
  receipt-attributed 52,180, reconciled exactly by the 349 entries / 287,225,296 bytes
  invocation 6a's aborted attempt wrote before the transport-layer refusal struck: real
  GPU work whose *receipt* was discarded on the exception (`n_calls: 0` in that
  attempt's own receipt, since encode-warm never gets attributed on a mid-phase
  failure), but whose content-addressed cache *entries* persisted on disk exactly as
  every other feature-cache write does — harmless and reusable, never double-counted
  in the wave's own accounting because 6b's own encode-warm calls each still populate
  or hit the cache independently of what a previous, discarded attempt wrote for the
  same content hash.

Pre-supplement (75/76) figures were: turns tool 46,167 / oracle 38,806; slices tool
1,525 / oracle 1,538 (same per-meeting delta distribution, `ES2005d` contributed no
slices to either count while refused); feature cache added 37,747 entries /
31,052,388,144 bytes (28.92 GiB), `ami-q4km` at 52,071 entries / 42,538,636,912 bytes
(39.62 GiB).

The positional packing-change fraction stays RETIRED as saturated, per the smoke read.

## The one supplemented meeting — `ES2005d`

### Original account (invocations 1-5, PARTIAL landing)

`ES2005d`'s pinned-diar turns produce a transport slice of **120.00000000000011 s**
against the hard cap `TRANSPORT_SLICE_MAX_S = 120.0`, so
`slicer.TransportBoundViolation` refused the whole plan and the meeting produced no
slices. The overrun is 1.1 × 10⁻¹³ s — pure floating-point accumulation, not a real
over-length slice. `src/meeting_minutes_agent/chunking/slicer.py:248` (pre-repair)
compared with a strict `>` and no epsilon tolerance, so a slice landing exactly on the
cap was refused.

**The guard behaved correctly**: it is fail-closed, it fired before any audio was sent,
and nothing the transport would have refused was transmitted. This original,
slicer-level-refusal receipt is no longer the working-tree copy (invocation 6
overwrote `receipts/ES2005d-receipt.json` with the final success) — its exact bytes
are Git blob history at the PARTIAL landing commit:
`git show b26b9be:docs/checks/2026-08-19-precomp-wave2/receipts/ES2005d-receipt.json`
(CLAUDE.md: Git blob bytes are the evidence hash authority, not working-tree bytes).
It carries the full error and the diar contact that preceded it; its diar time was
counted in the pre-supplement ledger.

**No repair was attempted in that pass, deliberately.** Slicer constants and algorithm
are a registered cache-invalidation axis (prereg §1): changing them would cold-start
every slice already built and split the wave across two slicer identities. The defect
was handed to the coordinator instead. It is deterministic — the diar tool is
deterministic, so the turns and therefore the plan are too — so `ES2005d` would fail
identically until the slicer was repaired, and any repair had to be sequenced as its
own change with its own re-computation of the affected meeting.

### The repair and the supplement (invocation 6)

The coordinator-directed repair landed as `fix(chunking): float-epsilon tolerance at
the transport bound` (commit `baaf41c394db340ddf4c4c16ae190b6c24f459c5`): a named
`TRANSPORT_SLICE_MAX_EPSILON_S = 1e-9` constant (`chunking/constants.py`) widens
*only* the acceptance comparison in `_assert_transport_bound` to
`TRANSPORT_SLICE_MAX_S + TRANSPORT_SLICE_MAX_EPSILON_S` — no packing/snap/gap-tiling
algorithm changed, and `TRANSPORT_SLICE_MAX_S` itself is untouched, so every plan the
strict pre-repair comparator already accepted stays byte-identical (regression-guard
test in `tests/unit/chunking/test_slicer.py`; the `ES2005d` **tool** slice-plan
`content_hash` — the one plan not affected by the edge case — is in fact identical
across both invocation-6 attempts: `e8de98e00479b65a56d6dfced89a8f352c033e62ed29a83c
32f865c18e051f04`, direct production evidence of the acceptance-tolerance-only
invariant, not just a synthetic test).

**Invocation 6a (aborted): a second, previously-latent gate.** With only the slicer
repaired, `ES2005d`'s plan built successfully — but `client/transport.py`'s
`LlamaServerTransport.request` carries its **own**, separate strict `>` check on
`audio_seconds` (the slice-bounds guard the module docstring describes, checked
before any byte is read). `audio_seconds` for a request is a slice's own `end - start`
resolved via `make_audio_chunk_resolver`, so it inherits the identical float-
accumulation residue — and this gate refused the identical shape one call-site
downstream: `TransportError: request 'precomp-w2-oracle-ES2005d-slice0010' carries
audio_seconds=120.00000000000011, which exceeds this transport's
max_audio_seconds_per_request=120.0`. This gate had never fired for any other meeting
in the wave (or in wave-1) because no other meeting's plan carries this exact
float-accumulation shape; it was invisible until the slicer's own refusal, which used
to fire first, was repaired. The diar contact in this attempt succeeded (`--force`
re-ran it; deterministic, reproduced the byte-identical RTTM already on disk) and 349
feature-cache entries were written before the exception (real GPU work; harmless,
content-addressed, never re-read as a receipt outcome — see the descriptive-metrics
reconciliation above). The full first-attempt artefacts (`fly-6.log`, `progress-6.log`,
`runner-6.log`, `gpu-health-6.log`, the discarded receipt, and the invocation
transport ledger) are archived under `invocation-6-attempt1-transport-bound-
discovery/` rather than silently discarded, because the discovery itself is real
audit-trail content.

**The same fix, reused.** `client/transport.py`'s check now compares against
`self._config.max_audio_seconds_per_request + TRANSPORT_SLICE_MAX_EPSILON_S` — the
identical shared constant, same acceptance-tolerance-only invariant, its own
red-first test and regression guard in `tests/unit/client/test_transport.py`. Both
fixes landed in the same commit (`baaf41c`) since they are the same defect class
discovered in one continuous repair session, not two independent changes.

**Invocation 6b (final): success.** `ES2005d` ok=`true`: diar wall 29.9 s, 18 tool +
18 oracle slices, 36 encode-warm calls (73.1 s), 109 new feature-cache entries
(89,458,384 bytes). `roster-state.json` reports `COMPLETE`, `remaining_n: 0`. Wave-2
is **76/76**.

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
  (wave-1's 18 + wave-2's 76 — `ES2005d`'s diar contact *succeeded* on every one of its
  three attempts across invocations 1, 6a, and 6b, and the deterministic diarizer
  reproduced the byte-identical RTTM each `--force` re-run, so the count and every hash
  are unchanged by the supplement), and `slice-wav-count.txt` reports **4,228** slice
  WAVs (4,192 at the PARTIAL landing, +36 for `ES2005d`'s 18 tool + 18 oracle slices).
- `server-errors.log` contains only seven benign `W common_fit_params: … n_gpu_layers
  already set by user to 999, abort` warnings — one per invocation-1-5 (five) plus one
  per invocation-6 server start (two, since 6a and 6b each started their own
  `llama-server`) — emitted at model load because `-ngl 999` is explicit. No error, OOM,
  assert, or abort occurred anywhere in the accumulated 424,635 lines of server log
  (421,832 from invocations 1-5, 2,803 more from invocation 6).
- Per-contact logging throughout; every model contact carries its transport ledger under
  `transport-receipts/inv-*.json`.
- AMI CC BY 4.0.
- `wave-summary.json` is re-emitted over **all** receipts by `aggregate2.py`, because
  `build_wave_summary` sees only the outcomes of the process that wrote it and `--resume`
  skips are not outcomes.

## Files

`receipts/` — 76 per-meeting receipts, **all 76 `ok: true`** (after invocation 6;
`ES2005d`'s receipt is the invocation-6b outcome — its slicer-refusal predecessor lives
only in Git blob history, see *The one supplemented meeting* above).
`wave-summary.json` — the wave artefact over all of them, re-aggregated after
invocation 6. `transport-receipts/inv-{1..6}.json` — per-invocation transport ledgers
(`inv-6.json` is invocation 6b's, the successful attempt; 6a's own transport ledger is
archived separately, see below). `runtime-identity.json` — hash-pinned runtime
identity, re-captured after invocation 6 (records both study-repo commits across the
wave, `dirty_paths` at capture time). `preflight.log`, `fly-{1..6}.log`,
`progress-{1..6}.log`, `runner-{1..6}.log`, `gpu-health-{1..6}.log`,
`server-errors.log` — operational logs (the `-6` files are invocation 6b, the
successful attempt). `invocation-6-attempt1-transport-bound-discovery/` — the aborted
invocation-6a attempt in full: its own `fly-6.log`, `progress-6.log`, `runner-6.log`,
`gpu-health-6.log`, its discarded `ES2005d` receipt
(`ES2005d-receipt-attempt1-transport-refusal.json`), and its transport ledger
(`transport-receipt-inv-6-attempt1.json`) — preserved because the transport-layer gate
it discovered is real audit-trail content, not noise to discard. `per-meeting-table.txt`,
`budget-ledger-final.json`, `roster-state.json`, `readme-stats.txt` — descriptive reads,
all re-emitted after invocation 6 (`roster-state.json` now reports `COMPLETE`).
`meetings-{2..5}.txt` — per-invocation computed lists (invocation 6 used an explicit
single-meeting target instead, `script-fly6.sh`). `script-*.sh` (including
`script-fly6.sh` and `script-land6.sh`), `*.py` — the operator scripts and helpers that
drove the pass, including the supplement. `MANIFEST.sha256` — hashes of every file
here, regenerated last, over the final 76/76 set.
