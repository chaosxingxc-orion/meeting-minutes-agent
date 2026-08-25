# Meeting Material Supply One-Shot Read

`E-MEETING-MATERIAL-SUPPLY-AUDIT` completed its sole reference read on
2026-08-25. The verdict is `MEETING-MATERIAL-SUPPLY-INSUFFICIENT`; no Omni call
was made.

## Result

| Metric | Frozen gate | Observed | Pass |
|---|---:|---:|---|
| Eligible meetings | at least 3 | 3 | yes |
| Corrective turns | at least 20 | 3 | no |
| Meetings with at least 3 corrective turns | at least 3 | 1 | no |
| Trigger precision | at least 90% | 0.72% (3/418) | no |
| Trigger recall | at least 50% | 10.00% (3/30) | no |
| Precision advantage over deranged | at least 30 pp | 0.72 pp | no |
| Provenance / construction leakage | complete / zero | 49/49 / zero | yes |
| Exact-form / 256-character violations | zero / zero | zero / zero | yes |

The reference contains 30 material-candidate opportunities across the three
eligible meetings, but the frozen fuzzy router converts only three into correct
activations. It also produces 415 false activations. Galp and TeamViewer produce
zero correct activations; all three correct activations occur in Jeronimo Martins.
The deranged arm produces 336 false and zero correct activations.

## Interpretation

Official material provides a provenance-bearing inventory, but material presence
does not make its terms safe per-chunk hints. The fixed equal-width
`SequenceMatcher >= 0.75` rule is especially confusable for short abbreviations:
the saved examples repeatedly activate items such as `OCF`, `REE`, and `LNG` on
unrelated text. This is a failure of the frozen `ORG -> SUPPLY` router, not evidence
that the Omni model cannot use correctly routed material.

Per preregistration, the threshold, aliases, and candidate set will not be tuned on
this read. A successor requires an independent holdout and a new preregistration;
it should separate abbreviations from proper names and require stronger,
runtime-legal evidence than raw character similarity.

The complete machine-readable result is [verdict.json](verdict.json).
