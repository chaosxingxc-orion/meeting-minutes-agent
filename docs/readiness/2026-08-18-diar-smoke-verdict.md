# DIAR-SMOKE — verdict of the registered one-shot read (2026-08-19)

The registered one-shot read of the flight in `docs/checks/2026-08-18-diar-smoke-flight/`
(12/12 contacts, both arms x six dev-18 Mix-Headset meetings).
Registration: `2026-08-18-diar-smoke-preregistration.md` (prereg). Scoring path:
`probes/diar_smoke_scoring.py` via `scripts/diar_smoke_read.py` at study commit `5a762cb`,
executed exactly once (exit 0, 2026-08-19T08:29:41Z). Machine record and full tables:
`docs/checks/2026-08-18-diar-smoke-read/` (`verdict.json`, `report.txt`, two pre-read crash
logs). Zero model contact, zero tool contact, no new bytes; NXT reference consumed
scoring-side only.

## 0. The verdict — mechanical evaluation of prereg §5

**NO REGISTERED VERDICT FIRES.** The five prereg §5 clauses, evaluated mechanically in their
registered units (DER percentage points — the units of the thresholds 2.0 / 22.0 / 30.0 and
of the 18.8% pyannote anchor) over the pooled no-collar-with-overlap DER, leave this
outcome cell uncovered. Pooled DER(A) = **23.7341**, pooled DER(B) = **20.7405** (points,
no collar, with overlap; NIST component-sum pooling over all six meetings).

| # | clause (prereg §5) | condition | value | fires | margin |
|---|---|---|---|---|---|
| 1 | parity gate (B vs A) | \|DER(B) − DER(A)\| ≤ 2.0 | gap = 2.9936 | **NO** | **−0.9936** |
| 2 | TOOL-LOCKED(B) | parity AND DER(B) ≤ 22.0 | DER(B) = 20.7405 | **NO** | DER leg **+1.2595** (clears); parity leg fails |
| 3 | TOOL-LOCKED(A) | parity fails but DER(A) ≤ 22.0 | DER(A) = 23.7341 | **NO** | **−1.7341** |
| 4 | TOOL-USABLE-WITH-CAVEAT | best-arm DER in (22.0, 30.0] | best arm B = 20.7405 | **NO** | below the interval floor by 1.2595 |
| 5 | FALLBACK-NEEDED | best-arm DER > 30.0 or both arms fail load | 20.7405; 12/12 loads OK | **NO** | 9.2595 below the trigger |

The uncovered cell is exactly: **parity fails AND DER(B) ≤ 22.0 < DER(A) ≤ 30.0** — the
deployment-candidate arm B beat the lock threshold by 1.26 points, but the two-sided parity
gate fails (B is 2.99 points BETTER than A, exceeding the ±2.0 band), and clause 3 binds A
only when A itself qualifies (it misses by 1.73). Clause 4 covers only a best arm INSIDE
(22, 30] — note DER(A) = 23.7341 is in that interval, but the registered clause binds the
best arm, which is B. Clause 5's own registered condition does not hold. The prereg
declared the four outcome clauses as jointly covering; they are not, at precisely this cell.

Consequence: this read does NOT close G1 lock #3 by itself. The lock-#3 decision escalates
to the owner as a registered-gap adjudication (§7 below) with this document as the complete
evidence. No new verdict category is invented here.

### 0.1 As-run evaluator defect (recorded; does not affect the tables)

The shipped `evaluate_diar_smoke_verdict` was fed pooled DER as FRACTIONS
(`DerBreakdown.der`: 0.2074 / 0.2373) while its thresholds implement the prereg's
percentage points; every threshold comparison in the written `verdict.json` `clauses` block
is therefore trivially satisfied and its as-run `status` of `TOOL-LOCKED(B)` is **void** —
a unit-wiring defect (`run_read` should have passed `der_pct`), not a fired verdict. The
pooled component sums (miss/FA/confusion seconds), all per-meeting metrics, and every other
field of `verdict.json` are valid and are what this document reports. `verdict.json` is
kept exactly as written (one-shot read output; the file is evidence). The evaluator/test
repair is left to a coordinated follow-up, not patched after the fact by this read mission.

