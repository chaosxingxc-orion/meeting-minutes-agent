# meeting-minutes-agent

An **AI meeting-notes agent on a frozen speech-capable omni core**. The research object is a
training-free control plane — built entirely outside the model — that ingests multi-speaker
meeting audio and produces speaker-attributed transcripts, minutes, and meeting QA, without
changing a single model parameter.

Standalone research repository, owner-admitted 2026-08-17. Status: **ACTIVE** — engineering
foundation complete, first capability probe flown and decided, G1 (first measured floors) in
registration. Client guidance for AI assistants: `CLAUDE.md`.

## Research purpose

Meeting speech is the hardest deployment surface for speech-capable LLMs: hours-long audio,
many speakers, domain-local vocabulary, and questions whose answers are scattered across
turns. Fine-tuning a model per meeting or per organization is not deployable; a frozen core
behind an API is the realistic setting. This repository asks:

1. **Attribution.** Can speaker-attributed records (`speaker A: utt1; speaker B: utt2 …`) be
   produced reliably on a frozen core — and must attribution be *carried by construction*
   (diarization metadata threaded outside the model) rather than *asked of the model*?
2. **Structure.** What task decomposition (chunking, transport packing, episode-local state)
   lets a context-bounded core cover an unbounded meeting without losing cross-turn
   information?
3. **Supply.** Which episode-local knowledge (glossary tables, speaker rosters, rolling
   summaries) actually raises minutes/QA quality when injected into the prompt — and which
   injections backfire? (The sibling SAEA study measured that naive supply can *harm*;
   this repository tests the meeting-domain instance.)
4. **Substrate.** Whether a public corpus adequate for end-to-end meeting-minutes evaluation
   exists at all. (Finding so far: **no** — the gap is documented as unfillable from public
   sources; evaluation is therefore composed from AMI/ICSI + derived QA/summarization layers.)

The end state of this repository is one or more qualified paper candidates on these
questions; large-scale confirmatory campaigns and manuscripts are explicitly out of scope
until separately authorized.

## Architecture (as currently ruled)

All design rulings are recorded chronologically in `docs/decisions.md`; the load-bearing ones:

- **DIARIZE-first pipeline.** Speaker diarization segments the audio *before* any dispatch;
  there are no fixed 40-minute units (measured: zero of 18 AMI dev meetings would fit the
  usable context anyway).
- **Two-level chunking.** Task chunks (180–900 s topic units) plan the work; transport
  slices (90 s, bounds [60, 120] s, zero overlap) carry audio to the core. Slice boundaries
  snap to speaker turns; pure-VAD slicing is demoted to the no-diarization ablation.
  Measured constants: audio costs exactly 13 tokens/second in the pinned llama.cpp build;
  the real per-slot context is 12,288 tokens.
- **Chronological packing only.** Utterances travel in time order; speaker identity rides a
  metadata channel, never a reordered transport. Attribution is assembled *by construction*
  from diarized turn metadata (the "Z-turn" backbone) — the alternative, asking the model to
  attribute via a declared speaker grid, was **retired by measurement** (see P-ATTR below).
- **Episode-local state only.** Glossary/keyword tables and speaker state live and die
  within one meeting episode. Cross-meeting persistence is out of scope by owner ruling.
- **Frozen core.** Qwen3-Omni (GGUF, llama.cpp `llama-server`) reached across an API-shaped
  boundary; zero-parameter training; no second answering LLM. Frozen tool-level components
  (diarization, VAD) are allowed when version- and checkpoint-pinned and logged per contact.
- **Deterministic controller.** The agent loop is built on openJiuwen's `AgentLoop` with a
  linear body — determinism by construction, verified by run fingerprints.

## What has been measured so far

- **E4 unseen-dialogue confirmatory experiment** (287 dialogues; 3,822/3,822 Pass-0
  and 3,096/3,096 second-pass requests): correct-speaker state beat wrong-speaker state
  on carry exact hit rate by 2.16 percentage points (dialogue-cluster bootstrap 95% CI
  [0.11, 4.30] pp). The direction is positive, but the point estimate missed the registered
  5 pp practical-effect gate. Carry NE-WER improved by 3.66 pp versus bare, and overall WER
  improved by 1.86 pp without a harm trigger. Verdict: **DIRECTIONAL-NOT-CONFIRMED**;
  see `docs/readiness/2026-08-20-e4-confirmatory-verdict.md`.
- **E4 confirmatory power audit** (zero model contact): detecting a pre-specified 5 pp
  paired carry improvement requires a deterministic unseen roster of 287 dialogues,
  833 carry mentions, and an estimated 6,922 calls / 22.01 repeated audio-hours after
  clustering and attrition reserves. Verdict: **CONFIRMATORY-FEASIBLE-BUT-LARGE**;
  the audit itself did not authorize contact; the owner later authorized and completed E4-CF.
  See `docs/readiness/2026-08-20-e4-power-verdict.md`.
- **E4 fixed second-pass conditioning smoke** (36 turns, six arms, 216/216): correct
  speaker state improved carry NE-WER from 9.38% to 7.81%, but corrected only two
  baseline misses and beat wrong-speaker state by only two hits; both registered gates
  required three. Verdict: **CONTEXT-SENSITIVE-NOT-SPEAKER-SPECIFIC**. Corrupt state
  degraded carry NE-WER to 15.62%. See `docs/readiness/2026-08-20-e4-conditioning-verdict.md`.
