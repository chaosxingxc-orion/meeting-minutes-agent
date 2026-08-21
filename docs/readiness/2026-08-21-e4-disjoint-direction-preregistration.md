# E4-DISJOINT-DIR exploratory direction pilot — preregistration

Date: 2026-08-21. Status: **REGISTERED BEFORE SECOND-PASS MODEL CONTACT**. The owner authorized continuing with the previously proposed approximately 172-call direction pilot after PR #1 merged. This registration does not authorize the full E4-DISJOINT confirmatory flight or an agent loop.

## Scope and frozen sample

The experiment reuses the registered E4-DISJOINT-PREV roster and its complete 795-call Pass-0 outputs. A target is selected only when score-side annotations establish a natural same-speaker carry opportunity, all three legal Pass-0-derived inventories have nonzero equal width, and the runtime-visible normalized speaker and wrong-speaker inventories are disjoint. Selection never observes Pass-0 correctness, a baseline error, confidence, or any second-pass output.

The frozen bindings contain 86 targets from 52 dialogue clusters and 93 carry mentions. State widths range from 1 to 8. The runtime binding contains no reference text, entity list, or carry label. The score binding is unavailable to the launcher.

- Runtime binding file SHA-256: `72d62ad06cccd43f699285a6c50f87697ba02c47c248215e58cead39ea71e28d`; content hash: `2cf931f7dec339d8b46f0491fe97469603ba3c76c54190057fe14e9cc683bb65`.
- Score binding file SHA-256: `1f2e59153e20dd243121f0f1d3e9534292313d8f7fa1cb121e0db6c2744b4330`; content hash: `1373362fed2aa2916aec1677706fba63d91da49026e6c0777084cb061094d5ec`.
- Parent Pass-0 response SHA-256 values: stage20 `2786a0c5edde176f7fc85f5dd846457b2d69333fa47aa149f3ff88f3871e4197`; stage40 `52f927700dd913f6da31fba3c24bff712cb90046b3d68bf7414ae25022cb4950`; stage60 `90e6beab340cef2d46adeb9c7d1476ad6f518aea49c7b2648d5f41d0cda9dc84`.

## Arms, ordering, and budget

- `D0-global`: equal-width global inventory.
- `D1-speaker`: equal-width current-speaker inventory.

Both arms use byte-identical target audio and the frozen E4 confirmatory renderer. Arm order alternates by target index. Decode parameters are temperature 0, seed 0, and max tokens 512. Transport uses one slot, a 300-second timeout, and zero retries. The exact ceiling is 172 calls and 2,114.418 repeated audio-seconds. The launcher requires these exact ceilings and refuses existing output paths.

Any failed request aborts the flight. A partial sink is structural evidence only and must not be scored or resumed under this registration. A new flight would require a new owner decision and receipt.

## Outcomes and frozen decisions

The primary descriptive contrast is `D1-speaker - D0-global` carry exact-hit rate. Secondary contrasts are carry NE-WER and overall WER. Safety uses false-hint target rate, overall WER, truncation, call count, and audio seconds. Dialogue-clustered 20,000-replicate bootstrap intervals at 80% and 95% are descriptive and cannot produce a confirmatory claim.

Decision order:

1. Any capped reply in either arm: `EXPLORATORY-INVALID-TRUNCATED`.
2. Speaker minus global overall WER above +0.01, or false-hint target rate above +0.02: `EXPLORATORY-HARMFUL`.
3. Carry hit-rate delta above zero, carry NE-WER delta below zero, and both safety limits pass: `EXPLORATORY-SPEAKER-DIRECTION`.
4. Carry hit-rate delta at most zero and carry NE-WER delta at least zero: `EXPLORATORY-NO-GAIN`.
5. Otherwise: `EXPLORATORY-MIXED`.

No decision label confirms a practical effect. A positive direction permits planning a new independent surface only.

## Frozen implementation and inference stack

- Binding builder: `59e12a671cc6ec5446275a32d7ef1079c97873b6ef6d109eeb77baf103f3e488`.
- Request module: `9a020227d29de2b14bfebe4e0c9f525cc287f4c2f7429222099c6be7bcf3c444`.
- Launcher: `323fee32831e8880e24ba8a34bf9005b35fbe66fdcc1f31d39dd038dd5f5333a`.
- Scorer: `206b506031e2ab4a9010948c7aed5e97732360f031923c4e72eedfbbbb38512b`.
- One-shot read CLI: `c4f4c0b7142b30048418809c6507b0c821e15f64d34915cab6f72e3c6c05764b`.
- Server launcher: `5da1ed65ce0eb27dad4ac85dfdfb68aa09f63348872b50aad4e9cb39b5272a33`.
- Tests: `ba59dd54fce1ddd328decdbae58e83c6bda5eada830adba11208437429d9b02c` and `8c866703af02e4ef679adf7f34a72a806baaf9742213d77dccab1a774e89a31a`; 5/5 passed before registration.

Model SHA-256 is `d9e2876556e7873e02c0359f832432ee2d67ab7dd0cee3efe0f77fd7a1f4dd85`; mmproj SHA-256 is `1104376db833f1e89c84834144ac3863340c2cd1ddaeddb39cb0247fb5c20c8d`. Server SHA-256 is `ad69437593e9f458b22eb9ffae2aaf574d36e8ccdecf6b8d44b6fa7b58d74fa9`. The dynamic-library hashes match the E4-DISJOINT-PREV server amendment. Server flags are context 16384, one parallel slot, flash attention on, all GPU layers, and q8_0 K/V cache.

The read output directory must not exist before the completed flight. The read is performed once and archived with input hashes, report, verdict, and Wiki update.