### 0.2 Read integrity (one-shot discipline)

Exactly one read executed to completion (exit 0); `verdict.json`/`report.txt` were written
once and not regenerated. Two prior attempts crashed BEFORE any metric was computed,
printed, or written (exit 1, `TransportBoundViolation` building TS3004d's ORACLE-turn slice
plan) and are preserved with full diagnosis in
`attempt-1-transportbound-crash.log` / `attempt-2-transportbound-crash.log`: attempt 1
(HEAD `b4a9326`) exposed missing audio-derived slicer inputs (fixed in `ec829d4`); attempt 2
(HEAD `ec829d4`) isolated the true root cause — the turn-aware slicer's interior
gap-midpoint tiling was not room-capped (fixed at the source in `5a762cb`, red-first test,
full suite 1126 passed; behavior-preserving for every previously-valid plan, so the frozen
P-ATTR manifest is unchanged by construction). The flown run directory was never modified
(flight `MANIFEST.sha256` verified 33/33 OK before attempt 1).

## 1. DER and JER, per meeting, per arm, both conventions

DER/JER in percent. `nc` = no collar, with overlap (the anchor convention); `c` = 0.25 s
collar, ignoring overlap. Optimal speaker mapping absorbs the emitter label conventions
(Arm A `speaker_0..3`, Arm B `speaker_1..4`) — e.g. ES2011a Arm B maps
`{A→speaker_1, B→speaker_4, C→speaker_3, D→speaker_2}`; every mapping is recorded in
`verdict.json`.

| meeting | arm | DER nc | JER nc | DER c | JER c |
|---|---|---|---|---|---|
| ES2011a | A | 37.1421 | 42.0913 | 31.4512 | 30.6634 |
| ES2011a | B | 31.5329 | 36.3113 | 24.3037 | 25.5480 |
| ES2011b | A | 24.1221 | 24.9410 | 16.4517 | 16.7043 |
| ES2011b | B | 18.5298 | 19.0848 | 10.1095 | 10.2051 |
| IS1008b | A | 18.1129 | 19.0275 | 11.1421 | 11.5760 |
| IS1008b | B | 14.9895 | 15.7288 | 7.8699 | 8.3770 |
| IS1008d | A | 18.4816 | 18.4804 | 8.7099 | 8.5662 |
| IS1008d | B | 22.7813 | 25.3885 | 12.1085 | 15.7992 |
| TS3004b | A | 22.3568 | 22.9228 | 14.7058 | 15.0447 |
| TS3004b | B | 16.5439 | 17.1194 | 9.5585 | 9.8812 |
| TS3004d | A | 25.7716 | 26.0426 | 17.7651 | 17.5282 |
| TS3004d | B | 23.9913 | 24.3658 | 16.4843 | 16.9786 |

B beats A on five of six meetings (all but IS1008d) under both conventions. ES2011a is the
hardest meeting for both arms under both conventions.

**Pooled** (NIST component-sum over the six meetings; total reference 10,590.4 s):

| convention | arm | DER | miss s | FA s | conf s | scored s |
|---|---|---|---|---|---|---|
| no collar, with overlap | A | **23.7341** | 2,319.4 | 110.4 | 83.8 | 10,769.2 |
| no collar, with overlap | B | **20.7405** | 1,623.7 | 346.4 | 226.4 | 10,752.2 |
| 0.25 collar, skip overlap | A | **15.6084** | 914.2 | 42.1 | 15.4 | 7,737.8 |
| 0.25 collar, skip overlap | B | **12.4158** | 646.1 | 40.5 | 86.4 | 7,720.8 |

