# Founding workplan — meeting-minutes-agent (owner-approved 2026-08-17)

Owner GO 2026-08-17. Four tracks; GPU saturation guaranteed by the flight ladder in §4. Fresh
agent per task (owner ops ruling 2026-08-17: no long-lived agent reuse). Evidence base: the
three 2026-08-17 surveys and SYNTHESIS.md in the umbrella workbench.

Owner rulings folded in: MeetingBank bounded subset is CORE (license verify first; **undeclared
license defaults to fully authorized for program use**, license text or its absence recorded
verbatim); meeteval + rouge-score approved for one-time install into the shared venv;
coreference is de-scoped into QA-measured attribution; cross-meeting memory stays out.

## 1. Engineering foundation (Sonnet, CPU, zero model contact)

| # | Task | Acceptance |
|---|---|---|
| E1 | Repo skeleton: `src/meeting_minutes_agent/`, tests, configs, run receipts (lean — import only the copy-rate instrument pattern by recorded decision; no SAEA exposure apparatus) | pytest green, PYTHONPATH-based (no venv installs) |
| E2 | NXT parser: AMI/ICSI stand-off XML (minutes → dialogue acts → word ids) resolved into transcripts + evidence links | layer counts reconcile with the 2026-08-17 local audit (142 abstractive, 137 extractive+summlink, 139 topics/DA, 171 words/segments) |
| E3 | Chunking engine: ~40-min core cap → topic-aligned chunks + inter-chunk glossary-state interface (episode-local, append-only, hashed) | reproducible chunk plans |
| E4 | Glossary module: extract → normalise → dedupe → gate, plus a naive-arm switch (mandatory control per arXiv 2511.18774) | gate unit-tested |
| E5 | Metrics stack: meeteval cpWER/ORC-WER (installed), MeetingQA F1 scorer, SAER-M definition doc, ROUGE legacy row | metric definitions pinned |
| E6 | llama-server client + flight receipts (frozen core, paid=0, hashable) | smoke passes |

## 2. Data production (Opus, CPU/IO)

| # | Task |
|---|---|
| D1 | Core acquisitions: MeetingQA, ICSI (~9 GB), QMSum, MeetingBank text layer + bounded audio subset (license verify first, owner default applies), M3-SLU release verification, NOTSOFAR-1 second tier. Receipts + lock entries per program schema |
| D2 | AMI split freeze: document BOTH incompatible partition conventions, adopt the full-corpus ASR partition (dev 18) unless evidence says otherwise; materialize E2 outputs under derived/ |
| D3 | MeetingBank subset design: city stratification, dev/eval freeze, segment-alignment validation |
| D4 | Earnings glossary substrate pinned by reference (lock pins, no byte copies) |

## 3. Local analysis (Opus, CPU, zero model contact)

| # | Task |
|---|---|
| L1 | AMI summary reference-multiplicity check → human-agreement ceiling statement |
| L2 | Entity-density census across AMI NE layer / earnings / ContextASR-Dialogue / MeetingBank text (as it lands) — quantifies the glossary loop's addressable mass per corpus |
| L3 | Chunk-boundary statistics (topic-segmentation alignment) |
| L4 | Coordinator-authored: P-GLOSS preregistration (EGTA / naive-arm / 2511.18774 positioning), SAER-M definition, written positioning vs Dixtral and Audio-Mind |

## 4. GPU flights (Opus babysits; order = the saturation ladder)

| # | Flight | GPU est. |
|---|---|---|
| G0 | (SAEA side, immediately) P-A2T + P-SLU probes | ~1–1.5 h |
| G1 | Zero-supply baselines: AMI dev 18 meetings (9.7 h audio) chunked transcription + attribution + zero-shot minutes; ICSI dev mirror; MeetingQA dev QA floor | 8–15 h |
| G2 | P-GLOSS v1 on the earnings substrate: two-pass self-built glossary → static re-injection, + naive / deranged / zero arms | 3–5 h |
| G3 | P-GLOSS v2 meeting form — REFRAMED per the 2026-08-17 entity census (`051053a`): AMI's open-vocabulary proper-name mass is 0.22% of tokens (3.8 distinct names/meeting; repeat payoff 0.211), so a glossary-GAIN experiment on AMI measures noise. G3 is a **transfer check under a stated density caveat**, not a gain test; the loop's falsifiable test is G2 on earnings (29.66 proper names/1k words, 97 distinct/call, repeat payoff 0.578). Any meeting-domain glossary-gain claim requires a MeetingBank entity re-census FIRST (precondition added to D3). AMI's load-bearing roles are attribution and long-form structure (G1/G4) | 4–8 h |
| G4 | Attribution probe: participant-roster supply vs zero (cpWER − ORC-WER movement) | 2–3 h |
| G5 | MeetingBank long-form campaign (post-subset) | sustained |

