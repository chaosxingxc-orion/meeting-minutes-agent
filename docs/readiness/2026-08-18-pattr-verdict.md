# P-ATTR capability smoke — verdict and pre-registered branch decision (2026-08-18)

The registered one-shot read of the flight in `docs/checks/2026-08-18-pattr-smoke-flight/`.
Registration: `2026-08-18-g1-preregistration-draft.md` §0. Scoring path: `probes/pattr_scoring.py`
(`score_arm`), unmodified, at study commit `8fb9448`. Machine record and full tables:
`docs/checks/2026-08-18-pattr-smoke-read/` (`verdict.json`, `report.txt`). Zero model contact, zero
GPU, no new bytes.

## 0. The branch decision

### 0.1 What "materially better" was declared to mean — BEFORE the numbers

§0 registered the branch as: *if A-grid's confusion cost is not materially better than A-free, the
LISTEN main design is RETIRED and G1 adopts the A-turn form; otherwise the main design is
confirmed.* "Materially better" was operationalized in the scoring driver, and written into
`verdict.json` (`branch.rule`) and `report.txt`, before any error rate had been computed:

Let `CC` be the secondary confusion cost (cpWER − ORC-WER, the untimed attribution isolate the
committed module reports for grid/free), micro-averaged within a meeting, and
`d_m = CC_free(m) − CC_grid(m)`. **A-grid is materially better than A-free iff all three hold:**

1. **direction** — `d_m > 0` in ALL FOUR meetings (the grid helps everywhere, not on average);
2. **magnitude** — the pooled `Δ` exceeds the per-meeting spread `max d_m − min d_m` (the gap must
   be larger than its own meeting-to-meeting variation, the only signal-to-noise statement n=4
   supports);
3. **non-degeneracy guard** — pooled `cpWER(A-grid) ≤ cpWER(A-free)` on the paired subset of
   sessions both arms could score. A grid that "wins" on confusion cost only by emitting less
   transcript has not bought attribution.

Conditions 1+2 are the bare rule; 1+2+3 the guarded rule. The guarded outcome is the decision.
Both are reported. A meeting with no computable `CC` cannot satisfy condition 1 — absent evidence
is not evidence of a grid benefit.

### 0.2 Applying it mechanically

| condition | result |
|---|---|
| confusion-cost evidence complete in all 4 meetings | **False** — A-grid yielded no `CC` in any meeting |
| (i) direction, all four `d_m > 0` | **False** |
| (ii) pooled `Δ` > spread | **False** (neither is computable) |
| (iii) non-degeneracy guard, 20 paired sessions | **False** — cpWER A-grid **1.0705** vs A-free **0.3611** |
| bare rule (i+ii) | **False** |
| guarded rule (i+ii+iii) | **False** |

> ## VERDICT: the LISTEN main design is **RETIRED**. G1 adopts the **A-turn** form — attribution by construction, the speaker label read from the diarization layer, the core asked only to transcribe.

The decision does not rest on a close WER contest. A-grid did not produce an attributable
transcript in a single one of its 24 slices (§2), so the arm has no confusion cost to compare.

## 1. Every ingredient number

Session unit: one transport slice — 24 sessions (6 × 4 meetings), identical for all three arms.
Each slice was an independent request and the smoke carries no rolling tail or speaker state, so
the core had no means of holding a label stable across slices; per-meeting permutation matching
would charge it for a capability the flight never gave it. Pins: meeteval 0.4.3, collar 5 s, pins
hash `d9a9d122…`.

### 1.1 Pooled over the 24 slice-sessions (micro-averaged)

| arm | cpWER | ORC-WER | CC = cpWER−ORC | ins | del | sub | ref words | sessions with cpWER | ORC refused |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A-grid | 1.0705 | — | — | 1937 | 2824 | 448 | 4866 | 20/24 | 21/24 |
| A-free | 0.4352 | 0.3242 | **0.1110** | 382 | 1336 | 898 | 6011 | 24/24 | 0 |
| A-turn | **0.3657** | 0.3492 | **0.0165** | 399 | 835 | 964 | 6011 | 24/24 | 0 |

