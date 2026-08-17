# L2 — entity-density census (2026-08-17)

Task L2 of the founding workplan: measure the glossary loop's addressable mass per corpus.
CPU only, zero model contact, no downloads. All figures below are computed from shipped bytes
under `$SPEECHRL_DATA_DIR`. No reference transcript text was written to any output file or any
runtime path; the census emits aggregate statistics only.

## 0. Metric definitions (identical across corpora unless noted)

- **Mention** — one annotated entity occurrence. AMI: one `<named-entity>` element in the NE layer.
  earnings21: one distinct entity id in the `wer_tags` column, grouping all tokens carrying that id
  (see §2 for why grouping, not consecutive-run splitting, is the correct rule here).
  ContextASR-Dialogue: one in-text occurrence of a listed `entity_list` string, matched
  case-insensitively on word boundaries against the episode's turn texts.
- **Surface form** — the mention's tokens, lowercased, punctuation stripped, whitespace collapsed.
- **Distinct-entity vocabulary** — number of distinct surface forms, reported both per episode
  (mean) and pooled across the corpus.
- **Repeat payoff share** = (mentions − distinct forms) / mentions. The fraction of mentions that
  are a second-or-later occurrence of a form already seen in the same episode. **This is the
  glossary loop's addressable mass**: a glossary built from a first occurrence can only pay off on
  these.
- **Recurring type share** = fraction of distinct forms occurring at least twice in the episode.
- **Long-span type share** = fraction of distinct forms whose first and last occurrence are more
  than 300 s apart (60 s for ContextASR, whose episodes average 151 s). This is the cross-chunk
  carry question from flight G3: a glossary only needs to *persist across a chunk boundary* for
  these.
- **Proper-noun share** is reported two ways, because they disagree sharply and the disagreement is
  itself a finding: an **annotation-grounded** token share (tokens inside proper-name-typed
  mentions / all word tokens) and a **capitalization heuristic** (non-sentence-initial capitalized
  tokens / all word tokens, excluding "I"). Neither AMI release ships a POS layer — `manual_1.6.2`
  and `auto_1.5.1` were both checked — so no true POS-based proper-noun count is available.

Denominators: AMI word tokens are `<w>` elements excluding `punc="true"`; durations from WAV
headers via `soundfile`. earnings21 tokens are `.nlp` rows (one token per row); durations from the
ConEC word-level `timestamps` alignment (max end time). ContextASR tokens are whitespace tokens of
the episode `text`; durations from the shipped `duration` field.

## 1. The census table

| | **AMI NE layer** | **earnings21 (ConEC)** | **ContextASR-Dialogue EN** |
|---|---|---|---|
| episodes | 117 meetings | 44 calls | 5,273 episodes |
| audio hours | 59.95 | 39.17 | 221.86 |
| word tokens | 564,390 | 362,747 | 1,773,596 |
| **all-entity mentions** | 16,335 | 42,805 | 77,673 (in-text) |
| mentions / hour | 272.5 | **1,092.8** | 350.1 |
| mentions / 1k words | 28.94 | **118.00** | 43.79 |
| **proper-name mentions** | **919** | **10,760** | 58,741 listed |
| proper-name mentions / hour | **15.3** | **274.7** | 264.8 listed |
| proper-name mentions / 1k words | **1.63** | **29.66** | 33.12 listed |
| proper-noun token share (annotation-grounded) | **0.22 %** | **3.61 %** | 8.72 % |
| proper-noun token share (capitalization heuristic) | 2.44 % | 2.58 % | 11.63 % |
| distinct entity vocab, pooled | 265 proper / 2,197 all | 3,019 proper / 7,061 all | 26,854 listed |
| distinct entity vocab, per episode | **3.8 proper** / 57.7 all | **97 proper** / 343 all | 11.1 listed |
| **repeat payoff share** (proper) | **0.211** | **0.578** | 0.232 |
| repeat payoff share (all entities) | 0.510 | 0.632 | 0.232 |
| recurring type share (proper) | 0.255 | 0.382 | 0.231 |
| long-span type share (proper) | 0.178 (all NE) | 0.120 | 0.174 (60 s) |

