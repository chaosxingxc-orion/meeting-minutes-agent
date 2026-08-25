# E-MATERIAL-RUNTIME-GATE-CI Pass-0 preregistration

Date: 2026-08-25. Status: **REGISTERED BEFORE OMNI CONTACT**. The owner explicitly
authorized Pass-0 after the six-meeting material cohort passed admission. This remains
`CONSTRUCTION_ISOLATED_EXPLORATORY`: historical reference exposure prevents an
independent-confirmation claim.

## Frozen runtime

The reference-blind runtime manifest is
`configs/probes/material_runtime_gate_ci/2026-08-25-pass0-runtime.json` (file SHA-256
`aa72dcd74b295e94c98aebbcc9c5b562b1d5325d3b22d34342c9d8e6bd5f08c5`, content hash
`48034facd2b1b6a3fef3848fa5cfbd411e48409e177d28a9fcfef1840fe6075b`). It freezes all
Sortformer turns for the three development and three confirmation meetings. Only a
turn above 120 seconds may be mechanically split. No turn may be selected, removed, or
reordered using material, reference, retrieval, or model output.

The hard ceiling is exactly **1,639 calls and 22,678.133 audio seconds**: development
`4474506` 244/3,733.005, `4479944` 149/3,672.032, `4483506` 318/3,695.076;
confirmation `4483633` 291/3,290.440, `4484563` 343/5,012.388, `4485244`
294/3,275.192. Each meeting is an independent fail-closed stage with an append-only
response JSONL and receipt. Existing outputs are never overwritten; any failed stage
stops the campaign and does not authorize replacement.

## Fixed model and request

Use Qwen3-Omni-30B-A3B-Instruct Q4_K_M SHA-256
`d9e2876556e7873e02c0359f832432ee2d67ab7dd0cee3efe0f77fd7a1f4dd85` and Q8_0
projector SHA-256 `1104376db833f1e89c84834144ac3863340c2cd1ddaeddb39cb0247fb5c20c8d`,
one slot, context 16,384, flash attention, all GPU layers, and q8_0 K/V cache. The prompt
is the byte-frozen bare `T1-A1` rendering, content SHA-256
`f2f32b5572adbceacf678536239682d4271411851f57a80e3a43a6477379e0d2`, with no
material, reference, glossary, summary, keyword, identity, or prior hypothesis input.
Decoding is temperature 0, seed 0, maximum 512 tokens, timeout 300 seconds, zero retries.

## Frozen implementation and read

Launcher SHA-256 is `a3a5f317137170f1a3254ad0a6ff42c0bc6a0534200ca05ebc132bfabfe85ac7`.
The prebuilt reference-blind structural reader SHA-256 is
`a20c10dc3b9cc5a328d2b0e2e669b3cebf793e480b1c8cbdd8bcf05bcef2d80f`.
It checks exact order/count, successful outcomes, non-empty text, retries, and response
hashes only. It cannot read reference text or score transcription quality. Pass-0 only
creates a frozen baseline for the separately registered zero-model semantic gate; it
does not authorize embedding, threshold fitting, Pass-1, or any gain claim.