Each arm's pooled cpWER is over its own scoreable sessions, so the A-grid column is **not**
like-for-like; the 20 paired sessions in §0.2 are the only comparable A-grid-vs-A-free cpWER.

**A-turn time-constrained primaries** (the only arm whose stream carries real per-segment timing,
so the only one the committed module computes them for): tcpWER **0.3885**, tcORC-WER **0.3821**,
primary confusion cost **+0.0063**. A-grid/A-free tc metrics are not computed — their reply grammar
carries no per-segment timing and the module refuses a synthetic timestamp.

### 1.2 Confusion cost per meeting

| meeting | A-grid CC | A-free CC | A-turn CC | `d_m = CC_free − CC_grid` |
|---|---:|---:|---:|---:|
| ES2011b | n/a | 0.0815 | 0.0131 | n/a |
| IS1008b | n/a | 0.0179 | 0.0082 | n/a |
| IS1008d | n/a | 0.2118 | 0.0275 | n/a |
| TS3004b | n/a | 0.1068 | 0.0143 | n/a |

A-turn's confusion cost is 0.008–0.027 across all four meetings — near zero, as attribution by
construction must be; the residue is reference-boundary mismatch, not speaker error. A-free's is
0.018–0.212 — an order of magnitude larger, and its meeting-to-meeting spread is 10× wider
(0.194 vs 0.019).

### 1.3 Per meeting, all arms

| meeting | arm | cpWER | ORC-WER | CC | ref words | hyp words | ORC refused |
|---|---|---:|---:|---:|---:|---:|---:|
| ES2011b | A-grid | 0.5949 | — | — | 1301 | 931 | 3/6 |
| ES2011b | A-free | 0.3843 | 0.3028 | 0.0815 | 1301 | 1100 | 0 |
| ES2011b | A-turn | 0.3551 | 0.3420 | 0.0131 | 1301 | 1210 | 0 |
| IS1008b | A-grid | 1.2509 | — | — | 1455 | 1348 | 6/6 |
| IS1008b | A-free | 0.2667 | 0.2488 | 0.0179 | 1455 | 1339 | 0 |
| IS1008b | A-turn | 0.2969 | 0.2887 | 0.0082 | 1455 | 1434 | 0 |
| IS1008d | A-grid | 1.2565 | — | — | 811 | 1484 | 6/6 |
| IS1008d | A-free | 0.5630 | 0.3513 | 0.2118 | 1785 | 1419 | 0 |
| IS1008d | A-turn | 0.4006 | 0.3731 | 0.0275 | 1785 | 1632 | 0 |
| TS3004b | A-grid | 1.2286 | — | — | 1299 | 1193 | 6/6 |
| TS3004b | A-free | 0.4918 | 0.3850 | 0.1068 | 1470 | 1199 | 0 |
| TS3004b | A-turn | 0.4007 | 0.3864 | 0.0143 | 1470 | 1299 | 0 |

A-grid's reference-word column is smaller where cpWER was refused for some of that meeting's
slices (IS1008d loses 3 slices, TS3004b 1). The per-slice table is in `report.txt`.

### 1.4 Boundary respect (the registered A-grid diagnostic)

| computation | matched positions | parsed segments vs declared turns | slices with a count mismatch |
|---|---|---:|---:|
| A-grid (registered) | **0 / 333 (0.0000)** | 459 vs 461 | 22/24 |
| A-free (contrast, not registered) | 0 / 167 (0.0000) | 179 vs 461 | 24/24 |

Both zeros are **label-namespace artifacts, not attribution measurements**: the diagnostic compares
the parsed speaker field against the declared speaker at the same position, and neither arm ever
put a declared AMI label there (A-grid put the grid index, A-free its own `<speaker_N>` names).
The informative number in that table is the segment count: A-grid emitted **459 segments against
461 declared turns** — it tracked the grid's *segmentation* almost exactly while discarding the
speaker labels entirely. A-free emitted 179 segments for the same 461 turns, i.e. it merges roughly
2.6 gold turns into every line it produces.

### 1.5 Parse statistics

| arm | parse modes | malformed lines | empty replies |
|---|---|---:|---:|
| A-grid | strict 23, lenient 1 | 0 | 0 |
| A-free | strict 24 | 0 | 0 |
| A-turn | 450 non-empty transcripts | 0 | 0 |

