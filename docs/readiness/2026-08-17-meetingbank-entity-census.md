# MeetingBank entity re-census — the substrate decision gate (2026-08-17)

The registered substrate-decision-gate measurement (umbrella
`wiki/survey/workbench/2026-08-17-meeting-agent-direction/DEEP-CHECK-SYNTHESIS.md` §3.1;
`docs/plans/2026-08-17-founding-workplan.md` §5). AMI measured 3.8 distinct proper names per
meeting at repeat payoff 0.211 and FAILED; ICSI ships no NE layer at all; MeetingBank is the last
meeting-domain candidate standing. This is its census.

CPU only, zero model contact, no downloads. All figures below are computed from shipped bytes
under `$SPEECHRL_DATA_DIR`. Aggregate statistics and entity surface forms only — no running
transcript text was written to any committed file or runtime path. Machine record:
`2026-08-17-meetingbank-entity-census.json`.

**Headline: SPLIT verdict. MeetingBank clears the density floor's first limb by roughly 31×
and clears the second limb on long meetings but not corpus-wide; it fails the same gate's
reference-adequacy limb outright. The landed 50-meeting flight subset FAILS. MeetingBank can host
a meeting-domain glossary claim on the summarization / QA / segmentation surface and only on a
length-stratified subset — it can never host an entity-WER or keyword-F glossary-GAIN claim.**

## 0. The registered floor, restated

Three limbs, all three binding:

