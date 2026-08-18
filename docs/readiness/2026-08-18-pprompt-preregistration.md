# P-PROMPT template-and-arrangement sweep — REGISTERED

Date: 2026-08-18. Status: **REGISTERED — flyable once the sweep machinery lands** (engineering
ticket after the item-14/diar-seam change lands; flight queued behind the SAEA Stage-2c slot).
Owner GO: 2026-08-18 ("3) Go" on the coordinator's proposed grid). Parent bindings:
`docs/readiness/2026-08-18-g1-preregistration-draft.md` §0b (deployment-baseline context
block; template × arrangement axes; corrupt-context controls — owner amendment; rolling text
tail; output-grammar contract from the P-ATTR verdict). This sweep LOCKS the prompt form for
G1; G1 floors do not fly before it is consumed.

## 1. Question

Which prompt template and context arrangement should the transcribe-attribute head use — and
is the head's quality actually sensitive to corrupted context (the owner's prior
corrupt-input incident, promoted to a measured control)?

## 2. Surface (no new sample identity, no diarization dependency)

The P-ATTR smoke's frozen 24-slice manifest
(`configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json`, seed 20260818, 91–110 s,
zero transport-bound violations, featcache warm) — reused verbatim. Oracle-turn packing
(NXT gold turns via the `NxtOracleDiarization` backend, oracle-tagged): prompt-form
conclusions ride the turn-aware packing G1 keeps as its ceiling arm, so no diarization-tool
lock is prerequisite. Split: usable-discovery (dev) meetings only; the AMI role registry
v1.1 question-usage policy applies; eval-16 untouched.

## 3. Grid (owner-approved shape: 4 × 3 × 24 + 2 × 24 = 336 requests)

**Template axis (4)** — exact texts frozen by the machinery ticket in a hash-pinned binding
manifest BEFORE flight; semantics registered here:
- T1 minimal: bare transcribe-and-attribute instruction + output-grammar contract (control).
- T2 deployment-baseline: T1 + the §0b context block (meeting metadata, speaker roster from
  turn metadata, task framing).
- T3 = T2 + an explicitly EMPTY glossary slot (measures the slot's framing cost before any
  glossary supply exists).
- T4 = T2 + reinforced output-grammar section (grammar contract restated with an explicit
  per-line format example).

**Arrangement axis (3)**: A1 context in system turn, audio in user turn; A2 context in the
user turn BEFORE the audio; A3 context in the user turn AFTER the audio.

**Corrupt-context controls (2 arms × 24, on the fixed reference cell T2/A1 only —
pre-registered to avoid winner-conditioned circularity)**:
- X1 wrong-roster: the context block's speaker roster replaced by a deranged roster from a
  DIFFERENT usable-discovery meeting (seeded, fixed-point-free at meeting level).
- X2 stale-tail: a rolling text tail from a different meeting's slices prepended as if it
  were this meeting's history.

Every arm carries the output-grammar contract (P-ATTR lesson: parser-level success is not
evidence — grammar adherence is scored, not assumed).

## 4. Metrics and mechanical selection rule

Per cell: cpWER (primary), speaker-confusion component, grammar-compliance rate (parseable
lines / total lines), per-slice distributions. Winner := lowest mean cpWER among cells with
grammar-compliance ≥ 0.90; cells within 0.01 cpWER of the best are a TIE-SET broken by (1)
lower speaker-confusion, (2) higher grammar-compliance, (3) simpler template (lower T index),
then simpler arrangement (lower A index). If NO cell reaches compliance 0.90:
**GRAMMAR-BLOCKED** — the contract itself returns to design before G1.

Corrupt-control verdicts (independent, each vs the T2/A1 reference cell):
- **CONTEXT-SENSITIVE(X)**: corrupt arm X degrades mean cpWER by ≥ 0.05 absolute — the head
  consumes the context channel; G1 must carry a context-integrity guard.
- **CONTEXT-INERT(X)**: degradation ≤ 0.01 — the context channel is decorative for this
  head at this scale; the deployment block stays for its G2 supply slots, cited as inert.
- Otherwise **CONTEXT-INDETERMINATE(X)** (report ingredients).

## 5. Cost (registered ceilings)

336 requests; ≤380 core calls; ≤35,000 metered audio-seconds (24 slices × 14 flights each,
91–110 s each; featcache warm so encoder cost is cache-served); ≤1.0 GPU-h (P-ATTR measured
0.437 s/request on this exact surface).

## 6. Discipline

One-shot read; pinned read suite (extending the P-ATTR scoring path in
`probes/pattr_scoring.py` conventions) built and coordinator-reviewed BEFORE the read;
flight receipts + archive under `docs/checks/` mirroring the P-ATTR smoke pair; the exact
template/arrangement texts and the corrupt-arm seeds land in a hash-pinned binding manifest
committed BEFORE flight; no gold transcript text enters any prompt (oracle turns supply
BOUNDARIES and speaker labels only — the same legality line the P-ATTR smoke flew under);
AMI CC BY 4.0 carried.
