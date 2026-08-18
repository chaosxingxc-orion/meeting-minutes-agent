# P-PROMPT sweep — verdict: winner cell and corrupt-context reads (2026-08-18)

The registered one-shot read of the flight in `docs/checks/2026-08-18-pprompt-flight/`
(336/336, zero failures). Registration: `2026-08-18-pprompt-preregistration.md` §4 (mechanical
winner rule, corrupt-arm verdicts) and §6 (one-shot discipline);
parent binding `2026-08-18-g1-preregistration-draft.md` §0b. Scoring path:
`probes/pprompt_scoring.py` over the committed `probes/pattr_scoring.py` (`score_arm`), driver
`scripts/pprompt_read.py`, at study commit `1580f92`. Machine record and full per-slice tables:
`docs/checks/2026-08-18-pprompt-read/` (`verdict.json`, `report.txt`). Zero model contact, zero
GPU, no new bytes. Pins: meeteval 0.4.3, collar 5 s, pins hash `d9a9d122…`. Session unit: one
transport slice — 24 sessions per arm, identical across all 14 arms.

## 0. The winner (mechanical rule, §4, applied verbatim)

> ## WINNER: **T1-A1** — the bare pinned transcribe-attribute instruction + output-grammar contract, nothing else, in the system turn. mean cpWER **0.4789**, mean speaker-confusion **+0.1569**, grammar-compliance **1.0000**.

- **Eligibility**: all 12 grid cells passed the compliance gate at exactly **1.0000** (≥0.90);
  GRAMMAR-BLOCKED was not approached. Zero malformed lines and zero empty-parse replies in all
  336 records — the P-ATTR output-grammar lesson held under every template and arrangement.
- **Tie-set**: `{T1-A1}` alone. The runner-up (T4-A1, 0.5225) is 0.0436 away — 4.4× the 0.01
  tie margin — so **no tie-break was invoked**; the registered trail (confusion → compliance →
  lower T → lower A) was never consulted.
- A structural fact that sharpens the lock: **T1 carries no extra context block, so its three
  arrangement cells render byte-identical requests** (binding manifest; identical
  `renderings_combined_hash`). The winning FORM is therefore unambiguous — bare instruction +
  grammar contract in the system turn, audio alone in the user turn — and "A1" is simply its
  canonical cell id.

## 1. Corrupt-context verdicts (each vs the T2/A1 reference cell, §4)

