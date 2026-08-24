# E-LOOP-STABILITY flight

Both registered phases completed without retries or failures.

| Phase | Calls | Audio seconds | Wall minutes |
|---|---:|---:|---:|
| Five-arm phase 1 | 7,145 | 75,385.765 | 89.23 |
| L3 convergence round | 1,429 | 15,077.153 | 18.66 |
| Total | **8,574** | **90,462.918** | **109.07** campaign |

Phase 1 contains exactly 1,429 responses for each of `L0-bare`, `L1-recent`,
`L2-global`, `L3-speaker`, and `L4-deranged`. Round 2 contains exactly 1,429
`L3-round2` responses rebuilt from the complete phase-1 L3 pass. Request IDs are unique,
all attempts succeeded, and every receipt budget closed at the registered limit.

The server used Qwen3-Omni Q4_K_M
`d9e2876556e7873e02c0359f832432ee2d67ab7dd0cee3efe0f77fd7a1f4dd85` and Q8 mmproj
`1104376db833f1e89c84834144ac3863340c2cd1ddaeddb39cb0247fb5c20c8d`, one slot,
16,384 context, flash attention, all GPU layers, and Q8 KV cache.

Artifact SHA-256 values:

- phase-1 responses: `c7f07106cce62214062b05883cfd659bad372a1c3ba9f7c273abf25a1958b8bc`
- phase-1 receipt: `51410f46879d8af9dba84067d7008502c210add9cbb97bdad733ab201e9f70bd`
- round-2 responses: `c55d42d2cd659ba69d68a9aa9766add10573beaef1dd8d96c9d0cc45d8bcd6a5`
- round-2 receipt: `902e8f487dd9a31e4355118547920be0b429c31affe66b82f5a5ee9eaf94a394`

The verbose per-request server log was intentionally not archived; the response ledgers,
receipts, server identity, and health-gated configuration are the reproducibility record.
