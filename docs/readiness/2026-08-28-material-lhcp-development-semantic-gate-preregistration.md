# E-MATERIAL-LHCP-DEVELOPMENT-SEMANTIC-GATE preregistration

## Question and claim boundary

On the frozen 25-meeting LHCP development supply, do embeddings of the correct
meeting's official-material keys score above an equal-width deranged meeting?
This is an encode-only material-attribution gate. It does not read reference
transcripts, score WER, call Omni correction, or establish speaker-specific
transcription improvement.

## Frozen inputs and execution

Use the one-write query supply from
`E-MATERIAL-LHCP-DEVELOPMENT-QUERY-SUPPLY`: 200 keys, 396 ordered queries and
its fixed-point-free cyclic derangement. Use the umbrella-pinned
`Qwen3-Embedding-0.6B-Q8_0.gguf` at revision
`370f27d7550e0def9b39c1f16d3fbaa13aa67728`, SHA-256
`06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`.
Run llama-server in embedding-only, last-pooling mode; normalize vectors to
float32 unit length. Batch size is 16, giving exactly 13 key batches and 25
query batches: 596 embeddings in at most 38 HTTP calls, with zero retries.

Persist every request and response, all 396 ranked correct and deranged
candidate lists, decisions, Pass0 bindings and query/correct/deranged vector
sidecars. Position 301 remains marked potentially truncated and is not
re-listened or replaced.

## Development reader and gates

For each query, dispatch when the correct-meeting top1/top2 cosine gap is at
least a threshold in `[0.00, 0.01, 0.02, 0.03, 0.04, 0.05]`. The wrong-meeting
score is unavailable to the selector and is used only by the reader. Select the
lowest threshold satisfying all four gates:

- correct-meeting attribution precision at least 70%;
- dispatch coverage at least 20%;
- dispatches represent at least 19 of 25 meetings;
- median correct-top1 minus deranged-top1 cosine at least 0.01.

The only positive verdict is `LHCP_DEVELOPMENT_SEMANTIC_SIGNAL_PRESENT`.
Failure stops the material-correction branch without threshold search on the
same trace. Passing only permits a separately registered correction-capability
experiment; confirmation remains sealed.

## Stopping rules

Stop before model contact on any hash, model identity, count, output-path,
server, disk-space or reader/validator drift. During the flight, any HTTP,
shape, dimension, normalization or persistence failure stops without retry or
replacement. Never overwrite a prior output directory.
