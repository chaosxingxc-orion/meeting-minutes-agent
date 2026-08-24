# E-STABLE-ERROR-SUPPLY preregistration

Registered before model contact on 2026-08-24.

This is a four-meeting, discovery-only Pass-0 supply experiment. Frozen runtime manifest:
`configs/probes/earnings22_stable_error/2026-08-24-runtime.json`, content hash
`7a87839ec155a304dcb70bc1df418bdace927e275659d57fe61f44162e351c41`.
The score-side binding hash is
`903f07e767869e109664c8797e13f4f7fb9667f0777cbed0158b9bae8324d7d0`.

The flight ceiling is exactly 1,429 successful calls and 15,077.153 audio seconds. Each
meeting is an independent stage and must produce a complete response JSONL plus receipt.
No intermediate score read is allowed. Failed stages stop; they do not authorize roster
replacement or partial inference.

Runtime identity is the established Qwen3-Omni Q4_K_M model SHA-256
`d9e2876556e7873e02c0359f832432ee2d67ab7dd0cee3efe0f77fd7a1f4dd85`, Q8_0
projector SHA-256 `1104376db833f1e89c84834144ac3863340c2cd1ddaeddb39cb0247fb5c20c8d`,
one slot, context 16,384, flash attention, all GPU layers, and q8_0 K/V cache. The prompt
and decoding parameters are frozen by the launcher and match prior Pass-0 flights.

The scorer and decision table are frozen in
`scripts/read_earnings22_stable_error_supply.py` and the Chinese plan. Gold/reference
data are prohibited from launcher input. This experiment cannot establish correction
controllability, Pass1 gain, or agent-loop monotonicity.
