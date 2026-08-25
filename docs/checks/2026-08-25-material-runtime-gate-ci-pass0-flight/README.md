# E-MATERIAL-RUNTIME-GATE-CI Pass-0 flight

The preregistered six-meeting flight is structurally complete: **1,639/1,639 calls**,
22,678.133 audio seconds, zero empty replies, and zero retries. All six meetings completed
in their frozen development-then-confirmation order. The local server was stopped after
the final response.

The flight used the pinned Qwen3-Omni Q4_K_M model and Q8_0 projector, one slot, context
16,384, flash attention, all GPU layers, and q8_0 K/V cache. Every request used the bare
`T1-A1` prompt with temperature 0, seed 0, maximum 512 tokens, no material or prior state,
and no retry. The runtime manifest content hash is
`48034facd2b1b6a3fef3848fa5cfbd411e48409e177d28a9fcfef1840fe6075b`.

The prebuilt reference-blind reader checked only order, count, outcome, non-empty text,
retry attempts, and artifact hashes; its machine decision is `PASS0_COMPLETE`. It did not
read references or measure transcription quality. Therefore this evidence establishes a
complete frozen baseline supply only. It does not show that material retrieval works,
that a dispatch threshold generalizes, or that any later pass improves WER.

- [Preregistration](../../readiness/2026-08-25-material-runtime-gate-ci-pass0-preregistration.md)
- [Runtime manifest](../../../configs/probes/material_runtime_gate_ci/2026-08-25-pass0-runtime.json)
- [Structural verdict](verdict.json)
- [Machine flight summary](flight-summary.json)
