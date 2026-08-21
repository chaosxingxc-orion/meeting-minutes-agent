# E4-CF-MECH frozen-output mechanism audit — REGISTERED

Date: 2026-08-21. Status: **REGISTERED; the real stratified read has not run**. This is a zero-model, post-hoc exploratory audit. It cannot modify or replace the official E4-CF decision `DIRECTIONAL-NOT-CONFIRMED`.

## Question and protected boundary

The audit asks why correct-speaker state produced a small positive routing effect and 109 false-hint activations. It reconstructs only runtime-visible state features from frozen Pass-0 hypotheses and turn/speaker metadata. It will not emit raw hypotheses, references, entities, terms, or target identifiers. Gold-derived score bindings are used only for aggregate outcome classification.

The complete frozen taxonomy, candidate predicates, thresholds, and decision order are in `docs/plans/2026-08-21-e4-cf-mechanism-audit.md`, sha256 `f89b5bdc3b3bf2e6f221125475b998a400730b4f5a36fe20db769ed0b93b481a`.

## Frozen inputs

| Input | SHA-256 |
|---|---|
| Pass-0 runtime manifest | `8a70c0c1e8e9f029e5b5a2bcf3f695b71edb1f1607c2e3f336bb495b9fa5d8a1` |
| Runtime binding | `2daf5ec4b10df60b66d9e5751ddbd32eaa49a9fd61ff5a1b41c6b8686a0dfa7d` |
| Score binding | `13da03acf69848b15b4ed79434a9f9de8ac7e05669e7f04a703b5e5601e15df7` |
| Pass-0 responses | `26cd1977f1181fa3da7e4d9c67fd3ec66684428e8de3e9b57a6a0d7efee45e2f` |
| Second-pass responses | `711d8844c53199374ec6738d280e1d8e3594155b63d1a80af111d2f85def5989` |
| Official E4-CF verdict | `20c654267aa05f0db579d2cc02d62cdaa812335af71f5cf49c68dce3e52269d9` |

## Frozen implementation

| Artifact | SHA-256 |
|---|---|
| `src/meeting_minutes_agent/probes/e4_mechanism.py` | `d7a0fed96e811528175110372f711e1a3b5c6f4153e855816f9416187118d174` |
| `scripts/e4_mechanism_read.py` | `c6127084b51240989b9b3b32325f9e25b29179e143ddb6fb96693dc6c5bba1ea` |
| `tests/unit/probes/test_e4_mechanism.py` | `c84a960d7be9f0f5cfa6dab58f9303bb0352feb45e4c3a440fe1c71d4dadc537` |

Pre-read verification: Python compilation succeeded and the dedicated suite passed `4/4`. The output directory `docs/checks/2026-08-21-e4-cf-mechanism-read/` did not exist at registration.

## Single-read rule

The registered CLI must run once and must refuse an existing output directory. It writes only aggregate `verdict.json` and `report.txt`. The machine decision is exactly one of `NO-ACTIONABLE-MECHANISM`, `PREREGISTER-ONE-FIXED-POLICY`, or `SAFETY-RISK-DOMINATES`. A policy-selection result permits only a new preregistration draft; it does not authorize model contact.
