# E-EXTERNAL-COMPANY-IDENTITY-SUPPLY registered read

Decision: **`EXTERNAL-COMPANY-IDENTITY-SUPPLY-INSUFFICIENT`**.

The one-shot zero-model read covered all 1,429 frozen turns. Registered company identities
occurred in 36 reference intervals; Pass0 already rendered an exact identity in 25 turns,
leaving only 15 corrective opportunities. The frozen fuzzy trigger fired eight times and
correctly covered five opportunities: 62.5% precision and 33.3% recall. Only Galp reached
the registered per-meeting distribution floor, so one of four meetings qualified rather
than the required three.

All structural guards passed: no exact identity triggered a correction, reference text was
not used in construction, and every candidate fit the 256-character limit. The observed
false triggers were `goal`→`Galp`, `for telecom`→`SK Telecom`, and
`mno telecom`→`SK Telecom`. This makes blind fuzzy activation unsafe at the frozen
threshold, but even a perfect trigger could cover only 15 opportunities, below the
registered 20-turn floor.

This result stops the four-company identity branch without a model flight. It does not
show that all external evidence is useless; it shows that one legal/brand identity per
meeting is too sparse for the intended per-chunk optimization loop. The external-public-
registry provenance also remains outside current M0 and has not received runtime approval.
