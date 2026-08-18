# G1 preregistration DRAFT — zero-supply baselines (AMI dev-18 + MeetingQA floor)

Date: 2026-08-18 (night). Status: **DRAFT — not registered, not flyable.** Owner review +
binding pass required. This is the meeting topic's first flight; it establishes every floor the
later glossary/supply arms are measured against.

## 0. P-ATTR capability smoke (owner ruling 2026-08-18: PRECEDES everything below)

The scheme's LISTEN design assumes the frozen core can attribute text within a multi-speaker
slice to a DECLARED speaker grid. That assumption is UNPROVEN, and the prior evidence is
pessimistic (M3-SLU's headline finding on this core family: models capture what was said but
fail at who said it; AMUSE reports Qwen3-Omni failing multi-speaker reasoning). Per the
owner's ruling — never design on an assumed capability — a small-scale smoke flies FIRST
(merged with the 1-meeting timing smoke; ~25 slices from 3–4 AMI dev meetings, dev being a
free surface under the split philosophy):

| Arm | Design | Measures |
|---|---|---|
| A-grid | declared turn grid in prompt, model fills text per span (the main LISTEN design) | boundary respect + confusion cost |
| A-free | no grid; model attributes freely | what the declared grid buys |
| A-turn | one request per speaker turn — attribution BY CONSTRUCTION (label from the diar layer; model only transcribes) | the zero-attribution-risk fallback's WER and call-cost (expect ~5–10x call count at 4.3 s/call overhead) |

Scored with cpWER-family confusion cost vs AMI gold (the metric family is permutation-matched
per-speaker streams, so model-side cluster naming is irrelevant; utterance segmentation itself
is NOT scored — an honest metric blind spot recorded here). PRE-REGISTERED branch: if A-grid's
confusion cost is not materially better than A-free (grid unused), the LISTEN main design is
RETIRED and G1 adopts the A-turn form (capability assumption replaced by construction);
otherwise the main design is confirmed and the smoke's timing data binds G1's budgets. Either
way G1 proceeds on a VERIFIED path.

## 1. Purpose

Measure the frozen core's zero-supply floors on the meeting stack: (a) chunked transcription +
speaker attribution on AMI dev-18 (9.667 h, the frozen ASR-partition dev set, per-meeting IDs
in the 2026-08-17 split freeze), (b) zero-shot minutes generation (four sections + evidence
claims), (c) the MeetingQA zero-shot floor (retiring the 57.3-vs-84.6 headroom language, per
the deep-check ruling: 57.3 is a fine-tuned DeBERTa, not an LLM floor).

## 2. Arms (all zero-supply; the registered controls from the deep check)

| Arm | Shape |
|---|---|
| Z-chunked | topic-aligned chunk plan (E3), oracle-diar speaker spans, transcribe+attribute head per chunk, minutes head at end |
| Z-single-pass | meetings ≤ core window flown as ONE instance (E3 single-pass plan) — the chunking-cost control: chunking cost = (single-pass − chunked) is a named line item |
| Z-no-diar | chunked, no speaker spans supplied — the attribution ablation floor |
| Z-qa | MeetingQA dev questions over the meeting audio (qa head unstubbed first — precondition), abstention scored against empty string |

Timing rule (BINDING, from the E7b review): time-constrained metrics (tcpWER/tcORC) take
segment timing from the **oracle-diar layer** (AMI gold turn times), never from the transcribe
head's synthetic even-split timestamps — the E5 anti-gaming validator refuses synthetic timing
by design. Arms without diar timing report only non-time-constrained metrics.

## 3. Metrics (E5 pins)

Primary attribution cost: tcpWER − tcORC-WER @ collar 5 s (identical streams, MetricPins
hashed). Secondary: cpWER − ORC-WER (literature row). Minutes: SAER-M (pre-registered draft
definition; per-statement attribution over evidence-linked sentences) + section-completeness
counts; ROUGE legacy row only. QA: macro token-F1 + IoU with empty-string abstention;
abstention and multi-span sub-metrics reported separately; comparability check against the
MeetingQA paper's own scoring script REQUIRED before any cross-paper comparison. Consumption
instrumentation on every arm (copy-rate, per the E1 instrument) even though supply is zero —
it establishes the instrument's floor noise.

