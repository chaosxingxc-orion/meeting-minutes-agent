# CLAUDE.md — meeting-minutes-agent

Standalone research repository: an **AI meeting-notes agent** on a frozen speech-capable omni
core. Owner-admitted 2026-08-17 by direct order; authorization record: umbrella
`wiki/experiments/papers/meeting-minutes-agent/2026-08-17-owner-go-and-paper-execution-contract.md`.

## Research object

An agent that ingests multi-speaker meeting audio and produces speaker-attributed records,
minutes, and meeting QA, through four integrated functions:

1. speaker decomposition (who spoke, when);
2. per-speaker content extraction;
3. coreference and relation resolution across speakers and turns;
4. an **episode-local keyword/glossary table** built and maintained during the meeting and
   statically injected back into the prompt;

integrated with the **interleaved listening, spelling and revising** control scheme (design
lineage imported from the SAEA study's 2026-08-10 readiness note by recorded owner decision —
the first and so far only cross-repo import).

## Topic boundaries (owner rulings, 2026-08-17)

- This is a **standalone agent research topic** for AI Meeting Notes academic problems. It is
  not framed as knowledge injection; the knowledge-injection research object stays with the
  SAEA study, which continues on non-meeting datasets only. Meeting corpora belong here.
- **Fresh start**: not bound by the SAEA study's probe framework, exposure apparatus, or
  experiment ladder. Import assets only by explicit recorded decision.
- **Speaker-dimension information is core and mandatory** (owner ruling 2026-08-17):
  diarization, within-meeting speaker clustering, and speaker-attribution state — including
  pinned frozen speaker-embedding tools — are episode-local working state and fully in scope.
  The SAEA study's deferral of speaker-embedding retrieval applied to that study's
  knowledge-supply mechanism and does not constrain this topic.
- Episode-local glossary and speaker state are in scope; **only cross-meeting persistence**
  (recognizing returning speakers or carrying state across meetings) **requires a separate
  owner decision** before any implementation.

## Program-wide invariants (do apply)

- Frozen core, training-free: no parameter updates, no task-trained model.
- English-only documents: root Markdown, docs, code comments, commit messages.
- No data, weights, or audio in Git; large bytes live under `SPEECHRL_DATA_DIR`.
- Paid API spend = 0.
- Human speech and its linguistic content only.

## Environment

- WSL2 `Ubuntu-24.04`; Python 3.12 in `~/.venvs/speechrl` (shared program venv — never
  `pip install` into it from agents; report missing dependencies instead).
- Data: `SPEECHRL_DATA_DIR=/mnt/e/chao_workspace/exploring-l4-intelligence/speechrl-data`.
- Inference: llama.cpp `llama-server` with the pinned Qwen3-Omni GGUF (ext4 copy under
  `/home/chao/models/`); dataset identity is pinned in umbrella `docs/datasets.lock.json`.
- `.gitattributes` enforces LF. The repository uses `master`.

## Open surfaces (fixed by the first design records, not by this file)

Carrier selection (AMI and the 2026-08-17 survey shortlist), evaluation protocol (minutes
quality, attribution accuracy, QA), the glossary-loop design, and the interleaved-scheme
integration plan.