- **E3 legal speaker-state audit** (12 ContextASR dialogues, 151/151 bare Pass-0
  turns): hypothesis-only first-mention state reached 90.04% support precision, 9.96%
  hallucination, and 57.50% same-speaker carry recall. Speaker routing reduced off-speaker
  supply from 49.77% to zero. Verdict: **LEGAL-STATE-READY**; this licenses a fixed second
  pass, not a transcription-gain claim. See `docs/readiness/2026-08-20-e3-state-audit-verdict.md`.
- **C-CTX text-conditioning probe** (32 ContextASR English samples, 5 arms, 160/160
  requests): correct entity context reduced NE-WER by 4.93 percentage points relative to no
  context, but missed the pre-registered 5.00-point reachability gate by 0.07 points. Corrupt
  entity context strongly degraded results. Verdict: **CONTEXT-SENSITIVE-BUT-UNCONTROLLED**;
  see `docs/readiness/2026-08-20-cctx-verdict.md`.
- **P-ATTR capability smoke** (first model contact of this repository; 498/498 requests,
  pre-registered, one-shot read): the declared-grid design failed by *reply-grammar
  capture* — the model keyed on grid indices and dropped speaker labels in 22/24 slices
  while the parser reported success. Free attribution worked (cpWER 0.4352); turn-aware
  attribution-by-construction won (cpWER 0.3657, speaker-confusion 0.0165, 0.437 s/request)
  and is the adopted G1 backbone. Verdict: `docs/readiness/2026-08-18-pattr-verdict.md`.
- **Granularity facts**: `docs/readiness/` records the 13 tokens/s constant, the 12,288
  usable slot, the 40-minute-chunk refutation, and the two-force justification of the 90 s
  transport slice.
- **Corpus substrate audit**: no public corpus supports end-to-end meeting-minutes
  evaluation; the gap is closed as unfillable and the evaluation protocol is composed from
  AMI (NXT annotations, 171/171 meetings parsed), ICSI, MeetingQA, QMSum, M3-SLU, and a
  bounded MeetingBank subset.

## Repository layout

| Path | Contents |
|---|---|
| `src/meeting_minutes_agent/corpora/` | NXT/AMI parsers, MeetingQA loader, role registry (question-usage policy) |
| `src/meeting_minutes_agent/chunking/` | two-level planner + turn-aware transport slicer |
| `src/meeting_minutes_agent/glossary/`, `state/`, `supply/` | episode-local knowledge state and prompt supply |
| `src/meeting_minutes_agent/heads/` | transcribe-attribute, minutes, and QA request builders/parsers |
| `src/meeting_minutes_agent/client/` | transport, budgets, receipts, feature cache, frozen-core client |
| `src/meeting_minutes_agent/controller/` | deterministic AgentLoop body |
| `src/meeting_minutes_agent/harness/` | episode runner |
| `src/meeting_minutes_agent/metrics/` | cpWER/tcpWER, timestamp anti-gaming validator, QA scorers (faithful upstream reimplementation), SAER-M draft |
| `src/meeting_minutes_agent/probes/` | P-ATTR probe builders and scoring |
| `configs/` | frozen probe manifests and the AMI role registry |
| `scripts/` | registry/manifest builders, probe launchers |
| `scripts/data/` | **dataset download + construction for local reproduction** (see its README) |
| `docs/plans/` | founding workplan, agent backbone, design tickets |
| `docs/wiki/` | Chinese research navigation, experiment registry, status and reporting pages |
| `docs/readiness/` | pre-registrations, measured readiness notes, probe verdicts |
| `docs/checks/` | immutable flight/read receipts (hash-manifested) |
| `docs/decisions.md` | chronological record of design discussions and owner rulings |
| `tests/` | pytest suite (800+ tests, offline, no model contact) |

## Getting started

Reference environment: WSL2 Ubuntu-24.04, Python 3.12. Any Linux with Python ≥3.12 should
work for the offline layers (parsers, chunking, metrics, tests); model-contact layers
additionally need a llama.cpp `llama-server` running the pinned Qwen3-Omni GGUF.

```bash
python -m venv ~/.venvs/meeting && source ~/.venvs/meeting/bin/activate
pip install uv && uv pip install -e ".[dev]"
pytest          # fully offline; no data or model required
```

Datasets are **never** stored in Git. Set a data root and follow `scripts/data/README.md`
to download and build the corpora locally:

```bash
export SPEECHRL_DATA_DIR=/path/to/your/data-root
bash scripts/data/setup.sh --help
```

## Research discipline

- **Research Wiki.** Start at `docs/wiki/README.md`; every experiment is registered in the
  Wiki before model contact and linked to immutable pre-registration, receipt, and verdict
  evidence after completion.
- **Pre-registration.** Every model contact is pre-registered (design, sample identity,
  mechanical branch rules, cost ceilings) before it flies; results are read once, through a
  pinned read suite built and reviewed *before* the read; verdicts are decided by the
  registered rules, not post-hoc judgment. Receipts live under `docs/checks/`.
- **Frozen everything.** Model checkpoint, llama.cpp build, tool versions, dataset
  revisions, and split identities are hash-pinned; gold labels and reference transcripts
  never enter runtime prompts.
- **Capability is proven, not assumed** (owner ruling): any capability a design leans on
  must first survive a small-scale measured probe — this rule already retired one design
  (P-ATTR A-grid) that a parser-level check would have waved through.

## Data licenses

This repository contains no corpus bytes — only manifests, hashes, and loaders. Licenses of
the corpora it consumes: AMI and ICSI are CC BY 4.0; MeetingBank is CC BY-NC-ND 4.0 (the
bounded audio subset is used under NC terms; NC carries onto derived results); MeetingQA,
QMSum, and M3-SLU under their respective published terms (see `scripts/data/README.md` for
per-dataset source and license detail). Respect each license when downloading.
