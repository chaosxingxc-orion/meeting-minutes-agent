# LHCP development semantic gate

`E-MATERIAL-LHCP-DEVELOPMENT-SEMANTIC-GATE` passed its preregistered
development gate. The one-shot verdict is
`LHCP_DEVELOPMENT_SEMANTIC_SIGNAL_PRESENT`.

Readiness passed 25/25 checks. The pinned 639,150,592-byte
`Qwen3-Embedding-0.6B-Q8_0.gguf` was restored to D-drive external storage and
matched SHA-256 `06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`.
The flight completed 38/38 batches and 596/596 embeddings with 1024-dimensional
float32 normalized vectors. It persisted 396 trace rows and 1,188 vector
sidecars. Independent validation returned `TRACE_COMPLETE` with zero errors.

The frozen rule selects the lowest passing threshold, 0.00. At that threshold,
the correct meeting beat its deranged control for 359/396 queries: attribution
precision 90.66%, coverage 100%, 25/25 represented meetings and median cosine
advantage 0.11701. All four gates passed. Every descriptive threshold through
0.05 also passed, but 0.00 remains the registered selection and cannot be
replaced post hoc.

The signal is not uniform. Meeting `856696c53` achieved only 8/19 wins (42.11%)
with median delta -0.01168, and `1109611c551` achieved 9/14 (64.29%). Queries
with multiple frontend speaker labels still reached 88.72% meeting attribution,
but this does not demonstrate speaker-specific routing. First slices without
history scored 24/25, so this experiment also does not isolate a benefit from
prior-keyword context.

Reference and confirmation access remained `NONE`; Omni correction calls were
zero. The external trace is under
`D:/speechrl-data/runs/lhcp-asr-development-semantic-gate/2026-08-28-flight-v1`.
The WSL offline regression passed with 1,617 tests and 25 skips.