1. **≥ 10 distinct proper-name terms per episode** (anchored to EGTA's ~10-terms/doc operating point)
2. **repeat payoff ≥ 0.40**
3. **reference adequacy** — verbatim transcript gold for any WER-family claim

Metric definitions are taken verbatim from the committed 2026-08-17 census
(`docs/readiness/2026-08-17-entity-density-census.md` §0) so the numbers are comparable:
a **mention** is one entity occurrence; a **surface form** is its tokens lowercased, punctuation
stripped, whitespace collapsed; **repeat payoff share** = (mentions − distinct forms) / mentions
within one episode; **long-span type share** = fraction of distinct forms whose first and last
occurrence are more than 300 s apart.

**One reconstruction had to be made and is flagged.** The AMI/earnings21 census script is not in
this repository, so the aggregation rule behind its published repeat-payoff figures was
reconstructed from the two published pairs. AMI reports 919 mentions over 117 meetings with 3.8
distinct forms per meeting — a pooled computation gives 0.516, not the published 0.211, whereas an
unweighted mean over episodes reproduces the published shape (earnings21: pooled 0.603 vs published
0.578). **The primary aggregation used here is therefore the unweighted mean over episodes, and
the pooled variant is reported alongside every figure** so the verdict can be read either way.
Where the two disagree, the disagreement is stated explicitly rather than resolved silently.

## 1. The census table

MeetingBank has **no NE gold**, so its column is an estimate and is marked as such throughout.
AMI and earnings21 are annotation-grounded.

| | **AMI NE layer** | **earnings21 (ConEC)** | **MeetingBank (estimated)** |
|---|---|---|---|
| episodes | 117 meetings | 44 calls | **1,366 meetings** |
| audio hours | 59.95 | 39.17 | **3,578.68** |
| mean episode length | ~31 min | ~53 min | **157 min** (median 130) |
| word tokens | 564,390 | 362,747 | 31,571,026 |
| **proper-name mentions** | 919 | 10,760 | **728,041** (est.) |
| proper-name mentions / hour | 15.3 | **274.7** | 203.4 |
| proper-name mentions / 1k words | 1.63 | **29.66** | 23.06 |
| proper-noun token share | 0.22 % (annotated) | 3.61 % | 4.65 % (est.) |
| **distinct vocab per episode** | **3.8** | **97** | **312.5** (median 294) |
| distinct vocab, pooled | 265 | 3,019 | 172,976 |
| **repeat payoff share** | **0.211** | **0.578** | **0.387** mean / 0.414 pooled |
| recurring type share | 0.255 | **0.382** | **0.198** |
| long-span type share | 0.178 | 0.120 | 0.122 |
| **floor verdict** | **FAIL** | **PASS** | **SPLIT — see §5** |

Applying the measured estimator precision (§3) to the MeetingBank column — mention-weighted
precision for the rate figures, type-level precision for the vocabulary figure — gives
15.7–18.1 mentions / 1k words, a 3.2–3.6 % token share and **219–260 distinct names per episode**.
Precision-adjusted, MeetingBank's proper-noun token share brackets earnings21's 3.61 %, and its
per-episode vocabulary is 2.3–2.7× earnings21's.

**The one number that inverts the story is recurring type share: 0.198, the lowest of the three
corpora — below even AMI's 0.255.** MeetingBank is not earnings21 with more hours. It is a corpus
with an enormous, overwhelmingly *singleton* name vocabulary (public commenters introducing
themselves, street addresses, community organizations named once) on top of a small head that
recurs very hard (`long beach` 20,297 mentions, `denver` 19,987, then a councilmember roster).
Mention mass is concentrated; type mass is a long tail. §6 shows why that distinction decides the
mechanism question.

## 2. Estimator 1 — capitalization, and what it excludes

The shipped Speechmatics transcripts (`engineVersion v1.0.2`, `en-US`) emit casing, word-level
timings and per-word confidences. A **mention** is one maximal run of capitalized tokens surviving
the exclusion rules; closed-set connectors (`of`, `the`, `and`, `for`, `de`, `la`, …) are absorbed
only when flanked by capitals on both sides. The filtering discipline mirrors the AMI census, whose
headline proper-name class is open-vocabulary PERSON / LOCATION / ORGANIZATION — role labels,
temporal expressions, numerals and scenario objects excluded.

Exclusions, in force and documented:

1. **sentence-initial tokens** — never candidates (the AMI rule).
2. **first-person pronoun** — `I`, `I'm`, `I've`, `I'll`, `I'd`.
3. **roles, titles, honorifics** — stripped from the head of a run; a run made only of them is
   dropped. `Councilman Price` → `price`, `Council President Harrell` → `harrell`. This is the
   MeetingBank analogue of AMI's closed-set PARTICIPANT subtypes, which the AMI census excluded
   because a roster supplies them and a glossary cannot learn them. The list includes Boston's
   `Councilor` **and the Speechmatics rendering of it as `Counselor` / `Counsel`**, which would
   otherwise have entered the count as a high-frequency name.
4. **TIMEX** — month and weekday names.
5. **discourse tokens an ASR capitalizes mid-utterance**, plus bare geographic heads left behind
   when a run truncates at a lowercased or sentence-initial neighbour (`street`, `avenue`, `park`,
   `west`, `grove`, …), plus this engine's artifacts (`dash`, `amp`, `fy`).
6. **generic institutional and procedural forms** applied to the whole normalized form —
   `city council`, `public comment`, `docket`, `ordinance`, `roll call`, `pledge of allegiance`,
   `consent calendar`, … Every meeting in every city has these; a glossary learns nothing from them.
   This is the same logic that removed `industrial designer` from the AMI count.
7. **single-character forms** — `Item B`, `line D`.

One MeetingBank-specific normalization step beyond the AMI rule: a trailing English possessive is
removed, so `denver's` and `denver` are one form.

The exclusion list was designed against a **discovery pass over 48 held-out meetings** and then
frozen before the corpus run — the top-150 pooled forms of that pass were read, and the artifacts
they exposed (`docket`, `counsel`, `dash`, `amp`, single letters, bare street heads, possessives)
are exactly items 3–7 above.

## 3. Estimator precision — measured, not assumed

60 candidates were sampled with seed 20260817, stratified across all six cities: **30
mention-weighted** (every occurrence equally likely — measures how much of the mention *mass* is a
real name) and **30 type-level** (uniform over the distinct surface-form vocabulary — measures the
precision of the *vocabulary a glossary would be built from*). Each was adjudicated by hand in its
transcript context. Labels are recorded per-item in the machine JSON.

| | n | clean true positive | true positive, span imperfect | false positive | strict precision | entity-bearing precision |
|---|---|---|---|---|---|---|
| mention-weighted | 30 | 20 | 2 | 8 | 0.667 | 0.733 |
| type-level | 30 | 21 | 4 | 5 | 0.700 | 0.833 |
| **combined** | **60** | **41** | **6** | **13** | **0.683** [0.558, 0.787] | **0.783** [0.664, 0.869] |

Brackets are Wilson 95 % intervals. "Span imperfect" means a genuine proper name whose run was
truncated or merged but whose string still carries a usable entity (`Alan Cohen` → `cohen` when the
given name fell on a sentence start; `Treasury of the United States` → `treasury` when the run broke
at a lowercase `the`).

Per city, strict precision: Denver 0.80, KingCounty 0.80, LongBeach 0.80, Seattle 0.60,
Boston 0.60, Alameda 0.50 (n = 10 each, so these are indicative only).

**The false-positive taxonomy matters more than the headline rate**, because the classes fail
differently:

| class | n | effect on the metrics |
|---|---|---|
| merged run (two entities fused across a conjunction or a docket title) | 4 | inflates distinct count, **deflates repeat payoff** — each merge is a novel singleton |
| generic common noun the ASR capitalized (`Slide 11`, `Parkway setback`) | 3 | inflates distinct count, mildly deflates repeat payoff |
| common acronym (`OPEB`, `LGBTQ`) | 2 | inflates both counts |
| ambiguous acronym (`AOC seven`, `the IMO you expires`) | 2 | inflates distinct count |
| ASR-invented name (`Tokyo audio`, `Councilor Me`) | 2 | inflates distinct count, deflates repeat payoff |

**The ASR-casing reliability caveat, stated honestly and with its direction.** Casing errors do not
bias the count symmetrically here. Sentence-boundary errors *truncate* runs (an entity survives with
a shorter surface form); conjunction merges *fuse* runs (a novel garbage string is created);
recognizer garbles *fragment* an entity across spellings — the corpus visibly carries `mongo` for
Mungo, `pryce`/`price`, `ashcraft`/`ashcroft`, `gonzalez`/`gonzales`, `fernandez anderson` split into
`fernandez` and `anderson`. Every one of these mechanisms creates additional singleton forms.
**Estimator noise is therefore overwhelmingly singleton, and singletons push repeat payoff down.
The raw repeat-payoff figure is a lower bound.** §4 quantifies by how much.

The precision figures also mean the density column of §1 should be read as ×0.68 (strict) to ×0.78
(entity-bearing) for mention rates, and as ×0.70 to ×0.83 (the type-level row) for the distinct
vocabulary — which, at 312.5 distinct names per episode, leaves 219–260. The first limb of the floor
is not close to the noise level.

## 4. How far the repeat-payoff figure moves under denoising

Every filter below is **episode-independent** — none of them uses within-episode counts, so none can
manufacture recurrence directly.

| candidate set | distinct / episode | repeat payoff (mean) | repeat payoff (pooled) |
|---|---|---|---|
| raw estimator (**primary**) | 312.5 | **0.387** | 0.414 |
| form ≤ 4 tokens (drops merged runs) | 281.4 | 0.408 | 0.436 |
| form ≤ 3 tokens | 256.1 | **0.425** | 0.454 |
| form ≤ 2 tokens | 210.5 | 0.451 | 0.483 |
| corpus doc-frequency ≥ 2 meetings | 212.6 | 0.468 | 0.501 |
| corpus doc-frequency ≥ 3 meetings | 190.4 | 0.488 | 0.523 |
| corpus doc-frequency ≥ 5 meetings | 167.4 | 0.511 | 0.548 |
| corpus doc-frequency ≥ 10 meetings | 138.2 | 0.543 | 0.582 |
| ≤ 3 tokens **and** doc-frequency ≥ 3 | 175.0 | 0.502 | 0.537 |

Merging near-duplicate surface forms *within* an episode (edit distance ≤ 1, the ASR-variance
fragmentation above) merges 2.2 % of types and moves repeat payoff 0.387 → 0.398.

**Read this as a bracket, not as a correction.** The raw 0.387 is a lower bound because estimator
noise is singleton-heavy. The doc-frequency rows are an upper bound, because corpus frequency is
positively correlated with within-episode recurrence — that filter partly selects for the thing it
measures. The length filter is the least correlated and the best-justified by the precision audit
(merged runs are the single largest false-positive class), and it gives **0.425 / 0.454**.

**Best estimate: repeat payoff ≈ 0.42–0.45, with the registered 0.40 floor inside the bracket
and below the point estimate — but with the raw primary statistic, 0.387, below the floor.**

## 5. Verdict against the floor, per city and for the flight subset

Primary aggregation (unweighted mean over episodes), raw estimator, no denoising:

| slice | episodes | distinct / episode | repeat (mean) | repeat (pooled) | **verdict** | episodes clearing both |
|---|---|---|---|---|---|---|
| **MeetingBank, all** | 1,366 | 312.5 | 0.387 | 0.414 | **FAIL** (limb 2 by 0.013) | 652 / 1,366 = 47.7 % |
| **≥ 90-minute slice** | 928 | 387.6 | **0.412** | 0.424 | **PASS** | 558 / 928 = 60.1 % |
| Alameda | 164 | 378.0 | **0.422** | 0.432 | **PASS** | 106 / 164 |
| Boston | 32 | 342.0 | **0.420** | 0.438 | **PASS** | 23 / 32 |
| Denver | 401 | 306.1 | **0.414** | 0.442 | **PASS** | 256 / 401 |
| LongBeach | 310 | 418.8 | 0.385 | 0.403 | **FAIL** (PASS if pooled) | 137 / 310 |
| KingCounty | 132 | 196.3 | 0.361 | 0.376 | **FAIL** | 44 / 132 |
| Seattle | 327 | 230.8 | 0.344 | 0.373 | **FAIL** | 86 / 327 |
| **flight subset (landed 50)** | 50 | 249.5 | **0.358** | 0.383 | **FAIL** | 12 / 50 = 24 % |
| — flight Denver | 20 | 203.3 | 0.397 | 0.417 | FAIL (marginal) | 8 / 20 |
| — flight LongBeach | 10 | 386.9 | 0.380 | 0.389 | FAIL | 2 / 10 |
| — flight Seattle | 20 | 226.9 | 0.308 | 0.344 | FAIL | 2 / 20 |

**Limb 1 is not in doubt anywhere.** The floor asks for 10 distinct proper names per episode.
The corpus minimum across 1,366 meetings is 9, the 1st percentile is 31, the 10th percentile is 115
and the median is 294. **Exactly one meeting in 1,366 falls below the floor**, and only 22 fall
below 50. Even at the strict-precision lower bound this limb clears by more than twenty-fold. This
is the decisive contrast with AMI, which offered 3.8.

**Limb 2 is genuinely marginal, and it is marginal for a reason that is measurable.** Repeat payoff
correlates with episode length at Pearson r = 0.537 (distinct count correlates at r = 0.883).
Meetings ≥ 90 minutes: 387.6 distinct, repeat 0.412 — **PASS**. Meetings < 30 minutes: 66.8
distinct, repeat 0.245 — FAIL. The corpus-level miss is driven by short meetings, and the
long-form slice that a long-form flight (G5) would actually use clears the floor on the primary
aggregation with no denoising at all.

**The landed flight subset fails, and the subset-versus-corpus bias the census was asked to expose
is real and adverse.** At 0.358 the subset sits *below* the corpus figure of 0.387, because it draws
20 of its 50 meetings from Seattle — the weakest city on this metric (0.344) and the shortest-meeting
city in the corpus (446 h over 327 meetings, 1.36 h mean, against LongBeach's 3.56 h). Only 12 of
the 50 landed meetings individually clear both limbs. Restricting even the landed subset to its
≥ 90-minute members, or re-stratifying toward Denver, would change this verdict; Denver's long-form
slice runs 393.1 distinct at 0.442.

**Limb 3, reference adequacy, fails outright and is not marginal.** MeetingBank's shipped references
are Speechmatics ASR output, not verbatim human gold — the acquisition manifest already records
`wer_scoring_supported: false`. Scoring transcription against them measures agreement with another
recognizer. **No WER-family or keyword-F entity claim can be scored on this corpus at any density.**

## 6. Provenance — how much of the entity mass is metadata-reachable

The deep check requires this factorization explicitly. Two measurements, because the shipped
metadata is much thinner than the metadata channel a real deployment would have.

**(a) From the shipped Legistar bytes.** `Metadata/MeetingBank.json` carries, per meeting, a set of
agenda items keyed by file number, each with a `type` and a `Summary` (the Legistar agenda-item
description). There is **no explicit sponsor or council-roster field** — the roster must be read out
of the Summary prose. Mean per meeting: 5.0 items, 5.0 file numbers, **19.6 distinct proper-name
types** recoverable from the Summaries.

| slice | roster name types / episode | mention share, exact | mention share, loose | type share, exact | type share, loose |
|---|---|---|---|---|---|
| corpus | 19.6 | **4.9 %** | **15.7 %** | 1.5 % | 6.6 % |
| Boston | 33.0 | 10.3 % | 24.8 % | 3.0 % | 12.3 % |
| LongBeach | 31.8 | 6.4 % | 18.4 % | 1.7 % | 8.0 % |
| Denver | 15.5 | 4.7 % | 15.9 % | 1.3 % | 6.2 % |
| Seattle | 14.8 | 4.7 % | 13.0 % | 2.0 % | 6.5 % |
| Alameda | 27.2 | 2.1 % | 14.2 % | 0.7 % | 4.6 % |
| KingCounty | 2.8 | 4.1 % | 7.9 % | 0.5 % | 3.4 % |
| flight subset | 17.1 | 4.0 % | 14.5 % | 1.8 % | 6.5 % |

"Loose" counts a match when either string is a contiguous token subsequence of the other.
**Answer, from shipped bytes: 5–16 % of the addressable entity mass is metadata-roster-reachable;
84–95 % is speech-only.**

**(b) Against a static per-city roster, which is what a real Legistar scrape would supply.** The
shipped Summaries do not contain the sitting council roster, yet the head of the speech vocabulary
*is* a council roster (`ortega`, `flynn`, `richardson`, `gonzalez`, `price`, `herbold`, `cashman`,
`espinosa`, `herndon`, `brooks`). So the shipped-bytes figure understates the metadata channel. A
per-city roster was therefore built **leave-one-meeting-out** by document frequency inside the same
city, so no meeting votes for the roster used to score it:

| static city roster | roster-only coverage of mentions | episode-local glossary **exclusive** share | combined |
|---|---|---|---|
| top 10 terms | 16.7 % | **51.8 %** | 68.5 % |
| top 25 | 21.4 % | 48.0 % | 69.4 % |
| top 50 | 25.8 % | 44.7 % | 70.5 % |
| top 100 | 30.4 % | 41.5 % | 71.9 % |
| top 250 | 37.8 % | 36.7 % | 74.5 % |
| top 500 | 44.4 % | 32.5 % | 76.9 % |
| entire city vocabulary (~unbounded) | 76.7 % | 13.2 % | 89.9 % |

**This is the most favourable result in the census for the topic's core mechanism.** At realistic
prompt-budget roster sizes (10–100 terms, EGTA's operating point), a static roster reaches 17–30 %
of the mention mass, while **41–52 % of the mention mass is reachable only from episode-local
discovery**. Episode-local supply is not redundant with a roster on this corpus. The exclusivity is
bounded, though: against an unbounded per-city vocabulary it collapses to 13.2 %, so the claim must
always be stated against a declared roster budget.

**A leakage hazard that partially collapses this factorization on MeetingBank, and must be
registered.** The Legistar `Summary` field *is* MeetingBank's summarization reference. On the
summarization surface — one of MeetingBank's only three valid surfaces — a metadata-derived glossary
is **Tier-M1 (reference-derived), not Tier-M0**, and is therefore ceiling/diagnostic only under the
registered leakage tiers. The registered speech-only / metadata-only / combined provenance
factorization (deep check §3.2) **cannot be run cleanly on MeetingBank's primary valid surface**;
the metadata-only arm is a ceiling there, not a baseline.

## 7. The mechanism test the gate implies

Repeat payoff credits a mention if the form appeared anywhere earlier in the episode — including
seconds earlier in the same passage. The mechanism actually under test is a glossary built from an
earlier pass and statically re-injected. That was measured directly: build the glossary from the
**first half** of the episode only, score coverage on **second-half** mentions. No oracle.

| glossary | mean size | second-half mention coverage (pooled) |
|---|---|---|
| top 10 first-half terms | 10.0 | 16.3 % |
| top 25 | 24.8 | 20.8 % |
| top 50 | 48.9 | 23.8 % |
| top 100 | 91.3 | 25.9 % |
| unbounded first half | 179.4 | 30.3 % |
| top 10, precision-filtered | 10.0 | 22.8 % |
| top 25, precision-filtered | 24.7 | 29.3 % |
| top 50, precision-filtered | 47.1 | 33.7 % |
| unbounded, precision-filtered | 101.8 | 40.5 % |

A ten-term glossary carries 16 % of the second half's proper-name mentions (23 % once low-precision
candidates are dropped); a fifty-term one carries 24–34 %. These are real, non-trivial numbers, and
they are also substantially below the 0.387 repeat-payoff headline — because a large part of that
headline is short-range repetition inside a single passage, not carry across a chunk boundary.
**Any cross-chunk-carry claim on MeetingBank should be sized against 16–34 %, not against 0.387.**
This is the number G3's carry-delta kill criterion should be powered on.

## 8. Verdict

**Limb 1 — distinct proper names per episode ≥ 10: PASS, decisively, everywhere.** 312.5 per
episode corpus-wide (219–260 precision-adjusted), 1,365 of 1,366 individual meetings above the
floor, every city and every flight-subset city above it by more than twenty-fold. MeetingBank is
not AMI: the open-vocabulary name mass the deep check hoped for is genuinely there, at 4.65 % of
tokens against AMI's 0.22 %.

**Limb 2 — repeat payoff ≥ 0.40: MARGINAL, resolving by slice.**

- FAIL corpus-wide on the primary aggregation, 0.387, missing by 0.013.
- PASS corpus-wide on the pooled aggregation, 0.414.
- PASS on the ≥ 90-minute slice on the primary aggregation, 0.412 over 928 meetings and 3,190 hours.
- PASS on Alameda (0.422), Boston (0.420), Denver (0.414); FAIL on LongBeach (0.385, passing at
  0.403 pooled), KingCounty (0.361), Seattle (0.344).
- PASS on every episode-independent denoising filter (0.425–0.548); best estimate 0.42–0.45.
- **FAIL on the landed 50-meeting flight subset, 0.358** — worse than the corpus, because the
  subset over-weights short Seattle meetings.

**Limb 3 — reference adequacy: FAIL, outright and structurally.** ASR references, no verbatim gold.

**Can MeetingBank host the meeting-domain glossary-GAIN claim?**

**As that claim is currently specified — no.** H1 is registered against keyword-F and entity-WER
(deep check §3.8), and those are WER-family metrics that MeetingBank's ASR references cannot score.
This is independent of density and no amount of subset re-stratification fixes it. The density
question, which this census was commissioned to settle, turns out not to be the binding constraint.

**On the summarization / QA / segmentation surface — yes, conditionally**, and this is the
constructive path. MeetingBank's summarization reference (Legistar agenda-item descriptions) is
official human-written text, not ASR output, so a glossary-gain claim measured as *downstream
summarization or QA quality* is scoreable here. Three conditions bind:

1. **Length-stratify the substrate.** Restrict to ≥ 90-minute meetings, where the registered floor
   passes on the primary aggregation with no denoising. Corpus-wide and on the landed subset it
   does not.
2. **Re-stratify or re-cut the flight subset.** The landed 50 fail at 0.358 and only 12 of them
   clear both limbs individually. Denver is the strongest already-landed city (long-form slice:
   393.1 distinct, 0.442); Seattle is the weakest and currently holds 20 of the 50 slots. Selecting
   meetings on a *first-half* density criterion is leakage-free and would be a legitimate frozen
   design; selecting on the full-episode outcome metric is circular and must not be done.
3. **Keep the glossary speech-derived.** The Legistar metadata is the summarization reference, so a
   metadata-derived glossary is Tier-M1 on that surface — ceiling and diagnostic only.

**Consequence for the workplan.** The census does not overturn the existing ordering; it sharpens
it. earnings21 remains the only substrate combining density, recurrence *and* gold references, so
G2 (P-GLOSS v1) stays where it is and stays the falsifiable test. MeetingBank's confirmed role is
the **meeting-domain long-form and summarization/QA surface** (G5), under length stratification, and
it is a strong one: 3,579 hours, 928 meetings over 90 minutes, 41–52 % of entity mass reachable only
by episode-local discovery at realistic roster budgets. What MeetingBank cannot be is the corpus
that scores an entity-recognition gain. The gap the deep check identified — a meeting corpus with
both entity density and verbatim gold — is **still open after this census**, and no candidate in the
current acquisition set closes it.

## 9. Reproduction

Read-only, CPU, ~35 s for the full 1,366-transcript pass with 16 workers. WSL2 `Ubuntu-24.04`,
`~/.venvs/speechrl` (Python 3.12), `PYTHONDONTWRITEBYTECODE=1`. No model contact, no downloads,
no audio decoded.

Inputs, all under `$SPEECHRL_DATA_DIR/datasets/meetingbank/`:
`text/zenodo/extracted/Audio&Transcripts/<City>/transcripts/*.transcript.json` (1,366 files,
2.59 GB); `text/zenodo/extracted/Metadata/MeetingBank.json` (the shipped Legistar index, 1,250
meetings, 253 MB); `audio-subset/subset-manifest.json`. Meetings are joined to the Legistar index
by the basename of the index's `URLs.Video`; 116 shipped transcripts carry no index entry and are
censused by estimator 1 only — including 2 of the 50 flight-subset meetings, which therefore have
no metadata roster at all.

Corpus duration computed from the transcripts' own `duration` field (100-ns ticks) totals 3,578.68 h
against the subset manifest's independently recorded `full_corpus_hours: 3579`, and the flight
subset totals 81.78 h against the manifest's `exact_hours_from_transcripts: 81.78` — an exact
cross-check of the time base.