Zero malformed lines and zero empty replies in all 498 records. The parser never failed — which is
exactly why the A-grid failure is easy to miss: those replies are *well-formed under the grammar*,
they just key on the wrong field (§2).

Speaker-label census: A-grid **154 distinct labels** (`[0]`, `[1]`, … — grid indices), A-free
**6** (`<speaker_1..4>`, `<speaker_0>`, and one unbracketed `speaker_1`).

### 1.6 Timing economics

| arm | requests | total latency | mean/req | median | max | latency per audio-second |
|---|---:|---:|---:|---:|---:|---:|
| A-grid | 24 | 114.7 s | 4.778 s | 4.454 s | 10.529 s | 0.0489 |
| A-free | 24 | 102.1 s | 4.253 s | 4.352 s | 5.715 s | 0.0435 |
| A-turn | 450 | 196.7 s | **0.437 s** | 0.187 s | 3.364 s | 0.0920 |

A-turn costs **18.8× the calls** but only **1.72× the summed request latency**, at roughly twice
the latency per audio-second of the slice arms (0.0920 vs 0.0435–0.0489). The pre-registration
expected "~5–10× call count at 4.3 s/call overhead", i.e. 516–1,032 s of request latency for this
smoke; the arm actually cost **196.7 s — 2.6–5.2× cheaper than planned**. The call multiplier came
in higher than expected (18.8×) and the per-call overhead far lower (0.437 s, not 4.3 s): a turn
clip is a few seconds of audio against a ~106-token prompt, so median latency is 0.187 s.

### 1.7 A-turn clip coverage of the gold region

| meeting | gold speech | covered by turn clips | fraction | clips |
|---|---:|---:|---:|---:|
| ES2011b | 455.8 s | 455.8 s | 1.0000 | 73 |
| IS1008b | 529.8 s | 529.8 s | 1.0000 | 121 |
| IS1008d | 554.9 s | 554.9 s | 1.0000 | 147 |
| TS3004b | 544.2 s | 544.2 s | 1.0000 | 109 |

100% in all four meetings: A-turn's WER carries no penalty for gold speech its clips never saw.

## 2. Why A-grid has no score: a reply-grammar failure, not a proven core incapability

The A-grid prompt asks for `<speaker>|<text>` lines and separately supplies a numbered grid
(`[i] start-end speaker`). The core resolved that conflict by keying on the grid index. Census over
all 24 A-grid slices, using the committed parser:

| reply form | slices |
|---|---:|
| `[i]\|<text>` — grid index in the speaker field, speaker label dropped | 22/24 |
| `[i]\|<speaker-letter>` — echoes back the labels the grid already supplied, **no transcript at all** | 1/24 (ES2011b slice0000) |
| degenerate repetition loop (§3) | 1/24 (TS3004b slice0000) |
| `<declared speaker>\|<text>` — the requested form | **0/24** |

So the committed parser reads `[0]`, `[1]`, … as speaker identities. Consequences: boundary respect
is 0 by construction; the hypothesis carries up to 154 "speakers" per slice, which meeteval refuses
(21/24 sessions lose ORC-WER, 4 of those lose cpWER too); and the surviving cpWER of 1.0705 is
dominated by that artifact — with 14–20 hypothesis streams against 4 reference speakers, all but
four streams are charged wholly as insertions (1937 insertions, 2824 deletions).

**Read this correctly.** The evidence says the A-grid design *as specified* yields no attributable
transcript, in 24 of 24 slices, and that is sufficient for the registered branch. It does **not**
say the core cannot attribute speech: A-free, the same core on the same audio with the grid removed,
produced well-formed multi-speaker transcript in 24/24 slices with 1–4 stable cluster labels. What
the grid bought was worse than nothing — it captured the output format and displaced the labels.
Note also that the declared grid *contains the answer* (each line names its speaker), so the one
slice where the core echoed labels back is not evidence of attribution ability either.

## 3. Truncation disclosure