Timeline: G0 flies immediately (no meeting-side dependency); G1 launches as soon as D2 + minimal
E2 land and fills a full day; E3/E4/E5 complete during G1; G2/G3 chain immediately after; G5
provides sustained load. No GPU idle window after G0.

## 5. Deep-check registered changes (2026-08-17 night — BINDING)

The six-agent adversarial deep check (2 FATAL / 24 MAJOR) produced registered changes recorded
authoritatively in umbrella
`wiki/survey/workbench/2026-08-17-meeting-agent-direction/DEEP-CHECK-SYNTHESIS.md`. Summary of
what now binds this plan: core claim re-scoped to "entity-dense long-form speech" with a
substrate decision gate (ICSI census + MeetingBank re-census vs a pre-declared density floor +
reference-adequacy) before G3/G5; **G2.0 prompt-consumption kill-gate smoke flies before the G2
matrix**; G2 expands to the full registered arm matrix (adds scrambled-raw, uniform-ungated,
no-carry with a carry-delta kill, single-pass with a chunking-cost floor, provenance
factorization speech-only/metadata-only/combined, oracle ceiling); E4 gains machine-enforced
M0/M1 leakage tiers and per-term provenance tags; E5 pins tcpWER−tcORC-WER @ collar 5 s as the
primary confusion cost plus the glossary-induced-substitution and unsupported-activation
diagnostics; MeetingQA headroom language is retired until G1 measures the zero-shot floor;
post-G1 MDE/power gates (AMI-dev MDE > 2 cpWER retires AMI as a gain substrate); an AMI role
registry (one role per meeting, fail-closed) supersedes the plain split freeze; L4 must state
H1/H2 and kill patterns verbatim; positioning corrections (EGTA is LoRA-adapted not frozen; no
EGTA-R-alone number exists — our prompt-only arm is the first such number on this family;
Audio-Mind phrasing purged; the claim is the conjunction, never provenance alone).
MeetingBank: license CORRECTED at acquisition (`84066ef`) — a three-way upstream conflict
resolves to the in-corpus Zenodo `LICENSE.txt`: **CC BY-NC-ND 4.0** (NoDerivatives, stricter
than the HF cards' NC-SA; strictest declaration binds). Internal non-commercial research use is
unaffected; no derived subset or adapted material may be released externally without author
clearance. Valid surfaces unchanged: summarization/QA/segmentation (ASR-derived references — no
WER-family claims). Subset landed: 50 meetings / 81.78 h / 3 cities, meeting-level dev-25 /
held-out-25 splits designed pre-fetch (the official bill-level splits leak across meetings:
791/1,248 meetings span more than one split — never reuse them); Seattle chunk carries a
recorded seasonal bias caveat.

Acquisition-evidence amendment (same night): **ICSI ships NO named-entity layer** (verified
against all 6,437 annotation-archive entries — an upstream gap, not a fetch gap; the survey's
NE expectation was wrong). Consequences: the substrate-gate ICSI entity census must use a
capitalization/NER-tool density ESTIMATE (measurement-grade, never scoring gold), ICSI cannot
host an entity-scored glossary-gain claim, and the meeting-domain entity question now rests on
the MeetingBank re-census alone. ICSI's confirmed roles: second minutes-gold corpus
(abstractive+extractive+summlink present, CRC PASS), six topic segmentations, MRDA dialogue
acts, attribution substrate (71.687 h real meetings, CC BY 4.0 verbatim).
