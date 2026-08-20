# G1 floors campaign — ONE-SHOT DESCRIPTIVE READ

Date: 2026-08-20 (UTC read timestamp; campaign flown 2026-08-19). Status: **READ COMPLETE —
descriptive floors, NO branch verdicts.** Registration:
`docs/readiness/2026-08-19-g1-floors-preregistration.md` (REGISTERED, owner GO 2026-08-19).
Flight: `docs/checks/2026-08-19-g1-floors-flight/` (72/72 items, 1,932 calls, zero breaches).
Read receipt and machine outputs: `docs/checks/2026-08-19-g1-floors-read/`.

This document reports what the four registered arms measure. It selects no winner, promotes no
branch, and makes no claim about generalization. Per the preregistration's MDE/noise discipline
(§4), **no comparison is narrated as real unless its per-meeting-clustered paired bootstrap CI
excludes zero**, and the P-PROMPT server-state spread (**0.085** cpWER, same request bytes,
different server state — `2026-08-18-pprompt-verdict.md` §4b) is the single-run noise reference
every effect size is read against.

Read parameters, everywhere: all **dev-18** meetings (eval-16 and reserved untouched), roster
resolved by `g1_campaign.meetings_for_mode("floors")`; metric pins hash `d9a9d122…c247f`;
bootstrap seed 20260818, 10,000 replicates, 90 % percentile CI, clustered at meeting
granularity. All 1,932 flown replies scored (1,496 transcribe + 36 minutes + 400 QA); the five
retried contacts appear once each in the sink under their logical request id, so the retry cost
nothing at the scoring layer.

---

## 1. The floors

### 1a. Pooled per arm (equal-weighted over the 18 meetings, never slice-weighted)

| arm | mean cpWER | speaker-confusion (cpWER−ORC) | tcpWER−tcORC@5s | grammar compliance | slices |
|---|---:|---:|---:|---:|---:|
| **Z-turn** (deployment) | **0.6099** | +0.2054 | +0.1042 | 0.9972 | 367 |
| **Z-oracle** (ceiling) | **0.6061** | +0.2195 | +0.1131 | 0.9984 | 371 |
| **Z-free** (attribution-free) | **0.8726** | +0.4001 | n/a | 1.0000 | 367 |
| **Z-nodiar** (pure-VAD) | **0.8816** | +0.3841 | n/a | 1.0000 | 391 |

`n/a`: the primary (time-constrained) confusion cost requires real per-segment timing on the
hypothesis stream. The transcribe-only arms emit one untimed single-stream segment by
construction, so their primary term is structurally undefined — not refused, not zero.

Indicative content-only decomposition (cpWER minus the speaker-confusion term; the two means
run over slightly different slice denominators — §4 — so read it as indicative, not as a
computed ORC-WER floor): Z-turn ≈ 0.404, Z-oracle ≈ 0.387, Z-free ≈ 0.473, Z-nodiar ≈ 0.498.
**Most of the spread between the attribution-bearing and attribution-free arms is speaker
assignment, not word content.**

### 1b. Per meeting × arm — cpWER

| meeting | Z-turn | Z-oracle | Z-free | Z-nodiar | slices (turn/oracle/free/nodiar) |
|---|---:|---:|---:|---:|---|
| ES2011a | 0.6441 | 0.6490 | 0.9218 | 0.9445 | 12/12/12/13 |
| ES2011b | 0.6041 | 0.6216 | 0.8168 | 0.8083 | 17/17/17/18 |
| ES2011c | 0.6127 | 0.6377 | 0.7800 | 0.8494 | 17/17/17/18 |
| ES2011d | 0.6898 | 0.7557 | 0.9647 | 0.9825 | 21/21/21/22 |
| IB4001 | 0.5770 | 0.5319 | 0.8771 | 0.8851 | 19/19/19/20 |
| IB4002 | 0.6845 | 0.7462 | 1.0453 | 1.0410 | 20/21/20/21 |
| IB4003 | 0.5426 | 0.5593 | 0.8623 | 0.8359 | 22/22/22/23 |
| IB4004 | 0.5851 | 0.5636 | 0.9049 | 0.8932 | 26/27/26/27 |
| IB4010 | 0.6240 | 0.6053 | 0.9138 | 0.9262 | 32/32/32/33 |
| IB4011 | 0.5930 | 0.5451 | 0.8471 | 0.8268 | 26/27/26/27 |
| IS1008a | 0.3826 | 0.3222 | 0.8255 | 0.8662 | 9/10/9/11 |
| IS1008b | 0.3580 | 0.4178 | 0.6194 | 0.6867 | 19/18/19/20 |
| IS1008c | 0.4996 | 0.4466 | 0.7148 | 0.7085 | 16/18/16/17 |
| IS1008d | 0.4579 | 0.4953 | 0.8857 | 0.8750 | 15/16/15/17 |
| TS3004a | 0.7384 | 0.6882 | 0.8613 | 0.9165 | 14/15/14/15 |
| TS3004b | 0.8051 | 0.8045 | 0.9156 | 0.8757 | 24/24/24/25 |
| TS3004c | 0.7166 | 0.6959 | 0.9205 | 0.9217 | 29/26/29/33 |
| TS3004d | 0.8625 | 0.8247 | 1.0300 | 1.0261 | 29/29/29/31 |

