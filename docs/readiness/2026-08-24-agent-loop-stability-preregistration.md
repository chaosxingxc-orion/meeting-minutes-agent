# E-LOOP-STABILITY preregistration

## Question and frozen surface

This experiment tests whether a post-meeting agent can reorganize a bounded sliding
context after a complete prior pass and reach a reproducible, convergent, non-harmful
state. It is a stability capability test, not a professional-term correction test.

The frozen runtime is `configs/probes/agent_loop_stability/2026-08-24-runtime.json`,
content hash `bd9d31b2875824619f76161b252e3760c9c15be7f9e4289969517dc0b4abbc7d`.
It binds the four Earnings-22 meetings, 1,429 turns, prior Pass-0 files, score manifest,
renderer, launcher, one-shot reader, prompt, and decode settings. Gold/reference data are
available only to the reader after both flights finish.

## Arms and state transition

Each arm reruns every frozen turn. Requests are counter-rotated within meetings.

- `L0-bare`: same-session no-state control.
- `L1-recent`: bounded current-pass transcript tail.
- `L2-global`: L1 plus an extractive prior-pass summary and global keywords.
- `L3-speaker`: L2 plus correctly routed predicted-speaker keywords.
- `L4-deranged`: L2 plus a deterministic other-speaker keyword inventory.
- `L3-round2`: rebuild memory from the complete L3 pass, then rerun L3 once.

The summary is an exact extractive view of earlier model output, not another model call.
Every state item is labelled untrusted. The prompt explicitly forbids inserting memory
unsupported by audio. No external term anchor is added in this experiment.

## Registered decisions

Structural gates require 100% response completeness, context-hash replay, and context
budget compliance. Stability requires L3 consistency to improve over bare by at least
2 percentage points, improve in at least 3/4 meetings versus both bare and deranged, and
the L3-round2/L3 edit delta to be at most 80% of the L3/L0 delta.

Safety gates require L3 WER increase at most 1 point, worst-speaker WER increase at most
2 points, unsupported activation at most 2%, and no increase in output-language drift.
The frozen reader returns `LOOP-STABILITY-REACHABLE` only if every structural, stability,
and safety gate passes; stable-but-unsafe output is `CONTEXT-STABLE-BUT-HARMFUL`.

## Budget and stopping

Phase 1 is 7,145 calls and 75,385.765 audio seconds. Round 2 is 1,429 calls and
15,077.153 seconds. Total budget is 8,574 calls and 90,462.918 audio seconds, zero retries,
temperature 0, seed 0, and 512 output tokens. Any incomplete phase may resume only from
the existing append-only ledger; no partial scoring is permitted. A single one-shot read
is allowed after both phases are complete.
