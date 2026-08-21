# E4-SAFETY-GATE-AUDIT implementation amendment

Date: 2026-08-21. Status: **FROZEN BEFORE TARGET-LEVEL READ**. This amendment records the implementation built from the preregistered design. It changes no candidate, threshold, fold, stratum, metric, or decision rule.

## Frozen implementation

- Audit module SHA-256: `3dbc158a371434037226f7b8f308972ada1b3a26cd172bfca020c10986eb2965`.
- One-shot read CLI SHA-256: `08eb3f1cfc1b8b323ae1d0913f69e09c91c6f2e85b09c726056e0e515e2fa595`.
- Dedicated tests SHA-256: `0b7e8b142082685cf43531797c9ddd03c4499eeed5b1a74b0836b2f4e4352b8b`.
- Offline result: 13 dedicated and E4 regression tests passed in 4.78 seconds in the registered WSL environment.

The tests use synthetic scores only. They verify deterministic bounded fold assignment, frozen width buckets, full-denominator fallback semantics, and distinct decisions for no coverage, no safe gate, scenario dependence, and internal stability. They do not read the real E4-DISJOINT-DIR target-level results.

The CLI accepts the three pinned Pass-0 response files, reconstructs runtime-only features, validates the complete frozen second-pass score cells and official parent verdict, refuses an existing output directory, and writes one machine verdict plus one text report. No model transport is imported or contacted.
