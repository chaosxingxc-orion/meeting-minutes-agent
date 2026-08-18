# P-PROMPT sweep — one-shot scoring read (2026-08-18)

The registered ONE-SHOT read of the flight recorded in
`docs/checks/2026-08-18-pprompt-flight/`. Scoring only: no model contact, no GPU, no new bytes.
Narrative verdict: `docs/readiness/2026-08-18-pprompt-verdict.md`.

Registration: `docs/readiness/2026-08-18-pprompt-preregistration.md` §4 (metrics + mechanical
winner rule + corrupt-arm verdicts) and §6 (one-shot discipline). Scoring path:
`probes/pprompt_scoring.py` over `probes/pattr_scoring.py` (`score_arm`), driver
`scripts/pprompt_read.py`, at study commit `1580f92fd9eb627163aae294e2d66697dc70dc17`.

## Contents

| file | what it is |
|---|---|
| `verdict.json` | machine record: all 14 cells' per-slice and per-cell scores, the mechanically applied winner rule, both corrupt-context verdicts, ORC refusals, pins, study commit |
| `report.txt` | the same read rendered for humans (ranked cells, refusal listing, corrupt verdicts) |
| `MANIFEST.sha256` | hashes of the files in this directory |

## Inputs

- Frozen P-ATTR manifest `configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json`
  (sha256 `3c3728cc…`, re-used verbatim by the sweep).
- Reply records, never in Git:
  `$SPEECHRL_DATA_DIR/derived/meeting-minutes/pprompt-sweep/runs/2026-08-18-pprompt-sweep/{arm}-responses.jsonl`
  for the 14 arms — 24 records each, every one `outcome=ok`, fingerprinted in the flight
  archive's `run-dir-artefacts.sha256`.
- Gold: the AMI NXT layer resolved by `meeting_minutes_agent.corpora.nxt` (boundaries + labels
  reference extraction only; no gold ever entered a prompt).
- Metric pins: meeteval 0.4.3, collar 5 s, pins hash `d9a9d122…` (identical to the P-ATTR read).

## Session unit

One transport slice — 24 sessions (6 slices × 4 meetings), identical for all 14 arms; every
arm's requests were independent (no rolling tail in the grid cells), mirroring the P-ATTR read's
session-unit rationale.

## Read-attempt history and the forced ORC deviation (recorded, not worked around)

The read was attempted twice at flight commit `f004e02` and both attempts were **OOM-killed by
the kernel (~56 GB anon RSS) before writing a single output byte** — `verdict.json` never
existed, so the one-shot guard's read count was still zero. Diagnosis (structure-only census +
a subprocess feasibility probe under RLIMIT_AS, feasibility flags only, no error rate surfaced
before this read): meeteval 0.4.3's ORC-WER dynamic program needs roughly
`n_ref_utterances × ∏(stream_words+1) × ~24 B`; the byte-identical T1-A2/T1-A3 replies on
IS1008d slice0005 parse to 7 hypothesis speaker streams, pushing that to ~7.9e9 (≈190 GB) —
unconditionally infeasible on the 54 GB host. cpWER (Hungarian) is cheap on every flown reply.

Amendment `1580f92` (committed BEFORE this read; decided before any error rate was read,
mirroring the P-ATTR read's own recorded meeteval refusals): `score_slice` refuses to attempt
an ORC term whose state-space bound exceeds `ORC_DP_BOUND_CAP = 2.0e9` (inside the observed 8×
feasible/infeasible gap) and records any in-attempt `MemoryError` the same way; a refused slice
keeps its REAL cpWER (same committed `compute_cp_wer`), carries `confusion_cost=None` plus a
per-slice `orc_refusal` reason, and cell means skip refused slices while exposing
`n_confusion_refused`.

Outcome in this read: **exactly 2 ORC refusals** (T1-A2 and T1-A3 on IS1008d slice0005, the cap
path; zero MemoryError refusals), so **cpWER and compliance are complete for all 336 replies**
and every confusion mean covers ≥23/24 slices. The winner rule's primary criterion was never
touched by the deviation.

Execution: attempt 3, 2026-08-18 19:11:07Z → 19:19:28Z, exit 0, under `ulimit -v` 32 GiB
(address-space armor so any residual explosion would have become a recorded refusal, never a
host OOM kill).
