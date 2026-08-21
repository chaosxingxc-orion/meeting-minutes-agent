# E4-CF-MECH verdict: one fixed policy is worth preregistering

Date: 2026-08-21  
Registration: `docs/readiness/2026-08-21-e4-cf-mechanism-registration.md`  
Machine result: `docs/checks/2026-08-21-e4-cf-mechanism-read/verdict.json`

## Decision

> **PREREGISTER-ONE-FIXED-POLICY — `speaker_wrong_disjoint`**

This was a zero-model, post-hoc exploratory read of the frozen E4-CF outputs. It does not alter the official E4-CF decision `DIRECTIONAL-NOT-CONFIRMED`.

Correct-speaker state repaired 66 bare carry misses and broke 21 bare hits, for a net gain of 45. Global state repaired 50 and broke 23; wrong-speaker state repaired 47 and broke 20, each netting 27. The correct-speaker arm therefore supplied the observed 18-hit net advantage over both controls.

## False-hint mechanism

Correct-speaker state produced 109 reference-inconsistent injected-term activations on 100/774 targets. Ninety of 109 came from terms with evidence count one; 108/109 had no supporting mention within the previous two turns. Only one activation co-occurred with a net carry gain and no target-level WER harm. Forty-one occurred on targets with no net carry gain and worse WER than bare. These are descriptive associations, not causal attributions.

Wrong-speaker state produced fewer activations (70 on 64 targets), with stronger and more recent source evidence: 31/70 had evidence count at least three and 40/70 were supported within the previous two turns. This helps explain why a wrong route did not necessarily produce larger aggregate WER: false-hint count is not a one-for-one WER increment, and other word corrections can offset it.

## Frozen predicate screen

| Predicate | Targets / dialogues | Speaker-global hit | Speaker-wrong hit | Speaker-global WER | Speaker-global false-hint target rate | Result |
|---|---:|---:|---:|---:|---:|---|
| all terms repeated | 0 / 0 | — | — | — | — | no coverage |
| recent support ≤3 | 68 / 52 | +3.85 pp | +6.41 pp | -0.09 pp | +1.47 pp | insufficient targets; safety miss |
| inventory ≤4 | 376 / 221 | +5.04 pp | +5.29 pp | -0.36 pp | +2.39 pp | false-hint safety miss |
| **speaker/wrong disjoint** | **418 / 228** | **+3.79 pp** | **+4.24 pp** | **-0.49 pp** | **+0.96 pp** | **selected** |

The selected predicate passed all preregistered exploratory screen rules, narrowly clearing the +1 pp false-hint allowance. It remains a hypothesis chosen on this dataset and requires a new untouched surface.

## Authorized conclusion

The only next policy worth drafting is: use correct-speaker state when normalized correct-speaker and wrong-speaker inventories are disjoint; otherwise fall back to global state. No other strata will be searched. The next action is a zero-model power/roster audit and preregistration draft. Model contact, selective listening, and agent-loop optimization remain unauthorized.