## 4. Power discipline (deep-check §3.6)

After G1: per-meeting bootstrap CIs + per-metric MDEs from zero-arm variance; paired
per-meeting design for all later arms; deltas below MDE reported as null. KILL: AMI-dev MDE >
2 cpWER points retires AMI as a gain substrate (NOTSOFAR-1 then inherits, post-census).

## 5. Bindings required before registration

n = 18 meetings (frozen dev list) + [TBD] MeetingQA dev question count; GPU estimate from a
[TBD] 1-meeting timing smoke (9.7 h audio, chunked ≈ 15–17 chunks + single-pass re-fly of
≤40-min meetings — expect the largest flight so far, 8–15 GPU-h projected); budgets and
exposure-equivalent receipts per this repo's lean receipt discipline (FlightReceipt + ledger
note in docs/); AMI role registry (one role per meeting: glossary-discovery / ASR-eval /
QA-eval, machine-checked fail-closed) committed BEFORE flight — the MeetingQA 80:10:10 overlap
matrix from the deep check is its input.

## 6. Preconditions

E-track complete (E1–E7b ✅); qa head + MeetingQA loader ✅ (2026-08-18, suite 584/2 — with the
lossy-flat-file finding: multi-span gold decoded from the BIO file, and the upstream-scorer
comparability gap flagged); AMI role registry ✅ (2026-08-18, PROPOSAL status — commits
`069b910..efee858`); 1-meeting timing smoke (first core contact of this repo — receipt +
owner-visible note) REMAINS; oracle-diar span extraction thin adapter REMAINS.

## 7. Registry-derived binding corrections (2026-08-18)

- "MeetingQA 80:10:10" is RETIRED: the release's own split is 64/48/54 meetings
  (3,007/2,252/2,476 questions).
- **v1.1 (2026-08-18, owner rulings in `docs/plans/2026-08-17-founding-workplan.md` §4b) supersedes
  the paragraph below**: role-keyed quarantine is retired in favour of a question-usage policy keyed
  on eval-16 membership and MeetingQA's own split. Z-final-reporting flies on the
  **reserved-final-reporting class (49 meetings, 2,235 questions)** — the old qa-eval role class
  (42 meetings) plus dev-18's own 7 test-split meetings. Discovery gains a **usable-discovery class
  of 101 meetings, 4,732 questions** (up from 1,918, a 2.47x recovery) spanning every non-eval-16
  meeting's MeetingQA train/dev-split questions, dev-18 included. Only eval-16 (16 meetings, 768
  questions) is untouchable. Details, counts and interpretation calls:
  `docs/readiness/2026-08-18-ami-role-registry.md` §11.
  *Original v1.0.0 framing (retained for provenance):* "Z-qa flies on the qa-eval role class
  (42 meetings, 1,918 usable questions); 5,817 questions are quarantined by role collision (every
  dev-18 and eval-16 meeting carries MeetingQA questions — the registry was load-bearing, not
  formal). Owner decision pending: admitting MeetingQA-dev meetings would recover 1,703 questions
  but shrink the glossary-discovery pool 76 → 45." That owner decision is superseded by the v1.1
  ruling above, which recovers questions by a different mechanism (question-usage policy, not a
  wider R3) and does not touch the glossary-discovery pool at all.
- **SAER-M is scoreable on 12 of the 18 ASR-eval meetings only** (IB meetings lack
  extractive+summlink); minutes-metric power computations use n=12, and IB4001/2/4 lack a
  topics layer, so the chunk plan's plain-duration fallback must be declared for them.
- **M3-SLU is ADMITTED (v1.1, 2026-08-18)** as a derived dataset with an independent evaluation
  system (`docs/plans/2026-08-17-founding-workplan.md` §4b item 2); its content overlap is a
  hygiene note, not a bar: field join is impossible, but a verbatim n-gram content join resolves
  its instances into AMI meetings — including at least one inside our frozen dev-18. Status record:
  `configs/corpora/m3slu-status.json`; narrative: `docs/readiness/2026-08-18-ami-role-registry.md`
  §6.
