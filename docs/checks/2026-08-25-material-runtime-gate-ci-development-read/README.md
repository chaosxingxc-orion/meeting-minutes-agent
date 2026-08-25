# E-MATERIAL-RUNTIME-GATE-CI development read

The preregistered development read completed with 622 eligible turns, 646 embeddings,
and 41 batched embedding calls. The lowest grid threshold satisfying the frozen aggregate
precision, coverage, and per-meeting dispatch requirements was **0.01**.

At threshold 0.01, 479/622 turns dispatched (77.01% coverage), with 351 correct-meeting
attribution wins (73.28% precision). The median correct-minus-deranged cosine margin was
0.05709. This threshold was written once and frozen before the confirmation read.

This is a construction-isolated development result. Historical references for the six
meetings had already been exposed before this experiment, so the result is not independent
evidence and does not establish transcription improvement.

- [Execution amendment](../../readiness/2026-08-25-material-runtime-gate-ci-semantic-execution-amendment.md)
- [Frozen semantic configuration](../../../configs/probes/material_runtime_gate_ci/2026-08-25-semantic-gate.json)
- [Machine result](development.json)

Machine-result SHA-256: `38a24009b6c5c171eae4ffafaaa8dc829ee1832f7606fc5dc6c89a551af8bb8e`.
