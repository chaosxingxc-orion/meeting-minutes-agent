# E-MATERIAL-NEW-SURFACE-RUNTIME-GATE preregistration

## Question and sequential boundary

On the reference-unread development split, does an encode-only semantic router
give the correct call's official slide candidates a stable advantage over an
equal-width wrong-call control? The experiment first freezes a zero-model PDF
snapshot, then freezes and runs one development embedding flight. Confirmation
remains sealed unless the development gate passes.

## Candidate and query construction

Only the 20 development PDFs bound by the admitted cohort may be parsed. Candidate
surfaces use the repository's fixed acronym/alphanumeric/title-case extractor.
For each call, sort candidates by
`sha256("material-new-surface-2026-08-26-key-v1:" + call_id + ":" + casefold(surface))`
and keep exactly eight. The first page occurrence supplies a 240-character-radius
source span. Fewer than eight candidates in any call stops the experiment.

Each of the 40 completed Pass0 outputs forms one query. The runtime speaker field
is the non-name label `known-single-speaker:<item_id>`. The reference-audio query
has empty prior context; the answer-audio query may use only the earlier Pass0
reference-audio text from the same item plus up to eight deterministic topic
tokens. No reference transcript or reference-derived field is read. The wrong-call
control is the next ascending `call_id`, cyclic over the 20 development calls.

## Embedding runtime and complete trace

Use `Qwen3-Embedding-0.6B-Q8_0.gguf` with SHA-256
`06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`,
the frozen llama-server binary, `--embedding --pooling last`, float32 L2-normalized
vectors, batch size 16, and no generation. The maximum is 160 key plus 40 query
embeddings in 13 HTTP calls.

Persist exact embedding request/response bodies, one query vector sidecar per
chunk, one reusable key-vector sidecar per call, all eight correct and all eight
deranged candidates and scores, top-1/top-2/gap, source values, context, Pass0
artifact bindings, and an append-only 40-row trace. Validate the frozen trace
schema before reading aggregate results. Missing or drifted input/artifact/vector,
server failure, count mismatch, zero vector, malformed response, or non-prefix
trace stops the flight.

## Development read and gate

Evaluate thresholds `[0.00, 0.01, 0.02, 0.03, 0.04, 0.05]`; select the lowest
threshold with correct-call attribution precision at least 70%, coverage at least
20%, at least 15/20 calls represented, and median correct-minus-deranged cosine at
least 0.01. The wrong-call score is evaluation-only and never available to the
deployment selector. Failure yields `DEVELOPMENT_SIGNAL_INSUFFICIENT` and no
confirmation embedding or Omni correction call. Passing only freezes a threshold
for confirmation; it does not establish WER gain.

EuphoriaYan's 2026-08-26 actual-model authorization covers this sequential
development embedding step after snapshot and trace preflight pass. It does not
authorize confirmation, reference reading, or multi-arm Omni correction.

