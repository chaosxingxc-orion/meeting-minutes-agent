# E4-DISJOINT-DIR budget-boundary supplement amendment

Date: 2026-08-21. Status: **REGISTERED BEFORE SUPPLEMENTAL MODEL CONTACT**. This amendment changes only the technical recovery path for the already registered E4-DISJOINT-DIR flight. The owner explicitly authorized the repair and one-cell supplement after the first attempt stopped at the client-side budget boundary.

## Failure and preserved evidence

Attempt 1 wrote 171 successful responses, then refused the final reservation before any network request. The registered total was 2,114.418 seconds; binary floating-point accumulation produced 2,114.418000000001 seconds. Offline structural validation found exactly one missing registered cell: `e4dir-10465-5-t009-d0-global`, duration 11.275999999999996 seconds. No partial response text has been read or scored.

## Authorized repair

`CallBudget` now treats totals within an absolute `1e-9` seconds of the registered cap as the same boundary, with zero relative tolerance. An accepted residue is clamped to the registered cap in the receipt. Any overrun beyond that tolerance remains fail-closed; call-count enforcement is unchanged.

The supplemental launcher must prove that the primary sink contains exactly 171 unique, successful, registered cells and that the declared request is the sole missing cell. It may execute only that request, with one call, one slot, zero retries, a 300-second timeout, and the original temperature 0, seed 0, max-tokens 512 decoding. It writes a separate response and receipt and refuses existing output paths. The assembler accepts only the exact 172-cell registered set and restores frozen request order. The original one-shot reader and scorer remain byte-unchanged.

No other model call, retry, sample change, arm change, agent loop, or confirmatory claim is authorized.

## Frozen amendment implementation

- Budget module SHA-256: `e3d4557f7923cb52f736f9a4d9c87cd8abf63300143dcefc9e54a8b1f101441c`.
- Budget regression tests SHA-256: `86e460fd541192b2e3d94b67e5096b85459d2ea865c6ac5d207676a09b798f61`.
- Supplemental launcher SHA-256: `20edd699eba778b22942a0b5ce39f9257b9a7064746de4e1137b4b5cba261e16`.
- Mechanical assembler SHA-256: `681efe6700d570b4aa25d569ee890a09bd54276c6c837c642a85bcba5cc1caf9`.
- Offline regression result: 17 passed in the registered WSL environment.
- Offline primary-sink validation: 171 seen; sole missing request `e4dir-10465-5-t009-d0-global`; 11.275999999999996 seconds.

The runtime binding, model and mmproj hashes, server binary and library hashes, server flags, prompts, score binding, decision table, and one-shot read implementation remain those frozen in the original preregistration and runtime-identity record.
