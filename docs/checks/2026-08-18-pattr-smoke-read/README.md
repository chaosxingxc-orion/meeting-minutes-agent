# P-ATTR capability smoke — scoring read (2026-08-18)

The registered ONE-SHOT read of the flight recorded in
`docs/checks/2026-08-18-pattr-smoke-flight/`. Scoring only: no model contact, no GPU, no new
bytes. Narrative verdict and the branch decision:
`docs/readiness/2026-08-18-pattr-verdict.md`.

Registration: `docs/readiness/2026-08-18-g1-preregistration-draft.md` §0 (arms, the pre-registered
A-grid-vs-A-free branch, the FLOWN paragraph). Scoring path: `probes/pattr_scoring.py`
(`score_arm`), unmodified, at study commit `8fb94488f9db15a99de9dd72497ac660ba002980`.

## Contents

| file | what it is |
|---|---|
| `verdict.json` | machine record: scoring plan, pins, input hashes, per-slice and per-meeting scores, boundary respect, parse stats, label census, timing, coverage, and the mechanically applied branch decision |
| `report.txt` | the same read rendered for humans, including the full scoring plan as declared before any error rate was computed |
| `MANIFEST.sha256` | hashes of the files in this directory |

## Inputs (hashes in `verdict.json`)

- Frozen manifest `configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json` (sha256 `3c3728cc…`).
- Reply records, never in Git:
  `$SPEECHRL_DATA_DIR/derived/meeting-minutes/pattr-smoke/runs/2026-08-18-pattr-smoke/{a-grid,a-free,a-turn}-responses.jsonl`
  — 24 / 24 / 450 records, every one `outcome=ok`.
- Gold: the AMI NXT layer resolved by `meeting_minutes_agent.corpora.nxt`.
- Metric pins: meeteval 0.4.3, collar 5 s, pins hash `d9a9d122…`.

## Session unit

One **transport slice** — 24 sessions (6 slices × 4 meetings), all three arms on the identical
sessions. Each slice was an independent request and this smoke is context-minimal by design (no
rolling tail, no speaker state), so the core had no means of holding a speaker label stable across
slices; a per-meeting permutation match would have charged it for a capability the flight never
gave it. It is also the only unit meeteval 0.4.3 could score here — see the refusals below.

## Metric refusals (recorded, not worked around)

meeteval 0.4.3 refuses more than 10 speaker streams and its MIMO matching cost explodes with
stream count. Because the A-grid replies put the grid INDEX in the speaker field, that arm carries
up to 154 "speakers" per slice: **21 of 24 A-grid sessions could not yield ORC-WER, and 4 of those
could not yield cpWER either**. Every refusal is recorded per cell in `verdict.json`
(`refusal`), never silently dropped, and the non-degeneracy guard is computed on the 20 paired
sessions both arms could score. A-free and A-turn scored 24/24.
