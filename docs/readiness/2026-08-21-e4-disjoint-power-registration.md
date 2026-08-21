# E4-DISJOINT-POWER formal registration

Date: 2026-08-21. Status: **REGISTERED BEFORE CORPUS READ**. This is a zero-model score-side roster and power census; it authorizes no model contact.

## Frozen question and boundary

The census asks whether untouched ContextASR English has enough natural same-speaker carry supply to plan an independent confirmation of the post-hoc `speaker_wrong_disjoint` policy. It does not test that policy. Unseen predicate prevalence is not identifiable without new Pass-0 hypotheses, so prevalence is a scenario assumption rather than a new-data estimate. Reference text and entity labels may be read only by this offline planner and must never enter runtime prompts.

## Frozen inputs

- JSONL: `/mnt/e/datasets/contextasr-bench/ContextASR-Dialogue_English.jsonl`, SHA-256 `4bbf64387d1c581df2c7ab5db9af4461e1112ee489377b67084c9b40cb6d45e8`.
- Discovery exclusion: `configs/probes/contextasr/2026-08-20-e3-state-audit-12-manifest.json`, SHA-256 `8adce09605db05158006bc7fd82bc77acd826e4ffd1591a8ef8eee91b045ff9f`.
- Confirmatory exclusion: `configs/probes/contextasr/2026-08-20-e4-confirmatory-candidate-roster.json`, SHA-256 `0019748e174559714bfd772daf94891c467f8a20442b9e854bbc59b426081ef6`.
- Exclusion gate: 12 discovery plus 287 confirmatory IDs, zero overlap, exactly 299 unique IDs.

## Frozen implementation

- Design SHA-256: `581c126063b08e31dd9076ec82ec43ee992784cb3aac741a71397ce8704184b9`.
- Module SHA-256: `6ed0abfb4426d532bd587bb22aa29c160d0d7590e6de47878d278fb60cd468b2`.
- CLI SHA-256: `e3133e0ef48d3ef54f57664c28d06e39159e8021cd24bd89d87196b64e643cec`.
- Test SHA-256: `1dadf5e4c2def3f45acd9e0864effbcfe145a6bea96a2af8414217c3eebb1a66`.
- Verification before registration: 8 tests passed in the existing WSL `xiazi-gemma4` environment.

## Frozen scenarios and budget accounting

All scenarios use two-sided alpha 0.05, power 0.80, paired discordance 0.15, dialogue design effect 1.5, and usable-state fraction 0.85. MDE is crossed over `0.03`, `0.04`, and `0.05`; assumed predicate prevalence is crossed over `0.40`, `0.50`, and the descriptive E4-CF value `418/774`.

The primary planning scenario is MDE 0.03 and prevalence 0.40. The policy arm is a deterministic alias: reuse D1-speaker when the runtime predicate is true and D0-global otherwise. Deduplicated cost therefore runs D0 and D1 on all targets plus D3-wrong on expected predicate-positive targets; a naive four-arm upper bound is also reported.

If the remaining corpus cannot supply the primary scenario, the machine decision is `INSUFFICIENT-CARRY-SUPPLY`. Otherwise it is `SCENARIO-POWER-READY-PREVALENCE-UNVERIFIED`. Neither decision authorizes Pass-0 or second-pass model calls.

## One-shot command and outputs

The output directory must not exist before execution. The CLI fails closed on the JSONL hash, exclusion gate, and overwrite attempt.

```bash
python scripts/e4_disjoint_power.py \
  --jsonl /mnt/e/datasets/contextasr-bench/ContextASR-Dialogue_English.jsonl \
  --discovery-manifest configs/probes/contextasr/2026-08-20-e3-state-audit-12-manifest.json \
  --confirmatory-roster configs/probes/contextasr/2026-08-20-e4-confirmatory-candidate-roster.json \
  --output-dir docs/checks/2026-08-21-e4-disjoint-power
```

Only `verdict.json`, `report.txt`, and `primary-candidate-roster.json` may be created. After the one-shot run, only hash verification, the prebuilt read, documentation, and Wiki synchronization are allowed.