"Proper-name" is corpus-specific and defined precisely in §2–§4. Bold marks the numbers the verdict
turns on.

## 2. AMI named-entity layer — the scenario-object skew, quantified

117 of the 171 meetings carry NE annotation (468 `*.ne.xml` files across those meetings; 17 of the
18 frozen dev meetings are covered — `IB4002` is not). Types resolve through
`ontologies/ne-types.xml`, whose top level is ENAMEX / TIMEX / NUMEX / ARTEFACT / COLOUR / SHAPE /
MATERIALS.

**Family shares of all 16,335 mentions:**

| family | mentions | share |
|---|---|---|
| NUMEX (CARDINAL, MONEY, MEASURE, PERCENT) | 6,071 | 37.2 % |
| ARTEFACT (DRAWING, MEANS_OF_WORKING, CONSTRUCTED, …) | 4,647 | 28.5 % |
| ENAMEX (PERSON, LOCATION, ORGANIZATION) | 2,038 | **12.5 %** |
| MATERIALS | 1,110 | 6.8 % |
| COLOUR | 968 | 5.9 % |
| TIMEX | 778 | 4.8 % |
| SHAPE | 723 | 4.4 % |

The expected scenario-object skew is confirmed and is large: **ARTEFACT + COLOUR + SHAPE +
MATERIALS = 45.6 %** of all AMI entity mentions are the remote-control design scenario's object
vocabulary (drawings, modelling stuff, plastic, red, curved). Add NUMEX and 82.8 % of the NE layer
is objects, quantities and colours. This is an ontology built to study a design task, not a corpus
rich in names.

**The explicit LOCATION / ORGANIZATION / PERSON shares requested:**

| type | mentions | share of all NE mentions |
|---|---|---|
| PERSON (all subtypes) | 1,674 | 10.25 % |
| LOCATION | 196 | 1.20 % |
| ORGANIZATION | 168 | 1.03 % |

**The PERSON figure is misleading and must be decomposed.** AMI's PERSON branch has four
`PARTICIPANT` subtypes that name a *role*, not a person: PROJECT_MANAGER 149, INDUSTRIAL_DESIGNER
326, MARKETING 314, INTERFACE_SPECIALIST 312, plus EXPERIMENTER 18 — **1,119 mentions, 54.9 % of
all ENAMEX**, whose surface forms are phrases like "industrial designer" and "user interface
designer". These are closed-set role labels, known in advance from the participant roster, and a
glossary cannot learn anything about them that a roster does not already supply. They are exactly
what flight G4 supplies as a participant roster, not what a glossary loop discovers.

A capitalization test does **not** separate them: AMI annotators capitalize role titles, so 91.8 %
of ENAMEX mentions have a capitalized surface, and the most frequent "capitalized entity" in the
whole corpus is `industrial designer` (63). This is why the capitalization heuristic overstates
AMI's proper-noun share (2.44 %) by roughly an order of magnitude against the annotation-grounded
figure.

**Open-vocabulary proper names** — PERSON/OTHER (real first names) + LOCATION + ORGANIZATION,
excluding the five role types — is the quantity the glossary loop can actually address:

- **919 mentions** across 117 meetings and 59.95 hours
- **15.3 mentions per hour**, **1.63 per 1,000 words**, **0.22 % of word tokens**
- **265 distinct forms in the entire corpus**; a mean of **3.8 distinct names per meeting**
- repeat payoff share **0.211**, recurring type share **0.255**
- most frequent forms: `gisella` 50, `real reaction` 38 (the fictitious company), `pierrette` 31,
  `maria` 31, `paola` 28, `milan` 25, `marianne` 25, `maggie` 25, `yalina` 25, `paris` 23

Fewer than four distinct names per meeting, most mentioned once or twice, at fifteen mentions an
hour. For the 18 frozen dev meetings specifically: 3,121 NE mentions, of which 619 capitalized
ENAMEX.

## 3. earnings21 via ConEC — provenance resolved, then measured

