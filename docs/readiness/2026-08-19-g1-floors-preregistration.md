# G1 floors campaign — REGISTERED (owner GO)

Date: 2026-08-19. Status: **REGISTERED — owner GO granted same day ("按你的建议执行")**;
G1-PATH flies first ("少量探测" ruling), then the VAD supplement, then the floors campaign. All four locks are closed: architecture (Z-turn, `93aa7ee`/`d3cbf4a`),
chunking (two-level 90 s), prompt form (T1-A1, `b6c07f0`), tools/run-flow (TOOL-LOCKED(B)
adjudication 2026-08-19). PRECOMP wave-1 is COMPLETE (`4631f68`): all dev-18 meetings carry
cached tool-turn AND oracle-turn slice sets (367 + 371 slices, featcache warm).

## 1. Purpose

Measured DEPLOYMENT-TIER FLOORS for the meeting-minutes agent — descriptive, no branch
lattice: per-arm scores, the deployment-vs-ceiling gap with uncertainty, and per-meeting
tables. These floors are what G2's supply interventions must beat.

## 2. Samples

All **dev-18** meetings (9.67 h; usable-discovery; eval-16 and reserved untouched). Minutes
scoring on the SAER-M scoreable subset (n=12); QA on the usable-discovery questions attached
to dev-18, seeded cap **N=200** (seed 20260818; cap disclosed).

## 3. Arms

| Arm | Transport | Turn source | Heads |
|---|---|---|---|
| Z-turn (deployment) | 90 s turn-aware, cached | pinned diar (TOOL-LOCKED(B)) | transcribe-attribute + minutes + qa |
| Z-oracle (ceiling) | 90 s turn-aware, cached | oracle NXT turns | transcribe-attribute + minutes + qa |
| Z-free (attribution-free baseline) | same tool-turn slices, NO turn metadata in prompt | — | transcribe only |
| Z-nodiar (ablation) | pure-VAD 90 s slicing | none | transcribe only |

All prompts use the locked T1-A1 form (bare instruction + output-grammar contract in
system, audio alone in user; context block EXCLUDED per the P-PROMPT verdict). Z-nodiar's
slices are NOT precomputed — either a small PRECOMP supplement (~370 slices, ≈0.6 GPU-h)
runs first or the arm pays lazy encode in-flight; the supplement is the default.

## 4. Metrics (per arm × meeting, plus pooled)

Attribution/transcription: cpWER, speaker-confusion component, tcpWER−tcORC@5s (primary
confusion cost), grammar-compliance. Minutes: SAER-M (n=12). QA: the reimplemented upstream
scorer (max-over-alternatives) on the capped question set. **MDE/noise discipline (panel
mandate)**: the deployment gap (Z-turn − Z-oracle) is published with a per-meeting-clustered
paired bootstrap CI (shared bootstrap module pattern); the P-PROMPT server-state spread
(0.085 cpWER same-request) is cited as the single-run noise reference; no comparison is
narrated as real unless its CI excludes zero. Capped-reply counts disclosed per arm.

## 5. G1-PATH (flies first, on GO)

Two meetings (ES2011a, IS1008a), ALL arms and heads end-to-end: validates plumbing,
budgets, receipts, and the per-slice dispatch chain. Structural pass/fail only (completion,
budget adherence, parser health); NO metric conclusions. ~250 requests, ≤0.5 GPU-h.

## 6. Cost (registered ceilings, campaign total incl. PATH and supplement)

≈2,100 flight requests estimated (transcribe ≈1,475 across four arms; minutes ≈240; QA
≈400) + ~370 supplement encodes. Ceilings: **≤2,900 core calls; ≤6.0 GPU-h; ≤8 h wall** —
executed in RESUMABLE CHUNKS ≤50 minutes each, server owned per chunk (the 60-minute
harness-reap rule, wave-1 lesson). Throughput basis: 3.7 s/request (P-PROMPT measured).

## 7. Discipline

Two-stage flight protocol per chunk; receipts + archive under `docs/checks/2026-08-19-g1-*`;
one-shot read via a pinned scoring CLI built and coordinator-reviewed before the read;
no gold transcript text in any prompt (oracle turns feed the SLICER only; NXT reference is
scoring-side); AMI CC BY 4.0; MeetingQA CC BY-NC-SA carried on QA-derived numbers.
