# Design discussions and decision record

Chronological record of the design discussions and owner rulings that shaped this
repository. Each entry states the ruling, the reasoning that was on the table, and the
document that carries the full text. This file is the entry point the README promises;
the carrying documents remain the documents of record.

## 2026-08-17 — Admission and charter

- **Topic admitted as a standalone research repository** (owner GO by direct order;
  authorization record in the umbrella program repo). The meeting-notes agent is its own
  research object — *not* a sub-case of the sibling SAEA study's knowledge-injection line.
  Meeting corpora belong here; the SAEA study continues on non-meeting datasets.
- **Speaker-dimension information is core and mandatory.** Diarization, within-meeting
  speaker clustering, and speaker-attribution state are episode-local working state and
  fully in scope, including pinned frozen speaker-embedding tools. (This reversed an
  earlier working assumption that speaker identity was a "memory" concern to defer.)
- **Episode boundary.** Episode-local glossary and speaker state are in scope; any
  cross-meeting persistence requires a separate owner decision first.
- **License default** (owner ruling): datasets published without a declared license are
  treated as usable for this research; declared licenses are honored exactly.
- Carried in: `CLAUDE.md`, `docs/plans/2026-08-17-founding-workplan.md`.

## 2026-08-17 — Corpus substrate audit

- Survey of local + public meeting corpora against the requirements matrix (long-form
  multi-speaker audio + reference minutes + QA + attribution annotations).
- **Outcome: the substrate gap is closed as UNFILLABLE** — no public corpus supports
  end-to-end meeting-minutes evaluation on its own. This is recorded as a citable finding,
  and the evaluation protocol is instead composed from AMI/ICSI (audio + NXT annotations),
  MeetingQA, QMSum, M3-SLU, and a bounded MeetingBank subset (CC BY-NC-ND — a license
  correction recorded the same day).
- Carried in: `docs/plans/2026-08-17-founding-workplan.md` (substrate-gate section).

## 2026-08-18 — Backbone and layout

- Agent backbone designed on **openJiuwen's `AgentLoop`** (owner ruling: design on
  AgentLoop, develop on openJiuwen; ReAct/DeepAgents-style free-form loops rejected for
  this object). Linear loop body → determinism by construction, verified by run
  fingerprints. `MinutesTaskManager` owns task decomposition.
- Component inventory C1–C10 and the source layout fixed.
- Carried in: `docs/plans/2026-08-18-agent-backbone-and-layout.md`.

## 2026-08-18 — DIARIZE-first (owner amendment)

- Owner question: "shouldn't we segment the audio with speaker diarization first, and only
  then dispatch? A speech unit should not be 40 minutes." **Ruling: DIARIZE-first** —
  diarization runs before any dispatch; there are no fixed 40-minute units.
- Measurement backing the ruling: audio costs exactly 13 tokens/second in the pinned
  llama.cpp build; the real per-slot context is 12,288 tokens; 0 of 18 AMI dev meetings fit
  a 40-minute unit. The owner's recalled ~90 s optimum was confirmed by two independent
  forces (throughput plateau at 30–90 s; encoder-chunk seams pick 90 s = 3 chunks).
- Resulting two-level design: task chunks 180–900 s (topic units) for planning; transport
  slices 90 s, bounds [60, 120] s, zero overlap, boundaries snapped to speaker turns;
  pure-VAD slicing demoted to the no-diarization ablation arm.
- Carried in: `docs/plans/2026-08-17-founding-workplan.md` (amendment section),
  `docs/readiness/` granularity notes, `src/meeting_minutes_agent/chunking/`.

## 2026-08-18 — Chronological packing is the only transport mode

- Question on the table: pack utterances chronologically (risking speaker confusion) or
  group per speaker (destroying discourse context)? **Ruling: chronological only.**
  Speaker identity rides the metadata channel; the transport never reorders time.
- Target output shape fixed: `speaker A: utt1; speaker B: utt2; …`.
- Carried in: `docs/plans/2026-08-17-founding-workplan.md` (packing-mode ruling).

## 2026-08-18 — Capability must be proven, not assumed (owner ruling) → P-ATTR

- Owner: "we cannot assume the model has this capability and design around it — you need
  small-scale experiments as evidence." Two concerns named: does the *evaluation* support
  utterance-level attribution precision, and does the *model* actually follow a declared
  speaker grid?