Per-meeting spread is wide on every arm: Z-turn ranges 0.358 (IS1008b) to 0.863 (TS3004d), a
0.50 band — nearly six times the single-run noise reference. IS1008* are the easy meetings and
TS3004b/d the hard ones on every arm, the same ordering the P-PROMPT sweep saw on its own
four-meeting subset. Two transcribe-only cells exceed cpWER 1.0 (IB4002, TS3004d): a
single-stream hypothesis scored against a multi-speaker reference can accumulate more errors
than the reference has words.

### 1c. Per meeting × arm — speaker-confusion (cpWER − ORC-WER) and grammar compliance

| meeting | Z-turn | Z-oracle | Z-free | Z-nodiar |
|---|---|---|---|---|
| ES2011a | +0.2548 / g1.000 | +0.1968 / g1.000 | +0.4834 / g1.000 | +0.4811 / g1.000 |
| ES2011b | +0.2284 / g1.000 | +0.2448 / g1.000 | +0.4021 / g1.000 | +0.3526 / g1.000 |
| ES2011c | +0.2418 / g1.000 | +0.2742 / g0.971 | +0.3387 / g1.000 | +0.3639 / g1.000 |
| ES2011d | +0.2880 / g1.000 | +0.3862 / g1.000 | +0.5238 / g1.000 | +0.5265 / g1.000 |
| IB4001 | +0.1646 / g1.000 | +0.2259 / g1.000 | +0.4371 / g1.000 | +0.3991 / g1.000 |
| IB4002 | +0.2765 / g1.000 | +0.3303 / g1.000 | +0.4314 / g1.000 | +0.4394 / g1.000 |
| IB4003 | +0.1139 / g1.000 | +0.1460 / g1.000 | +0.3070 / g1.000 | +0.3370 / g1.000 |
| IB4004 | +0.1797 / g1.000 | +0.1827 / g1.000 | +0.4847 / g1.000 | +0.4529 / g1.000 |
| IB4010 | +0.2268 / g0.988 | +0.2359 / g1.000 | +0.4722 / g1.000 | +0.4031 / g1.000 |
| IB4011 | +0.2132 / g1.000 | +0.1563 / g1.000 | +0.4271 / g1.000 | +0.3051 / g1.000 |
| IS1008a | +0.0620 / g1.000 | +0.0443 / g1.000 | +0.2556 / g1.000 | +0.3576 / g1.000 |
| IS1008b | +0.0682 / g1.000 | +0.1485 / g1.000 | +0.2838 / g1.000 | +0.2930 / g1.000 |
| IS1008c | +0.0599 / g1.000 | +0.1209 / g1.000 | +0.2660 / g1.000 | +0.2382 / g1.000 |
| IS1008d | +0.1401 / g1.000 | +0.1347 / g1.000 | +0.4236 / g1.000 | +0.4394 / g1.000 |
| TS3004a | +0.2664 / g0.998 | +0.2365 / g1.000 | +0.3881 / g1.000 | +0.3601 / g1.000 |
| TS3004b | +0.2684 / g0.963 | +0.2395 / g1.000 | +0.3069 / g1.000 | +0.3178 / g1.000 |
| TS3004c | +0.2672 / g1.000 | +0.2490 / g1.000 | +0.4266 / g1.000 | +0.3386 / g1.000 |
| TS3004d | +0.3775 / g1.000 | +0.3978 / g1.000 | +0.5439 / g1.000 | +0.5080 / g1.000 |

Grammar compliance is effectively saturated: 1.0000 on both transcribe-only arms by definition
(no per-line grammar to violate), and 0.9972 / 0.9984 pooled on the attribution arms, with the
only visible dips at TS3004b (0.963, Z-turn), IB4010 (0.988), ES2011c (0.971, Z-oracle) and
TS3004a (0.998). **The locked T1-A1 output grammar is not a bottleneck at this floor.**