**A provenance discrepancy had to be settled first.** The existing derived asset
`derived/entity-inventory/v1/` (33 calls, manifest `carrier_lock_key: "earnings21-original"`,
`runtime_prohibited: true`) did not reproduce under an obvious recount. Testing seven candidate
definitions against all 33 files identified the exact one: **the original earnings21 carrier's
`wer_tags` column, grouping all tokens sharing an entity id — 33/33 exact match**, no other
definition matching any file. Two facts follow. First, entity ids are *nested and can be
non-contiguous* (a DATE span "the first quarter 2020" overlaps a YEAR span "2020"), so
consecutive-run splitting under-counts and must not be used. Second, the inventory is keyed to the
**original** transcripts, not ConEC's corrected ones. Both are reported below; the ConEC-corrected
figures are primary, since ConEC is this study's glossary substrate and its corrections exist
precisely to fix mis-transcribed named entities.

| | original carrier | ConEC-corrected |
|---|---|---|
| word tokens | 362,351 | 362,747 |
| all-entity mentions | 38,367 | 42,805 |
| proper-name mentions | 7,471 | 10,760 |
| proper / hour | 190.7 | 274.7 |
| proper / 1k words | 20.62 | 29.66 |
| proper token share | 2.76 % | 3.61 % |

ConEC's corrections add 3,289 proper-name mentions (+44 %) over the original — a direct measure of
how many named entities the original transcription lost to `<unk>`, homophones and errors.

**Type distribution (ConEC, 42,805 mentions):** DATE 20.0 %, CONTRACTION 19.7 %, ORG 11.0 %,
CARDINAL 10.7 %, PERSON 6.3 %, MONEY 6.1 %, ABBREVIATION 5.1 %, PERCENT 4.6 %, GPE 3.2 %,
YEAR 2.5 %. Proper-name types (PERSON, ORG, GPE, LOC, PRODUCT, FAC, NORP, EVENT, WORK_OF_ART, LAW,
LANGUAGE) are 25.1 % of mentions; numeric and temporal types are 47.6 %.

**Recurrence is the strongest of the three corpora.** Repeat payoff share 0.578 for proper names
(0.632 all entities): well over half of every proper-name mention in an earnings call is a repeat
of a name already spoken in that call. Recurring type share 0.382. Long-span (>300 s) type share
0.120 with a late-mention share of 0.129, so recurrence is real but somewhat front-loaded — a
company or executive is introduced early and returns.

**ConEC also ships a per-call glossary**, the biasing word lists in `earnings21/contexts/*.txt`
extracted from slides, press releases and participant rosters: 44 files, **mean 790 terms per call,
median 715, range 104–2,252**. This is a genuine pre-known supply source, independent of the
transcript, and the only one of the three corpora that has one derived from real-world documents.

## 4. ContextASR-Dialogue English — dense supply, thin recurrence

5,273 episodes, 221.86 h, from `ContextASR-Dialogue_English.jsonl`. Each record carries an
`entity_list` alongside `movie_name`, `dialogue` turns and `text`. **Entity counting used
`entity_list` metadata; the `text` field was read in memory only to locate occurrences and compute
aggregate rates, and no transcript text was written to any output file or runtime path.**

- **11.14 listed entities per episode** (median 11, range 9–21), 58,741 listed in total,
  26,854 distinct corpus-wide
- 79.2 % of listed entities are capitalized-initial and 83.6 % are multi-word — these are genuine
  named entities (titles, character names, voice actors), not common nouns
- 396 listed entities (0.7 %) never appear verbatim in their episode's text
- 77,673 in-text occurrences, i.e. **1.34 occurrences per listed entity** — 350.1 per hour,
  43.79 per 1,000 words
- entity tokens are **8.72 %** of all word tokens, the densest of the three corpora
- **but repeat payoff share is only 0.232** and recurring type share 0.231

The shape is inverted relative to earnings21: very high density and a large, pre-declared entity
vocabulary, but each entity is typically said once. Episodes average 151 s, so there is little room
for recurrence, and the long-span share (0.174 at a 60 s threshold) reflects short episodes rather
than sustained reference. Note also that this is synthetic TTS-rendered dialogue built around a
movie topic — its density is a property of the generation recipe, not evidence about natural speech.