- **P-ATTR capability smoke** was pre-registered (three arms, 498 requests, mechanical
  branch rules) as the mandatory gate before any floor experiment, and became this
  repository's first model contact.
- **Verdict (pre-registered branch, one-shot read): the declared-grid design is RETIRED**
  — reply-grammar capture: the model keyed on grid indices and dropped speaker labels in
  22/24 slices while the parser reported success. Free attribution measured cpWER 0.4352;
  **turn-aware attribution-by-construction won** (cpWER 0.3657, speaker confusion 0.0165,
  0.437 s/request) and is the adopted backbone ("Z-turn"). An output-grammar contract is
  now mandatory in every prompt-form experiment, and the diarization-tool choice moved onto
  the critical path.
- Carried in: `docs/readiness/2026-08-18-pattr-verdict.md`,
  `docs/checks/2026-08-18-pattr-smoke-flight/`, `docs/checks/2026-08-18-pattr-smoke-read/`,
  `docs/readiness/2026-08-18-g1-preregistration-draft.md` (§0, §2 arm redesign).

## 2026-08-18 — Prompt-context rulings

- Owner's three-part question: is the meeting's usual core information supplied? are
  prompts specifically optimized? is context sufficient (history + speech together)?
- Rulings bound into the G1 draft: every arm carries a deployment-baseline context block; a
  **P-PROMPT dev sweep** (template × arrangement axes) runs before any floor experiment;
  after a prior corrupt-input incident, the sweep must include **corrupt-context control
  arms**; long-range memory uses a rolling text tail.
- Carried in: `docs/readiness/2026-08-18-g1-preregistration-draft.md` (§0b).

## 2026-08-18 — Split-usage philosophy and derived datasets (program-level rulings)

- **Split usage under training-free research**: train/dev splits are free surfaces for
  optimization and analysis at every discovery stage; only test-split numbers are reported
  as final results; test stays untouched until final reporting.
- **Derived datasets** (e.g., M3-SLU derived from AMI) are not data leakage as long as they
  carry an independent evaluation system — admitted for discovery use.
- Consequence here: the AMI role registry was rebuilt (v1.1) from role-keyed quarantine to
  a question-usage policy — usable-discovery 101 meetings / 4,732 questions,
  reserved-final-reporting 49 / 2,235, untouchable eval-16 (768).
- Carried in: `src/meeting_minutes_agent/corpora/roles.py`,
  `configs/corpora/ami-role-registry.json`, `docs/readiness/` v1.1 note.

## 2026-08-18 — Three locks before large-scale runs (owner gating ruling)

Large-scale meeting runs are gated on three locks, with GPU parallelism maximized inside
that boundary:

1. **Architecture lock** — closed: Z-turn backbone adopted on P-ATTR evidence.
2. **Chunking lock** — closed: two-level 90 s design measured and bound.
3. **Tools / run-flow lock** — open: diarization-tool selection is the critical path
   (selection ticket: `docs/plans/2026-08-18-diarization-tool-selection.md`), followed by
   the P-PROMPT sweep, then G1 registration.

Carried in: `docs/plans/2026-08-17-founding-workplan.md` (§4b owner rulings),
`docs/readiness/2026-08-18-g1-preregistration-draft.md`.

## 2026-08-26 — Reframe the research object as an omni agentic memory system

- **Owner ruling:** under the frozen, training-free constraint, omni-embedding instruction
  optimization alone is too narrow. The research object is now an omni agentic system in
  which an omni embedding model may address an audio-text memory, but is only one component.
- **First priority:** isolate memory use before optimizing collection, compression, or
  retrieval. The initial memory value is raw waveform plus frozen machine text and
  speaker/time/provenance metadata; the main model may receive text and audio.
- **Meeting-minutes focus:** first test decision/action commitment, speaker/owner attribution,
  stance, chronology, and evidence-grounded minutes. Native audio must be compared with
  text-only, paired, and modality-deranged controls.
- The existing single frozen Omni core, typed `MinutesTaskManager`, episode-local boundary,
  model-contact gates, and one-shot reference discipline remain in force. This ruling does
  not authorize model contact or cross-meeting persistence.
- Carried in: `docs/plans/2026-08-26-omni-agentic-memory-use-proposal.md` and
  `docs/wiki/research-roadmap.md`.