`pattr-grid-TS3004b-slice0000` hit the 1,024-token generation cap (registered in the FLOWN
paragraph) and was scored **as-is**, with no re-flight and no repair. On reading it, the reply is
worse than truncated: after ~22 plausible lines it degenerates into a repetition loop
(`[23]|Z...`, `[24]|Z...`, … to `[153]|Z...`) and runs into the cap. It parses to 154 segments in
lenient mode and is one of the four sessions where even cpWER was refused. It is the single worst
A-grid cell and it is disclosed rather than dropped; excluding it would not change any condition of
the branch decision, since A-grid's confusion cost is missing in all four meetings regardless.

## 4. Deviations from the scoring plan, and why

The read ran the committed `score_arm` path. Three things were forced by meeteval, all decided
before any error rate was read, all recorded in `verdict.json` (`scoring_plan`, R9):

1. **Session unit = transport slice**, not meeting. A whole-meeting 4-stream ORC-WER exhausted
   memory on this host (meeteval's MIMO cost explodes with stream count). The slice is also the
   semantically correct unit here (§1).
2. **Refusals recorded as data.** meeteval hard-refuses >10 streams in both its cpWER and ORC-WER
   paths. Each refusal is a per-cell `refusal` record with its stream count and the refusal text;
   the read continues. No metric, pin, or threshold was changed.
3. **The non-degeneracy guard is computed on the paired common subset** (20 sessions, 4,866
   reference words for both arms), so it never compares two different denominators.

No re-scoring was done after seeing a result, and the A-grid parse was deliberately **not** repaired
to recover its transcript: that would be a new scoring path applied after the fact, which one-shot
discipline forbids. Recovering it is a legitimate future read of the same records, under its own
registration, if the owner wants the counterfactual.

## 5. Limitations — this is capability evidence, never a deployment floor

- **Scale**: 24 slices from 4 AMI dev meetings (asr-eval role), ~6,011 reference words per arm.
  n=4 meetings supports a sign-consistency statement and nothing stronger.
- **Context-minimal by design**: no rolling transcript tail, no roster/agenda context block, no
  supply. §0b's deployment-baseline context was deliberately absent to isolate attribution. Every
  WER here is therefore an under-context number and must not be quoted as a G1 floor.
- **Per-slice sessions mean cross-slice speaker identity was never tested.** Whether the core can
  keep "speaker 1" stable across slice boundaries is an open question this smoke cannot answer; it
  is exactly what §0b's rolling tail is meant to address.
- **A-turn's numbers ride on an oracle.** Its turn spans come from the gold AMI segment layer
  (Tier-M1 `oracle-turn`, `allow_oracle_turns=True`). A-turn's 0.3657 cpWER and ~0 confusion cost
  are an **oracle-diarization ceiling**, not a deployable result: adopting the A-turn form for G1
  commits G1 to sourcing turn boundaries, and any real diarizer's error will re-enter as
  attribution error. This is the single largest caveat on the branch decision.
- **A-free's confusion cost is the untimed secondary metric**, whose registered caveat applies:
  system-side utterance reordering inflates ORC-WER and therefore *shrinks* cpWER−ORC-WER. A-free's
  0.1110 is if anything an underestimate of its attribution error.
- **Utterance segmentation is not scored** (the registered blind spot). It matters here: A-free
  merges ~2.6 gold turns per emitted line, which the metric family does not charge.
- **A-grid is unscoreable, not measured.** Its cpWER of 1.0705 is a label-namespace artifact; no
  claim about its transcription quality is made or implied.

## 6. What this changes for G1

1. The LISTEN main design (declared turn grid, model fills text per span) is retired as the
   headline arm. G1's transcription+attribution arm is the A-turn form.
2. G1 must name a **turn-boundary source**. A-turn's economics are affordable (0.437 s/request,
   1.72× A-grid's wall-clock for 18.8× the calls), but its attribution quality is inherited from
   whatever supplies the spans.
3. A-free remains the honest zero-supply *baseline* for "what the frozen core does unaided" — it
   works, it is 0.4352 cpWER, and its 0.1110 confusion cost is the attribution gap a supply or
   state mechanism would have to close.
4. Any future prompt that supplies a structured block must pin an **output-grammar contract** and a
   parse check: this flight shows a supplied grid can silently capture the reply format while the
   parser reports 100% strict success. That belongs in §0b's P-PROMPT sweep as a hard admission
   test, not as a scoring-time discovery.
