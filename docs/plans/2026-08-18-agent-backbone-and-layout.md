# Agent backbone and repository layout (design record)

Date: 2026-08-18. Status: coordinator design, owner-review pending. This records the two things
the founding workplan left implicit: what the agent's runtime BACKBONE is, and the target
directory layout the engineering tracks build into.

## 1. The backbone: a chunk-sequential episode loop

The frozen Qwen3-Omni core is the only model. The agent is a **deterministic, rule-based
control loop** around it (no second LLM; prompt-level supply only; episode-local state only).
The backbone is the owner-merged **interleaved listening / spelling / revising** scheme made
concrete:

```
EPISODE(meeting audio, shipped materials)
│
├─ INGEST      materials → M0 knowledge (agenda, participant roster, bill index)
│              audio     → chunk plan (topic-aligned, ~40-min window; single-pass
│                          mode when the episode fits — a first-class plan type)
│
├─ per chunk k (the interleaved loop):
│   ├─ LISTEN   core transcribes + attributes chunk k, with the CURRENT episode
│   │           state injected prompt-side (glossary roster, speaker map, format
│   │           instructions) under dose caps
│   ├─ SPELL    control plane mines chunk k's own first-pass output for candidate
│   │           terms and speaker cues (rule extract; LLM-prompted extract is a
│   │           later, separately-measured wire-in)
│   └─ REVISE   normalise → dedupe → gate → APPEND to the episode state
│               (append-only, content-hashed; corrections supersede by hash)
│
├─ TASK HEADS  prompt-driven heads over accumulated state + resolved transcript:
│   ├─ minutes head        (abstract / actions / decisions / problems + evidence links)
│   ├─ qa head             (meeting QA, abstention-aware)
│   └─ attribution head    (speaker-attributed record)
│
└─ OUTPUT      artifacts + run receipts + consumption traces (copy-rate,
               induced-substitution, unsupported-activation) per arm
```

Registered experiment arms are switches on exactly two joints: the REVISE stage (gated /
naive-raw / scrambled-raw / uniform-ungated / deranged / no-carry) and the INGEST provenance
filter (speech-only / metadata-only / combined).

## 2. Component inventory and status

| # | Component | Module | Status |
|---|---|---|---|
| C1 | Corpus adapters (AMI/ICSI NXT; MeetingBank Legistar; M3-SLU; NOTSOFAR) | `corpora/` | NXT DONE (171/171, 0 orphans); others pending their probes |
| C2 | Chunker + chunk plans | `chunking/` | E3 IN BUILD |
| C3 | Episode state store (glossary + speaker map + decision/action ledger; append-only, hashed) | `state/` (glossary pipeline in `glossary/`) | glossary E4 IN BUILD; speaker map + ledger DESIGNED HERE, not yet built |
| C4 | Supply assembly (roster rendering, dose caps, format instructions, arm switches) | `supply/` | NOT BUILT — SAEA rails SupplyPacket pattern importable by recorded decision |
| C5 | Core client (llama-server transport + flight receipts) | `client/` | E6 QUEUED — import the SAEA transport pattern by recorded decision |
| C6 | Task heads (prompt templates + parsers for minutes / QA / attribution) | `heads/` | NOT BUILT |
| C7 | Episode controller (the backbone loop itself: chunk iteration, state transitions, arm orchestration, budgets) | `controller/` | NOT BUILT — **named E7, the true spine** |
| C8 | Metrics stack | `metrics/` | E5 IN BUILD |
| C9 | Instrumentation (copy-rate, receipts, consumption traces) | `instrumentation/`, `runreceipt.py` | E1 DONE |
| C10 | Evaluation harness (arm runner over corpus splits/roles) | `harness/` | NOT BUILT — after E6/E7 |

## 3. Target directory layout

```
papers/meeting-minutes-agent/
├── CLAUDE.md  README.md
├── configs/
│   ├── corpora/        # per-corpus split/role registries (fail-closed role map)
│   ├── arms/           # the registered arm matrix as data
│   └── probes/         # per-flight configs
├── docs/
│   ├── plans/          # this file; founding workplan
│   ├── readiness/      # censuses, split freezes, SAER-M definition, preregs
│   └── checks/         # per-flight evidence bundles (MANIFEST.sha256 convention)
├── scripts/            # thin CLIs (reconcile, flight launchers)
├── src/meeting_minutes_agent/
│   ├── corpora/nxt/ …  # C1
│   ├── chunking/       # C2 (E3)
│   ├── glossary/       # C3 pipeline (E4)
│   ├── state/          # C3 store: episode state, speaker map, ledger
│   ├── supply/         # C4
│   ├── heads/          # C6
│   ├── controller/     # C7 (E7)
│   ├── client/         # C5 (E6)
│   ├── metrics/        # C8 (E5)
│   ├── instrumentation/ + runreceipt.py   # C9
│   └── harness/        # C10
└── tests/{unit,integration}/
```