| arm | corruption | mean cpWER | reference (T2-A1) | degradation | verdict |
|---|---|---:|---:|---:|---|
| X1 | wrong roster (seeded label derangement per slice) | 0.5689 | 0.5562 | **+0.0127** | **CONTEXT-INDETERMINATE** |
| X2 | stale tail (another meeting's model-generated history) | 0.6016 | 0.5562 | **+0.0454** | **CONTEXT-INDETERMINATE** |

Both degradations land strictly between the registered thresholds (INERT ≤0.01,
SENSITIVE ≥0.05), so both verdicts are CONTEXT-INDETERMINATE and the prereg requires the
ingredients, which follow.

- **X1 ingredients**: per-meeting degradation vs T2-A1 is ES2011b **+0.0455**, IS1008b +0.0034,
  IS1008d +0.0013, TS3004b +0.0004 — the entire pooled effect sits in one meeting; the other
  three are flat. Confusion cost +0.2048 vs the reference's +0.1958 (+0.0090). A deliberately
  wrong roster moved almost nothing on 3 of 4 meetings.
- **X2 ingredients**: per-meeting degradation is **sign-inconsistent** — ES2011b +0.1235,
  IS1008b **−0.1147**, IS1008d −0.0267, TS3004b **+0.1994** (spread 0.314, dwarfing the +0.0454
  pooled mean). A stale cross-meeting tail can hurt a lot or "help" a lot depending on the
  meeting; n=4 supports no stronger statement. Confusion cost +0.1521 (−0.0437 vs reference).
- Neither corrupt arm was truncation-affected (both flew 0 capped replies), and both scored
  1.0000 compliance.

## 2. The full 12-cell grid (mean over 24 slice-sessions per cell)

| cell | mean cpWER | mean confusion | compliance | | cell | mean cpWER | mean confusion | compliance |
|---|---:|---:|---:|---|---|---:|---:|---:|
| **T1-A1** | **0.4789** | +0.1569 | 1.0000 | | T3-A1 | 0.5292 | +0.1962 | 1.0000 |
| T1-A2 | 0.5639 | +0.1440 † | 1.0000 | | T3-A2 | 0.6287 | +0.1658 | 1.0000 |
| T1-A3 | 0.5639 | +0.1440 † | 1.0000 | | T3-A3 | 0.5234 | +0.1712 | 1.0000 |
| T2-A1 | 0.5562 | +0.1958 | 1.0000 | | T4-A1 | 0.5225 | +0.1633 | 1.0000 |
| T2-A2 | 0.5581 | +0.1975 | 1.0000 | | T4-A2 | 0.5496 | +0.1917 | 1.0000 |
| T2-A3 | 0.5258 | +0.1829 | 1.0000 | | T4-A3 | 0.5701 | +0.1517 | 1.0000 |

† mean over 23/24 slices: the ORC term of IS1008d slice0005 was refused as state-space
infeasible in these two cells (§5); cpWER and compliance are complete for all 336 replies.

Per-meeting cpWER tables for every cell are in `verdict.json`; IS1008d and TS3004b are the hard
meetings throughout (cell means 0.45–0.71 and 0.50–0.95 respectively).

## 3. Axis marginals (descriptive only — the registered rule selects cells, not axes)

**Template axis** (mean of 3 cell means): T1 **0.5356** < T2 0.5467 < T4 0.5474 < T3 0.5604.
The bare instruction beats every context-carrying template on mean cpWER, and also carries the
lowest confusion marginal (T1 +0.1483 vs T2 +0.1921, T3 +0.1777, T4 +0.1689). The deployment
context block bought nothing on this surface, and the empty glossary slot (T3) was the worst
template on cpWER. This ordering is stable when the one capped slice is excluded everywhere
(T1 0.448 < T4 0.494 < T3 0.513 < T2 0.521).

**Arrangement axis** (mean of 4 cell means): A1 **0.5217** < A3 0.5458 < A2 0.5751. Two
caveats make this the weakest read in the document: (i) T1's row contributes pure decode noise
to this axis (its three cells are one request, §4b); (ii) the axis is capped-reply-confounded —
all 8 truncated replies sit in A2/A3 cells on one slice (§4a), and excluding that slice
everywhere **inverts the order** (A3 0.471 < A2 0.500 < A1 0.512). Read it as: A1 never
truncated and never degenerated; text-after-audio (A3) was otherwise mildly better than
text-before-audio (A2). No arrangement conclusion beyond the winner cell should be built on
this axis.

## 4. Mandatory disclosures

### 4a. Eight capped replies, scored as-is

Eight replies hit the 1,024-token generation cap, all on **TS3004b-slice0000**, one per cell in
**T1-A2, T1-A3, T2-A2, T2-A3, T3-A2, T3-A3, T4-A2, T4-A3** (every A2/A3 cell; no A1 cell, no
corrupt arm). All eight were scored as-is, per the registered treatment. On that slice the
capped cells score cpWER 1.35–3.32 (several parse to 192-segment repetition-loop shapes, still
grammar-compliant) against 0.51–1.00 in the uncapped A1 cells.

**The winner cell is not affected**: T1-A1 hit the cap nowhere (max 474 completion tokens) and
its TS3004b-slice0000 reply is ordinary. Sensitivity of the conclusions (arithmetic on the
read's own per-slice records, excluding that one slice from every cell): the template ordering
is unchanged (T1 best), the winner's template group stays on top, but within the byte-identical
T1 triplet the nominal best cell becomes T1-A2/T1-A3 (0.4442) over T1-A1 (0.4563) — a swap
inside one and the same request, i.e. decode noise, not a form change. The arrangement marginal
is the one capped-sensitive read (§3). The corrupt verdicts are untouched (no capped reply in
T2-A1, X1, or X2).

### 4b. Decode-noise reference: byte-identical requests on this server

T1's three cells flew byte-identical requests. The registered decode-noise measurement —
**T1-A2 vs T1-A3 mean cpWER delta — is 0.0000**: the two later flights returned byte-identical
reply text on 24/24 slices (verified against the archived JSONLs), despite the flight's counter
observation. The winner's 0.0436 margin exceeds that reference.

But the same triplet carries a second, larger same-bytes comparison that must be disclosed:
**T1-A1 vs T1-A2/A3 — same request bytes, different server state (first arm after server
start) — differs on 19/24 slices with a mean-cpWER spread of 0.0850**, which **exceeds the
winner's 0.0436 margin over the runner-up**. Read both facts together: immediate same-state
resends reproduce exactly, but a same-bytes request against different server/cache state can
move mean cpWER by more than the gap between the top grid cells. The mechanical winner stands
as registered; the fine ranking among the leading cells (T1-A1 vs T4-A1 vs T3-A3 vs T2-A3)
should not be treated as decode-noise-proof. The template-level conclusion (T1 above every
context-carrying template in both decodes of T1: 0.4789 and 0.5639 vs T2–T4 marginals
0.547–0.560 — n.b. the second decode sits inside the T2–T4 range; it is the T1 marginal 0.5356
and the capped-slice-excluded view, where both T1 decodes lead, that carry the direction) is
the robust part; the cell-level margin is one draw.

### 4c. Oracle-turn packing scope

The sweep rode the P-ATTR smoke's frozen 24-slice surface with oracle-tagged turn metadata
(NXT gold turn BOUNDARIES and labels in the context blocks; never gold transcript text). All
conclusions transfer to **G1's ceiling arm and prompt form only** — they say nothing about
deployment-tier diarization, and every number here inherits the oracle-diarization caveat the
P-ATTR verdict already carries. These are prompt-form comparisons at the dev/discovery tier,
not floors and not deployment claims.

## 5. Forced deviation: ORC state-space refusals (recorded as data, decided pre-read)

The read was attempted twice at flight commit `f004e02`; both attempts were OOM-killed by the
kernel (~56 GB) before writing anything — the one-shot output never existed. A structure-only
census plus a subprocess feasibility probe (rlimit-capped, feasibility flags only, no error
rate surfaced) located the cause: the byte-identical T1-A2/T1-A3 replies on IS1008d slice0005
parse to 7 speaker streams, putting meeteval 0.4.3's ORC-WER dynamic program at ~7.9e9 state
units (≈190 GB) — unconditionally infeasible on the 54 GB host, while cpWER (Hungarian) is
cheap on every flown reply. Amendment `1580f92` — committed BEFORE the read, thresholds chosen
from reply STRUCTURE only, mirroring the P-ATTR read's recorded meeteval refusals — refuses an
ORC term above a 2.0e9 state-space cap (and records any in-attempt MemoryError identically);
a refused slice keeps its real cpWER and carries `confusion_cost=None` + a reason. Outcome:
**exactly 2 ORC refusals in 336 slice-scores** (those two cells' IS1008d slice0005), zero
MemoryError refusals. cpWER — the winner rule's primary criterion — and compliance are complete
for all 336 replies; the two affected confusion means average 23/24 slices and confusion was
never consulted (the tie-set was a singleton). The read itself ran under a 32 GiB
address-space rlimit (attempt 3, exit 0, 19:11→19:19Z).

## 6. What this verdict LICENSES

1. **The G1 prompt-form lock**: G1's transcribe-attribute head binds the **T1-A1 form** — the
   pinned bare instruction + output-grammar contract in the system turn, audio alone in the
   user turn, **no deployment context block, no empty glossary slot, no reinforced-grammar
   restatement**. For this form the arrangement question is closed by construction (T1 renders
   identically under all three arrangements). The winning template+arrangement freezes by id
   and hash per §0b(2); the binding manifest's T1 `task_instruction_sha256` (`eef611b2…`) is
   the frozen text.
2. **The corrupt verdicts feed G1's context-integrity guard decision as measured inputs**:
   X1 = CONTEXT-INDETERMINATE (+0.0127, one-meeting effect), X2 = CONTEXT-INDETERMINATE
   (+0.0454, 0.0046 under the SENSITIVE threshold, per-meeting spread 0.314 with both signs).
   Under the locked T1 form G1 carries no context block or tail by default, so no guard is
   mandated by this read; any future arm that reintroduces a tail or roster block must confront
   X2's near-threshold, high-variance degradation profile (§0b(2)'s validation-gate rule) and
   may not cite this read as evidence of context inertness — INDETERMINATE is not INERT.
3. Nothing here is a floor, a superiority claim, or a deployment-tier number (§4c); G1 floors
   fly under their own preregistration with this prompt form bound.