### 1d. Per meeting × arm — primary confusion cost (tcpWER − tcORC@5s)

| meeting | Z-turn (computable/slices) | Z-oracle (computable/slices) |
|---|---|---|
| ES2011a | +0.0850 (12/12) | +0.1021 (10/12) |
| ES2011b | +0.0901 (17/17) | +0.0764 (17/17) |
| ES2011c | +0.0937 (17/17) | +0.0716 (17/17) |
| ES2011d | +0.1222 (20/21) | +0.1363 (21/21) |
| IB4001 | +0.1211 (18/19) | +0.1367 (19/19) |
| IB4002 | +0.1494 (20/20) | +0.1425 (20/21) |
| IB4003 | +0.0516 (20/22) | +0.0897 (20/22) |
| IB4004 | +0.0951 (23/26) | +0.0945 (26/27) |
| IB4010 | +0.1158 (32/32) | +0.1075 (30/32) |
| IB4011 | +0.1054 (22/26) | +0.1058 (24/27) |
| IS1008a | +0.0688 (9/9) | +0.0821 (10/10) |
| IS1008b | +0.0596 (19/19) | +0.0636 (18/18) |
| IS1008c | +0.0346 (13/16) | +0.0653 (16/18) |
| IS1008d | +0.0846 (15/15) | +0.0819 (15/16) |
| TS3004a | +0.1221 (13/14) | +0.1269 (14/15) |
| TS3004b | +0.1220 (23/24) | +0.1339 (20/24) |
| TS3004c | +0.1655 (26/29) | +0.1822 (23/26) |
| TS3004d | +0.1886 (27/29) | +0.2375 (24/29) |

A slice's primary term is computable only when every parsed line aligned positionally to a real
turn-table entry; surplus parsed lines fall back to whole-slice bounds and make the slice
untimed. The computable fraction is **346/367** (Z-turn) and **344/371** (Z-oracle).

### 1e. SAER-M — **NOT SCOREABLE on this campaign's minutes replies**

The registered scoreable subset is confirmed structurally: **12 of 18** meetings carry the
extractive+summlink evidence layer (ES2011a–d, IS1008a–d, TS3004a–d); the six IB meetings carry
none and are excluded by the same criterion the metric's own definition uses.

But **no SAER-M accuracy can be reported for either arm**, and the 0.0000 the committed scorer
returns is an artefact, not a floor. `compute_saer_m` joins gold and prediction on
`sentence_id`. Gold sentence ids are NXT corpus ids (first gold id on ES2011a:
`ES2011a.JacquelinePalmer.s.1`); the minutes head synthesizes its own bullet ids as
`"<section>-<index>"` (`abstract-0`, `actions-0`, …). **The intersection is exactly 0 sentence
ids on all 24 (arm × scoreable-meeting) cells.** Mechanically, all 214 gold sentences are
classified `unattributed`, every predicted bullet is classified `hallucinated_speaker`, and
`n_correct = 0` by construction rather than by measurement. Reporting "SAER-M = 0.0" as a floor
would be reporting a join failure as a capability.

What the minutes replies do support — plumbing and claim-density facts, no metric:

| arm | bullets parsed | bullets carrying a speaker claim | parse modes (strict/lenient/failed) |
|---|---:|---:|---|
| Z-turn | 196 | 26 (13.3 %) | 1 / 15 / 2 (failed: IB4001, IB4010) |
| Z-oracle | 336 | 112 (33.3 %) | 3 / 15 / 0 |

Both arms sit almost entirely in the `lenient` parse mode: the four-section grammar is being
approximated, not honored, and the per-bullet evidence tag — the very field SAER-M consumes —
is present on a minority of bullets on the deployment arm. Making SAER-M measurable needs an
alignment layer from generated minutes bullets to gold summary sentences (the metric's
definition assumes corpus-assigned sentence ids that a generative head cannot produce); that
layer does not exist in this repository and building it is not part of this read.

### 1f. QA — the capped question set

Registered cap applied exactly: **200 of 489** usable-discovery questions attached to dev-18,
seed 20260818; 56 of the 200 are unanswerable questions. Routed per meeting, 11 of 18 meetings
drew questions; 400 QA calls = 200 × 2 arms. Scorer: the reimplemented upstream MeetingQA
scorer (max over gold alternatives).

