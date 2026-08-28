# E-MATERIAL-LHCP-BM25-LOCAL-EXTRACTOR preregistration

## Evidence status and question

This post-reference development discovery tests whether a deterministic,
reference-blind lexical extractor can preserve the opportunity supply found in
the 4,886-candidate oracle pool. It ranks candidates without reading reference
text; frozen oracle labels are used only by the one-shot evaluator.

## Frozen ranker

For each meeting, build one BM25 index over its complete source candidate pool.
Each candidate document is three copies of its normalized canonical followed by
the normalized source span from the lowest page, lexical path, and lexical span
occurrence. Use Robertson BM25 with `k1=1.2`, `b=0.75`, and
`log(1 + (N-df+0.5)/(df+0.5))` IDF. Break score ties by candidate ID.

Rank two fixed reference-blind query variants independently:

- `current_only`: normalized current Pass0 slice;
- `current_plus_prior`: current Pass0 slice followed by the at-most-eight
  already frozen immediately preceding same-meeting keywords.

Evaluate widths 1, 2, 4, 8 and 16. Do not tune tokenization, canonical weight,
BM25 constants, query fields, or widths after reading the ranking results.

## Decision rules

The primary extractor width is eight. A variant is
`BM25_LOCAL_EXTRACTION_POWER_READY` only when its top eight contain at least one
oracle wrong-to-correct candidate in at least 157 slices across at least 15
meetings. It is `BM25_LOCAL_EXTRACTION_EXPLORATORY_ONLY` for at least 50 slices
across at least 10 meetings. Otherwise it is
`BM25_LOCAL_EXTRACTION_INSUFFICIENT`.

Report both variants; do not choose a future policy from this same development
read without a new freeze. A passing result only nominates BM25 as an
embedding-pool constructor. It does not authorize embedding or Omni contact.

## Claim boundary

The oracle labels came from already opened development references. This audit
does not estimate independent generalization, runtime dispatch precision, WER
gain, false-hint safety, speaker specificity, or confirmation performance.
Confirmation remains sealed and gold membership may not enter ranking.
