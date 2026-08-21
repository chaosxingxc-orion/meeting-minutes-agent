# E4-SAFETY-GATE-AUDIT preregistration

Date: 2026-08-21. Status: **REGISTERED BEFORE TARGET-LEVEL READ**. The owner authorized a zero-model attempt and explicitly raised scene dependence as the main concern. No model contact is authorized.

## Scope

The audit reuses the complete E4-DISJOINT-DIR outputs without producing, retrying, or replacing any transcription. A deployable policy selects the frozen speaker output when a runtime-only gate accepts and otherwise falls back to the frozen global output; every target remains in the denominator. The four candidates, their order, thresholds, four deterministic dialogue folds, inventory-width strata, coverage/safety/utility gates, and decision order are frozen in `docs/plans/2026-08-21-e4-safety-gate-audit.md`.

This is post-hoc exploratory analysis. The current surface contains ContextASR movie dialogue only. Cross-domain scalability is unidentifiable by design; even the strongest possible label is `WITHIN-SURFACE-STABLE-CANDIDATE`.

## Frozen inputs

- Pass-0 runtime manifest SHA-256: `046db6f5b8869dba152cab0c5fe2c22543739ad3e8a7ce531e41e067c6e883d5`.
- Pass-0 response SHA-256: stage20 `2786a0c5edde176f7fc85f5dd846457b2d69333fa47aa149f3ff88f3871e4197`; stage40 `52f927700dd913f6da31fba3c24bff712cb90046b3d68bf7414ae25022cb4950`; stage60 `90e6beab340cef2d46adeb9c7d1476ad6f518aea49c7b2648d5f41d0cda9dc84`.
- Direction runtime binding SHA-256: `72d62ad06cccd43f699285a6c50f87697ba02c47c248215e58cead39ea71e28d`.
- Direction score binding SHA-256: `1f2e59153e20dd243121f0f1d3e9534292313d8f7fa1cb121e0db6c2744b4330`.
- Complete direction responses SHA-256: `a15f4af4f8f2c379557c1b5176c23a2755b553a9f513cde6d72111adfcd06bf5`.
- Official direction verdict SHA-256: `a897ea267adca9dc92caecd0ec3fbf02b7bf72556f98130d132e62939d65a32e`.

The runtime feature builder may read Pass-0 hypotheses and runtime speaker/turn metadata. Gold reference and carry labels enter scoring only after features and candidate inclusion are fixed. Second-pass text cannot define a feature, threshold, fold, or stratum.

## Implementation freeze and read discipline

Implementation and tests will be added after this design commit. Before the sole read, an amendment must record their SHA-256 values and offline test result. The read output directory must not exist beforehand and must refuse overwrite. Only the frozen machine verdict may drive the decision. No target-level rule may be added after reading.