| arm | n | macro F1 | exact match | parse (strict/lenient/failed) | abstentions |
|---|---:|---:|---:|---|---:|
| Z-turn | 200 | **0.0725** | 0.0400 | 199 / 1 / 0 | 72 |
| Z-oracle | 200 | **0.0970** | 0.0600 | 199 / 1 / 0 | 66 |

| meeting | n | Z-turn F1 / EM | Z-oracle F1 / EM |
|---|---:|---|---|
| ES2011a | 7 | 0.0000 / 0.0000 | 0.0000 / 0.0000 |
| ES2011b | 15 | 0.1380 / 0.0667 | 0.2069 / 0.1333 |
| ES2011c | 18 | 0.0648 / 0.0556 | 0.2406 / 0.2222 |
| ES2011d | 23 | 0.0644 / 0.0435 | 0.0485 / 0.0000 |
| IB4001 | 17 | 0.0694 / 0.0000 | 0.0420 / 0.0000 |
| IB4002 | 20 | 0.0654 / 0.0500 | 0.0319 / 0.0000 |
| IB4003 | 19 | 0.0891 / 0.0526 | 0.0373 / 0.0000 |
| IB4010 | 45 | 0.0658 / 0.0222 | 0.0961 / 0.0444 |
| IS1008b | 9 | 0.1275 / 0.1111 | 0.0161 / 0.0000 |
| IS1008d | 8 | 0.0400 / 0.0000 | 0.1250 / 0.1250 |
| TS3004b | 19 | 0.0614 / 0.0526 | 0.1750 / 0.1579 |

**Binding caveat on every QA number**: the QA head's audio anchor is the arm's **first
transcribe slice only** — one ~90 s window, shared by every question about that meeting —
because the transport enforces a hard 120 s per-request audio cap and MeetingQA carries no
audio-grounding timestamp (`probes/g1.py` module docstring, a recorded design decision). These
are therefore floors for *question answering from one bounded audio window*, not a measurement
of meeting-level QA capability, and the reply grammar itself is near-perfectly honored
(199/200 strict on both arms). The output-format layer is healthy; the evidence supply is not
there. MeetingQA is CC BY-NC-SA; every number in this subsection inherits that licence.

---

## 2. The deployment gap (Z-turn − Z-oracle)

Per-meeting-clustered paired bootstrap, 18 meetings, seed 20260818, 10,000 replicates, 90 % CI.
No meeting was dropped from any pairing.

| metric | point estimate | 90 % CI | CI excludes zero |
|---|---:|---|---|
| cpWER | **+0.0037** | [−0.0124, +0.0193] | **no** |
| speaker-confusion (cpWER−ORC) | −0.0140 | [−0.0312, +0.0025] | no |
| **tcpWER−tcORC@5s** | **−0.0090** | **[−0.0160, −0.0025]** | **yes** |
| grammar compliance | −0.0012 | [−0.0057, +0.0031] | no |
| QA macro F1 (11 meetings) | −0.0212 | [−0.0609, +0.0176] | no |

**cpWER: no narratable difference.** The pinned tool diarizer's turn boundaries and oracle NXT
turns produce transcription-attribution floors that this campaign cannot separate. The CI is
0.032 wide — under 40 % of the 0.085 single-run noise reference — so the null is not merely an
underpowered shrug at this scale, though it remains a null and is stated as one. The per-meeting
signs are inconsistent (Z-turn is lower on 8 meetings, Z-oracle on 10) and **no single meeting's
Z-turn − Z-oracle difference reaches the noise reference**: the largest are ES2011d −0.0659
(deployment better) and IS1008a +0.0604 (ceiling better).

**Primary confusion cost: the one narratable comparison, and it is small.** Z-turn's
time-constrained confusion cost is 0.0090 lower than Z-oracle's, CI [−0.0160, −0.0025]. The
direction is that the *deployment* arm charges slightly less confusion than the oracle-turn
ceiling — the opposite of a degradation. The magnitude is roughly a ninth of the cpWER noise
reference and about 8 % of either arm's own primary cost (0.1042 / 0.1131), and the term is
averaged over the 346/344 slices where it is computable rather than over all slices. It is
narrated here because its CI excludes zero, and it is narrated as small.

Everything else — speaker-confusion, grammar, QA — has a CI containing zero and is **not**
narrated as a real difference.

---

## 3. The ablation readings

Same bootstrap machinery, applied to the arm contrasts (`ablations.json`). Z-turn and Z-free
consume the **identical** tool-diar slice set (367 slices), so their contrast isolates the
prompt/head shape with the audio held fixed; Z-nodiar carries its own pure-VAD geometry (391
slices).