Rule: experiment arms live in `configs/arms/` as data consumed by `controller/`; no arm logic
is ever hard-coded into heads or corpora.

## 4. Build order (updates the E-track)

E3/E4/E5 (in build) → **E6 client** → **E7 controller + minimal heads** (transcribe+minutes
first; QA head after the MeetingQA floor measurement) → C10 harness → G1 zero-baselines.
Speaker map and decision ledger land inside E7's scope (they are state consumed and produced by
the loop, not standalone modules).

## 5. v2 amendments (owner architecture rulings, 2026-08-18)

### 5.1 LISTEN–SPELL–REVISE is the PERCEPTION loop, not the whole agent

Owner critique accepted: the three-stage loop covers the ASR/knowledge stage only. The backbone
gains an explicit **MinutesTaskManager** layer (the concretization of C7) that owns:

- **Span inventory**: the diarized span table (see 5.2) as the unit of dispatch;
- **Task queue + dispatcher**: typed tasks (transcribe-span, re-listen-span,
  summarize-section, resolve-decision/action, answer-question), rule-routed to the
  perception loop or to task heads; scheduling is deterministic (priority + order rules as
  data, never model-decided in v1);
- **Product assembly**: the minutes state machine (section drafts → evidence links → final
  four-section minutes), consuming the episode state and head outputs.

### 5.2 DIARIZE pre-stage and speaker injection (owner ruling: speakers must be separated)

New pipeline stage between INGEST and chunking: **DIARIZE** — a frozen, pinned, logged
TOOL-level pre-pass producing speaker-attributed spans (cluster ids + turn boundaries). Answer
authority stays with the core; the tool only segments. Arm axis registered: oracle-diar (gold
turns, AMI/ICSI — the ceiling), tool-diar (deployable), no-diar (ablation floor); diarization
error propagation is measured by the E5 confusion-cost instrument. Tool selection is an open
decision: evaluate pyannote.audio vs NeMo vs wespeaker under {no paid, pinnable revision,
license-compatible, WSL-venv installable with owner approval}; until selected, oracle-diar
arms carry G1.

Speaker information enters the loop at three points: (i) LISTEN prompts carry span-level
speaker tags with roster bindings ("Speaker S2 — likely J. Doe, PM, per shipped roster");
(ii) the episode state holds the **speaker map** (cluster id ↔ roster name, with evidence;
updated by REVISE — self-introduction mining in SPELL is the binding mechanism); (iii) the
glossary is speaker-conditioned (each term tagged with its introducing speaker, enabling
per-speaker vocabulary views).

### 5.3 Agent-loop framework: openJiuwen AgentLoop (owner directive)

Ruling recorded: the agent is developed ON **openJiuwen** (openjiuwen 0.1.16.post2, the
SAEA-proven pin), and the backbone is an **AgentLoop** design — NOT ReAct (no model-decided
control flow in v1; the framework tool base stays reserved for a future model-invoked re-ask
arm, per the 2026-08-08 owner ruling) and NOT DeepAgents. Concrete mapping, importing the
SAEA ojw pattern by recorded decision (second cross-repo import):

| Meeting-agent concern | openJiuwen construct (SAEA-proven) |
|---|---|
| Episode outer graph | `Workflow` + Start/End, `create_workflow_session` per episode (timeout env override knob) |
| Task-manager loop | `AdvancedLoopComponent` over Pregel; `FuncCondition` = queue non-empty ∧ budgets hold |
| Perception loop (LISTEN→SPELL→REVISE) | `LoopGroup` linear chain of `WorkflowComponent` nodes |
| Single door to the frozen core | our client component (E6) wrapping the meeting repo's core client — framework LLM clients NEVER instantiated |
| Loop-carried text state (glossary, speaker map, section drafts) | session global state (None-deletion discipline: read back with `.get()`) |
| Heavy objects (PCM, slice registry, receipts) | constructor-injected, never session state |
| Episode batching | `asyncio.gather` + semaphore at the episode level; per-episode loops stay sequential |

Red lines carried over verbatim: openjiuwen never enters `pyproject.toml`; determinism —
linear-chain bodies inherit the SAEA proof, but the task-manager graph introduces BRANCHING,
which puts multiple nodes in a Pregel super-step: **a branch-ordering determinism proof is a
registered precondition before any registered run on this executor**. E3/E4/E5 modules stay
framework-agnostic pure logic; only thin component wrappers touch openJiuwen.

Runtime record: `openjiuwen==0.1.16.post2` (the SAEA-proven pin) was installed into the shared
`~/.venvs/speechrl` WSL venv on 2026-08-18 under the owner's build-on-openJiuwen directive above,
ahead of E6 (`client/component.py`'s `FrozenMeetingCore`, the single-door component this table
names).
