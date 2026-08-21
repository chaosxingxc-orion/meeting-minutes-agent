# E4-DISJOINT-POWER evidence archive

- Machine decision: `INSUFFICIENT-CARRY-SUPPLY`.
- Formal read: one zero-model corpus census after registration; no model calls.
- Source: ContextASR English JSONL, SHA-256 `4bbf64387d1c581df2c7ab5db9af4461e1112ee489377b67084c9b40cb6d45e8`.
- Exclusions: 299 previously seen dialogues, leaving 4,974 dialogues.
- Remaining aggregate supply: 6,423 carry mentions and 6,064 target turns.
- Eligible pool (`carry_mentions >= 2`): 1,634 dialogues and 4,782 carry mentions.
- Primary requirement (3 pp MDE, 40% prevalence, 85% usable state): 5,774 raw carry mentions; shortfall 992.

The 3 pp scenario becomes arithmetically feasible only under unverified prevalence assumptions: 50% requires 1,577 dialogues, 31,749 deduplicated calls, and 101.55 repeated audio-hours; the E4-CF descriptive 54.01% requires 1,457 dialogues, 29,536 calls, and 94.51 hours. These are planning scenarios, not evidence that the unseen predicate prevalence is that high.

## Frozen hashes

- Registration: `f66079f6758eddbf66be6f2922dc516569b5c50b4cbe2d65c293e24aa29e376a`.
- `verdict.json`: `bdc23750fd43ece3ff1a37d734904eba6aa239ff00969bcbe7a4b4ff5644d36f`.
- `report.txt`: `5d09db8b7fc0b4d9c828bd5f3b4679573029f255be00a5a929cfefd5c7e561e3`.
- `primary-candidate-roster.json`: `9fa552432c0944d1eb9083037568c899bbf136fad9b375e2e259e611ba1b821d` (empty by design because the primary gate failed).

No raw transcript, entity text, or model output is stored in this directory.