| contrast | cpWER | 90 % CI | excludes zero |
|---|---:|---|---|
| Z-free − Z-turn | +0.2627 | [+0.2286, +0.2978] | **yes** |
| Z-nodiar − Z-turn | +0.2718 | [+0.2364, +0.3081] | **yes** |
| Z-nodiar − Z-free | +0.0091 | [−0.0024, +0.0212] | no |
| Z-free − Z-oracle | +0.2664 | [+0.2316, +0.3031] | **yes** |

| contrast | speaker-confusion | 90 % CI | excludes zero |
|---|---:|---|---|
| Z-free − Z-turn | +0.1947 | [+0.1690, +0.2194] | **yes** |
| Z-nodiar − Z-turn | +0.1787 | [+0.1496, +0.2080] | **yes** |
| Z-nodiar − Z-free | −0.0160 | [−0.0349, +0.0031] | no |

**Z-free (attribution-free baseline).** Dropping turn metadata from the prompt and switching to
the transcribe-only head costs +0.2627 cpWER against the deployment arm on the same audio — an
effect three times the single-run noise reference, and the largest separation this campaign
measured. Roughly three quarters of it (+0.1947) is the speaker-confusion component. Read with
care: the transcribe-only head's reply is scored as one untimed single-stream segment with a
placeholder speaker id, so cpWER charges it for *all* speaker assignment. The contrast is
therefore between two different *scoring shapes* as much as two different capabilities, and the
honest statement is the decomposed one — **the attribution-bearing arms' advantage is
concentrated in speaker assignment (≈0.19 of the 0.26), not in word content (≈0.07)**.

**Z-nodiar (pure-VAD slicing).** Against Z-free, the arm that differs from it only in slicing
geometry, the gap is +0.0091 cpWER with CI [−0.0024, +0.0212] and −0.0160 on speaker-confusion
with CI [−0.0349, +0.0031]: **neither excludes zero, so this campaign separates pure-VAD 90 s
slicing from tool-diar turn-aware 90 s slicing on neither metric.** What the diarizer buys at
this floor is the *turn metadata in the prompt*, not the *slice boundaries*: replacing
diar-derived boundaries with VAD boundaries is not narratable, while removing turn metadata from
the prompt is the campaign's largest effect. Z-nodiar's absolute floor (0.8816) sits with
Z-free's (0.8726), far above both attribution arms.

---

## 4. Refusals, exclusions, and disclosures

