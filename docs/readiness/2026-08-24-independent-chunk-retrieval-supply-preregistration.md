# E-CHUNK-RETRIEVAL-LOO-SUPPLY preregistration

## Question

After same-chunk prior-output retrieval converged but failed consistency and safety, this
zero-model audit asks whether the previous pass contains independent, novel corrective
evidence. It does not contact a model and cannot revise the registered
`CHUNK-RETRIEVAL-NOT-REACHED` verdict.

## Frozen policy

For each frozen turn, its previous-pass text is a query only. A candidate must come from
the same predicted speaker, occur in at least two other chunks, be absent from the current
query, and have token similarity at least 0.75 to a query term. At most four candidates
are retained. Evidence counts chunk presence, not repeated tokens within one chunk.

Reference transcripts are opened only by the one-shot reader to measure whether novel
candidates occur in the target audio interval. They are never used to construct pools,
queries, candidates, or prompts.

## Frozen identities

- runtime: `a2e272852cf35a6a67b9331b405a2472d3d3a217c8738f50693a8ad1898ce4b9`
- score manifest: `163064779b3bf97244612fcd1af5333d04ffafe8a36c97656a32fa54dec70afb`
- Pass0 responses (`4430051`, `4443920`, `4461799`, `4483589`):
  `3f446006c6dd0f63c462902969ea268f34c07330cc33fd8f4c60d06d29f20975`,
  `76866623d1c59a6d253bb32abc7d5a2ce8ae6a0f8394dbb8d0366582a0e3c5b7`,
  `8664437f7317a22cfe2625c5991fd00ffc4c12588a7b2176edd6360f29a2bd83`,
  `acf9309a919c5ea8c467e5130ca9401ab4c82f292f48c79798c298b91dd8c96e`
- retriever: `cac45cf1d191c9027892b3099a0faa308b620b98e59278dad1488491d04f2707`
- one-shot reader: `2cc1a48b7a928bb1738bfa4eeb5e3f9b59852357a0b08cf7b713e0add23b1674`

The pre-read hash-enforcement change is recorded in the
[implementation amendment](2026-08-24-independent-chunk-retrieval-supply-implementation-amendment.md).

## Admission gates

Supply requires at least 400 novel-candidate turns, at least three meetings with 50 such
turns, and at least 25 unique candidates. Relevance requires at least 100 turns with a
reference-supported candidate, at least three meetings with 20 supported turns, and 90%
candidate precision. Structural gates require zero current-query leakage, zero use of the
current turn as evidence, and 100% compliance with the 256-character prompt budget.

Only all-gate success returns `INDEPENDENT-CHUNK-SUPPLY-READY` and admits a separately
registered model flight. Failure stops this output-only fuzzy-retrieval branch; thresholds
must not be tuned on the read.