## 5. Verdict — where does the glossary loop have real addressable mass?

**earnings21 is the only corpus of the three where the glossary loop can pay off on its own terms,
and it is where P-GLOSS v1 belongs.** It is the only one that combines all three necessary
ingredients: high proper-name density (274.7 mentions/hour, 29.66 per 1,000 words, 3.61 % of
tokens), a large per-episode vocabulary that a single pass cannot memorize (97 distinct proper names
per call), and — decisively — **recurrence: 0.578 of proper-name mentions are repeats within the
same call**. A glossary built from a call's first pass has, on average, more than half of that
call's remaining proper-name mentions still ahead of it. It further ships a real, document-derived
biasing list (mean 790 terms/call) that supports a supply arm independent of self-built glossaries,
and its long-form calls make the cross-chunk carry question of G3 meaningful.

**AMI's weakness is confirmed, and the true figure is worse than the ~2 % the workplan assumed.**
The capitalization heuristic does give 2.44 %, so "proper nouns ≈ 2 %" is confirmed as a surface
statistic. But that number is inflated by AMI's convention of capitalizing role titles: the
annotation-grounded open-vocabulary proper-name token share is **0.22 %**, an order of magnitude
lower, at **15.3 mentions per hour** and **3.8 distinct names per meeting**. Combined with a repeat
payoff share of 0.211, an AMI meeting offers on the order of one glossary-addressable repeat name
per meeting. **A glossary-gain experiment run on AMI proper names would be measuring noise**, and a
null result there would say nothing about the method. AMI's entity mass is real but sits in
ARTEFACT / COLOUR / SHAPE / MATERIALS / NUMEX (82.8 % of mentions) — the design-scenario object
vocabulary — and in closed-set participant roles (54.9 % of ENAMEX), which a roster supplies
directly. This is an argument for AMI's role in this study being **attribution and long-form
structure** (flights G1 and G4, where the participant roster is the supplied evidence and
cpWER − ORC-WER is the movement of interest), **not glossary gain**.

**ContextASR-Dialogue is a high-density supply testbed but a poor recurrence testbed.** At 8.72 %
entity tokens and 11.14 pre-declared entities per episode it is the strongest surface for testing
whether *supplied* entity lists change transcription — the supply arm — and its scale (5,273
episodes, 221.9 h) supports tight intervals cheaply. But with 1.34 occurrences per entity and a
repeat payoff share of 0.232, a *self-built* glossary has almost nothing left to pay off on within
a 151 s episode. It should be used to isolate the supply effect, never to argue that a glossary
loop carries value across chunks.

**Consequence for the workplan.** The ordering already in the flight ladder is the right one and
this census reinforces it: G2 (P-GLOSS v1) on the earnings substrate is where the loop is
falsifiable. G3's cross-chunk carry form needs a corpus with both length and recurrence; earnings21
supplies it (long-span type share 0.120 over 53-minute mean calls) while AMI does not, so the AMI/
ICSI arm of G3 should be framed as a transfer check under a stated density caveat rather than as
the primary evidence. If a meeting-domain glossary claim is wanted with real mass behind it, the
corpus to look to is the MeetingBank text layer once D3 lands — its city-council proceedings carry
open-vocabulary names (people, districts, ordinances) that AMI's design scenario does not — and
this census should be re-run over it before any meeting-domain glossary claim is made.

## 6. Reproduction

Read-only, CPU, ~35 s total. WSL2 `Ubuntu-24.04`, `~/.venvs/speechrl`,
`PYTHONDONTWRITEBYTECODE=1`. Inputs: AMI `manual_1.6.2` `namedEntities/`, `words/`,
`ontologies/ne-types.xml`, `corpusResources/meetings.xml` and WAV headers; ConEC
`earnings21/transcripts/{nlp_references,timestamps,wer_tags}` and `contexts/*.txt`; original
earnings21 `transcripts/{nlp_references,wer_tags}`; `ContextASR-Dialogue_English.jsonl`;
`derived/entity-inventory/v1/` for the provenance cross-check. No model contact, no downloads, no
audio decoded.