**Capped replies: zero, every arm.** No reply on any of the 1,496 transcribe requests hit the
generation cap (`total_capped_replies = 0` on all four arms, independently confirming the
flight's own §4 disclosure). No floor in this document is truncation-confounded.

**ORC state-space refusals: 12 of 1,496 slice-scores (0.80 %).** The committed `orc_dp_bound`
guard (cap 2.0e9, reused verbatim from the P-PROMPT read) declined the ORC term where the
dynamic program was infeasible; the affected slices keep their real cpWER and are excluded only
from the confusion means.

| arm | meetings and counts | observed bounds |
|---|---|---|
| Z-turn (8) | ES2011d 1, IB4003 2, IB4004 1, IB4011 2, IS1008c 1, TS3004b 1 | 2.3e9 – 9.2e9 |
| Z-oracle (4) | IB4004 1, IB4011 1, TS3004b 1, TS3004c 1 | 4.7e9 – 3.3e10 |

Zero `MemoryError` refusals: the read ran under a 32 GiB address-space rlimit and never needed
it. Zero timestamp-validation refusals.

**Undefined-denominator slices: 9, all in TS3004c.** Z-turn 2, Z-free 2, Z-nodiar 5, Z-oracle 0.
These are slices whose gold reference range carries zero transcribed words; every WER-family
rate divides by the reference word count, so they have no rate at all. They are recorded with
`cp_wer = null` and `reference_empty = true`, excluded from every mean, and counted separately
from ORC refusals. TS3004c retains 27/29, 27/29 and 28/33 scoreable slices respectively, so no
meeting dropped out of any pairing.

**Denominator note.** Within one arm, the cpWER mean runs over the scoreable slices and the
confusion means over the smaller ORC-computable subset: cpWER 365 / 371 / 365 / 386 and
speaker-confusion 357 / 367 / 365 / 386 (Z-turn / Z-oracle / Z-free / Z-nodiar), with the primary
term narrower still (346 / 344). Every table above states its own counts; the §1a indicative
decomposition is the only place two different denominators are subtracted, and it is labelled
indicative for exactly this reason.

**Flight-side disclosures carried into this read.** Five of 1,932 contacts (0.26 %) were
retried, all on Z-oracle (2 minutes, 3 transcribe): each was a degenerate unbounded generation
that burned the 300 s per-attempt transport timeout and then succeeded on its bounded retry —
the same signature G1-PATH2 diagnosed and the reason that flight's per-attempt timeout was
halved. All five appear in the sink exactly once, under their logical request id, with
`outcome = ok`; the read scored the successful reply and no slice was scored twice or skipped.
All 1,932 sink records are `ok`, and the five response sinks are byte-identical before and after
this read.

**Machinery repaired before the read.** The read CLI could not score Z-nodiar at all (no
`--vad-manifest-dir`), and a zero-word gold reference aborted the entire read with a
`None − None` TypeError inside the confusion-cost subtraction; the first read attempt died on it
after ~30 minutes having written nothing. Both were fixed with tests before this read ran (full
suite 1,521 passed / 6 skipped), and the details are in
`docs/checks/2026-08-19-g1-floors-read/README.md` §2. This document reports the first and only
completed read.

**In-domain diarization caveat (carried, unchanged).** The pinned tool diarizer
(`nvidia/diar_streaming_sortformer_4spk-v2`, TOOL-LOCKED(B), DER 20.74 no-collar / 12.42 with
collar on six dev-18 meetings) has AMI in its training data. Its DER licenses *tool use inside
this campaign*; it licenses no generalization claim, and it is a live confound for the
deployment-vs-ceiling reading specifically: an in-domain diarizer is the most favorable case for
a deployment arm, so "the tool-diar arm is indistinguishable from the oracle-turn ceiling" must
be read as *on AMI, with a diarizer that has seen AMI*.

---

## 5. What these floors mean as G2's baseline

Descriptively, the four arms partition the measured surface into one large separation and one
absence of separation. The large one is turn metadata in the prompt: on identical audio, the
attribution-bearing arms sit ~0.26 cpWER below the attribution-free ones, and roughly three
quarters of that is speaker assignment rather than word content. The absent one is the turn
*source*: a pinned in-domain diarizer and oracle NXT turns land inside a ±0.02 cpWER band whose
CI contains zero, and swapping diar-derived slice boundaries for pure-VAD boundaries is likewise
not narratable. G2's supply interventions therefore do not have an oracle-turn headroom of
consequence to recover on this metric — the deployment arm is already at the ceiling this
campaign can measure. The headroom that exists is absolute, not relative: **cpWER 0.6099 with a
+0.2054 speaker-confusion component, on a per-meeting band from 0.358 to 0.863.** Any supply
intervention that claims progress on attribution has to move that absolute floor, and — per the
noise discipline this document runs under — has to move it by more than a 0.085 single-run
spread, with a clustered CI excluding zero, on the same 18 meetings.

The downstream heads set a different kind of bar. QA from one bounded 90 s window floors at
macro F1 0.0725 (deployment) / 0.0970 (ceiling) with near-perfect grammar and 72/200
abstentions: the format layer works, the evidence supply does not reach the question, and that
is precisely a supply problem stated in G2's own terms. Minutes cannot yet be scored at all —
not because the head fails to produce bullets (196 and 336) but because the evidence tag is
present on 13 % of deployment-arm bullets and no alignment exists between generated bullets and
gold summary sentences; SAER-M becomes a usable target only after that alignment is built.

These are floors, not verdicts. Nothing here selects a branch, promotes an arm, or claims
anything beyond the tables above.

---

## 6. Provenance

- Registration: `docs/readiness/2026-08-19-g1-floors-preregistration.md`.
- Flight: `docs/checks/2026-08-19-g1-floors-flight/` (README, `structural-report.txt`,
  `runtime-identity.json`, `MANIFEST.sha256` — 114 entries, 0 FAILED at read time).
- Read: `docs/checks/2026-08-19-g1-floors-read/` (`verdict.json`, `report.txt`,
  `supplement.json`/`.txt`, `ablations.json`/`.txt`, every operator script, `MANIFEST.sha256`).
- Prior locks: architecture, chunking, prompt form (`2026-08-18-pprompt-verdict.md`),
  tools/run-flow (`2026-08-19-diar-adjudication-TOOL-LOCKED-B.md`).
- Licences: AMI CC BY 4.0; MeetingQA CC BY-NC-SA on every QA-derived number.