(The collar-convention pooled rows are derived from the per-meeting breakdowns in
`verdict.json` by the same component-sum formula `pool_der_breakdowns` implements; the
no-collar rows are the file's own pooled block.) Error profile: A's deficit is almost
entirely MISS (2,319 s vs B's 1,624 s) — the streaming Arm B detects more speech, at the
cost of more FA (346 vs 110 s) and more confusion (226 vs 84 s).

JER pooled note: the scoring module defines no NIST pooled-JER; the unweighted mean of
per-meeting JER is A 25.5842 / B 22.9998 (nc) and A 16.6805 / B 14.4649 (c).

**pyannote 3.1 published AMI anchor (18.8, no collar, with overlap)**: pooled B = 20.7405
is **+1.94 points above (worse than) the anchor**; pooled A is +4.93 above. Neither arm
beats the published pipeline on this six-meeting subset; B is within ~2 points of it. (The
anchor is the full AMI test set under the same convention; this is a six-meeting dev-18
subset — an orientation comparison, not a leaderboard claim.)

## 2. Speaker-count accuracy

12/12: every RTTM on every meeting under both arms yields exactly 4 distinct speakers, and
every NXT reference table has exactly 4 — **100% speaker-count accuracy, both arms** (the
v2 model's 4-speaker bound fits the ES/IS/TS scenario meetings exactly, as registered).

## 3. Turn-boundary displacement vs oracle turns

Distance from each oracle turn boundary to the nearest tool boundary (seconds):

| meeting | arm | n | mean | median | max |
|---|---|---|---|---|---|
| ES2011a | A | 521 | 0.361 | 0.112 | 16.122 |
| ES2011a | B | 521 | 0.395 | 0.127 | 16.043 |
| ES2011b | A | 712 | 0.262 | 0.096 | 16.313 |
| ES2011b | B | 712 | 0.328 | 0.124 | 17.667 |
| IS1008b | A | 571 | 0.460 | 0.144 | 8.949 |
| IS1008b | B | 571 | 0.928 | 0.175 | 18.230 |
| IS1008d | A | 748 | 0.219 | 0.080 | 6.896 |
| IS1008d | B | 748 | 0.381 | 0.159 | 13.259 |
| TS3004b | A | 1,198 | 0.204 | 0.128 | 4.531 |
| TS3004b | B | 1,198 | 0.211 | 0.095 | 6.882 |
| TS3004d | A | 1,835 | 0.287 | 0.104 | 40.408 |
| TS3004d | B | 1,835 | 0.326 | 0.104 | 40.329 |

Medians sit at 0.08–0.18 s for both arms — sub-frame-accurate for 90 s transport packing.
The 40 s maxima on TS3004d for BOTH arms sit in its ~48 s inter-turn silence region (the
same stretch that exposed the slicer tiling bug): isolated short oracle turns inside/near
long silence that neither diarizer emits a nearby boundary for.

## 4. Packing-change fraction (the deployment-vs-ceiling transport number)

Fraction of 90 s transport slices whose positional `(start, end)` bound changes when oracle
turns are replaced by tool turns (both plans through the real
`build_turn_aware_slice_plan`, provenance `ORACLE_TURN` vs `TOOL_DIAR`, identical
audio-derived duration + pause-transition inputs):

| meeting | slices oracle | slices tool (A / B) | changed (A / B) | fraction (A / B) |
|---|---|---|---|---|
| ES2011a | 12 | 12 / 12 | 12 / 12 | 1.00 / 1.00 |
| ES2011b | 17 | 17 / 17 | 17 / 17 | 1.00 / 1.00 |
| IS1008b | 18 | 19 / 19 | 19 / 19 | 1.00 / 1.00 |
| IS1008d | 16 | 15 / 15 | 16 / 16 | 1.00 / 1.00 |
| TS3004b | 24 | 24 / 24 | 24 / 24 | 1.00 / 1.00 |
| TS3004d | 29 | 29 / 29 | 29 / 29 | 1.00 / 1.00 |
| **pooled** | 116 | — | **117 / 117 changed of 117 / 117 compared** | **1.0000 / 1.0000** |

**The registered metric reads 1.0000 for both arms on every meeting.** Slice COUNTS stay
within ±1 of oracle everywhere, but the positional-equality comparison (6-decimal rounding)
cascades: the first sub-second boundary difference shifts every subsequent slice bound, so
any realistic tool turn table yields fraction 1.0. Mechanical implication for G1: the
deployment-vs-ceiling gap CANNOT be assumed away at the transport layer ("tool-diar packs
the same slices" is FALSE verbatim); the gap must be measured downstream on task metrics
per slice, not absorbed by this fraction. The metric as registered saturates and carries no
discrimination beyond that statement — a lesson for the PRECOMP sweep design (a
boundary-tolerance or content-overlap variant would discriminate; changing it now is a
post-hoc redefinition this document does not perform).

## 5. Wall/GPU economics (from the flight record, restated)

Total registered audio 10,941.3 s (3.04 h). Arm A total wall 326.6 s (ES2011a's 160.2 s
first contact carries CUDA context/warm-up; post-warm-up A runs at ~2% of real time). Arm B
total wall 467.9 s, 4.1–4.6% of real time per meeting, peak 1,072 MiB, peak 52 °C.
GPU: 0.082 GPU-h utilisation-integrated for the whole flight (conservative upper bound
0.25 GPU-h) vs the registered ≤1.0 ceiling. Deployment story intact on economics: the B
path is a 147 MB q8_0 GGUF + a single pinned binary, no Python ML stack, ~23x faster than
real time on this GPU.

## 6. Recorded deviation and caveats (carried in ALL outcomes)

**Streaming-mode deviation (flight-recorded).** Arm B flew in DiarStream STREAMING mode
(the tool default and the v2 model's native long-form path), not the prereg §2 `--offline`
sketch — `--offline` refused all six meetings (rel-pos table cap ~6 min); one diagnosed
retry dropped the flag (tool, checkpoint, hashes unchanged; attempt-1 evidence preserved
under the flight's `attempt-1-offline-mode/`). Consequence for interpretation: A (fp32,
card-default offline `.diarize()`) and B (q8_0 GGUF, streaming) differ in BOTH quantization
AND inference mode, so the parity clause no longer isolates quantization safety — the
2.99-point gap (B better) is mode-confounded. Any pin freeze binding B must name
"streaming (default), not `--offline`" as the flown geometry.

**In-domain caveat.** AMI appears in the NVIDIA models' training data (partition unstated
by the model card); every DER/JER above is therefore an in-domain number and is cited as
such — it licenses tool USE on AMI-domain material, never a generalization claim.

**Subset caveat.** Six dev-18 scenario meetings, 3.04 h; the 4-speaker bound excludes ICSI
by registration.

## 7. What this read settles and what it escalates

Settled mechanically by this read:
- Both arms load and run all six meetings (12/12); FALLBACK-NEEDED's load condition is
  dead; a pyannote-3.1 fallback smoke is NOT required by any fired clause.
- Pooled DER(B) = 20.7405 (nc) clears the 22.0 lock threshold with margin +1.2595;
  DER(A) = 23.7341 does not (−1.7341); the two-sided parity gate fails by 0.9936.
- Speaker counting is exact everywhere; boundary medians are ~0.1 s; the registered
  packing-change fraction saturates at 1.0 (the ceiling-vs-deployment transport gap is
  real and must be carried into G1's design, not assumed zero).

Escalated to the owner (the prereg's clause set is non-covering at this cell; deciding any
of these here would be a post-hoc registration change):
1. **G1 lock #3 (tools/run-flow)**: remains OPEN. The evidence supports a
   B-binding on every axis EXCEPT the registered two-sided parity gate, which B fails in
   the favorable direction under a mode confound.
2. **`PinnedToolDiarization` binding**: deferred with the same evidence; if the owner
   adjudicates the gap cell toward a B-binding, the flown pin set is Arm B = v2 q8_0 GGUF,
   nemo-speech `4c749a7`, STREAMING geometry, with the in-domain caveat attached to every
   downstream deployment-tier number; if toward A or a re-fly (e.g. an A-streaming parity
   arm to unconfound mode), that is a NEW registration, not this smoke.
3. **PRECOMP sweep decision**: blocked on the same adjudication; carries §4's
   saturation lesson for its own metric registration.

This read is spent either way: prereg §7's one-shot discipline holds regardless of the
adjudication outcome.
