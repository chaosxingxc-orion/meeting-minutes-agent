# E-MATERIAL-LHCP-FULL-POOL-SEMANTIC-EXTRACTOR preregistration

## Question and evidence status

Can the frozen Qwen3 embedding model compress the complete LHCP meeting
material pool into a width-eight local candidate set while preserving enough of
the 206 development oracle opportunity slices? This is a post-reference
development discovery, not independent confirmation.

## Frozen supply and model

Reuse the reference-blind 4,886 development candidates and 396 Pass0 queries.
Candidate keys use `Official material candidate: <canonical>. Context:
<lowest-page source span>`. Queries use the existing retrieval instruction,
current Pass0 text, current Sortformer labels, and at most eight keywords from
only the immediately preceding same-meeting slice. Reference and oracle fields
must not enter either embedding input.

Use `Qwen3-Embedding-0.6B-Q8_0` revision
`370f27d7550e0def9b39c1f16d3fbaa13aa67728`, frozen GGUF and server hashes,
last-token pooling, float32 L2 normalization, batch size 16, no retry, and one
local server. Embed 4,886 keys plus 396 queries: 5,282 embeddings and at most
331 HTTP calls. Rank only candidates from the known current meeting; break
cosine ties by candidate ID. Persist exact request/response files, vector
matrices, rankings, and receipts.

## Reader and decision rules

The prebuilt one-shot reader evaluates widths 1, 2, 4, 8 and 16 against the
already frozen development oracle labels. Width eight is primary. Return
`FULL_POOL_SEMANTIC_EXTRACTION_POWER_READY` only if top eight hit at least 157
opportunity slices across at least 15 meetings. Return
`FULL_POOL_SEMANTIC_EXTRACTION_EXPLORATORY_ONLY` for at least 50 slices across
at least 10 meetings; otherwise return
`FULL_POOL_SEMANTIC_EXTRACTION_INSUFFICIENT`.

## Boundaries and stopping rules

Embedding-model contact requires a new explicit owner authorization after a
fully passing readiness audit. This experiment makes no Omni call and reads no
new reference or confirmation data. Stop on any hash, count, identity, budget,
dimension, output-collision, HTTP, or trace mismatch. A passing development
result nominates a frozen extractor for later independent work; it does not
prove runtime safety, WER gain, speaker specificity, or confirmation success.
