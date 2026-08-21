# E4-DISJOINT-POWER preflight record

Date: 2026-08-21. Status: **PREFLIGHT COMPLETE; DATA BLOCKER LATER RESOLVED AND FORMAL CENSUS RUN**.

The E: volume was restored later on 2026-08-21. The registered census then ran once and returned `INSUFFICIENT-CARRY-SUPPLY`; see `docs/readiness/2026-08-21-e4-disjoint-power-verdict.md`. The blocker description below is retained as the execution history.

## Frozen artifacts

- Design: `docs/plans/2026-08-21-e4-disjoint-power-audit.md`, SHA-256 `581c126063b08e31dd9076ec82ec43ee992784cb3aac741a71397ce8704184b9`.
- Module: `src/meeting_minutes_agent/probes/e4_disjoint_power.py`, SHA-256 `6ed0abfb4426d532bd587bb22aa29c160d0d7590e6de47878d278fb60cd468b2`.
- CLI: `scripts/e4_disjoint_power.py`, SHA-256 `e3133e0ef48d3ef54f57664c28d06e39159e8021cd24bd89d87196b64e643cec`.
- Tests: `tests/unit/probes/test_e4_disjoint_power.py`, SHA-256 `1dadf5e4c2def3f45acd9e0864effbcfe145a6bea96a2af8414217c3eebb1a66`.
- Offline verification: 8 tests passed across the new module and `e4_power` regression suite in the existing WSL `xiazi-gemma4` environment.

The exclusion gate was checked without corpus access: the discovery manifest contains 12 IDs, the E4-CF roster contains 287, their overlap is zero, and their union is exactly 299. Their SHA-256 values are `8adce09605db05158006bc7fd82bc77acd826e4ffd1591a8ef8eee91b045ff9f` and `0019748e174559714bfd772daf94891c467f8a20442b9e854bbc59b426081ef6`.

## Analytical preflight

With two-sided alpha 0.05, power 0.80, discordance 0.15, design effect 1.5, and usable-state fraction 0.85, the frozen scenarios require:

| MDE | Prevalence | Analyzable predicate carry | Raw carry mass |
|---:|---:|---:|---:|
| 3 pp | 40% | 1,963 | 5,774 |
| 3 pp | 50% | 1,963 | 4,619 |
| 3 pp | 54.01% | 1,963 | 4,277 |
| 4 pp | 40% | 1,104 | 3,248 |
| 5 pp | 40% | 707 | 2,080 |

The prior same-source frozen summaries imply, but do not newly census, 4,974 remaining dialogues, 6,423 carry mentions, and 6,064 target turns after removing the E4-CF roster. Thus the primary 3 pp/40% scenario would consume about 89.9% of remaining carry supply. This arithmetic is a feasibility warning, not a formal roster or budget result.

## Current blocker and next command

The registered source lived at `/mnt/e/datasets/contextasr-bench/ContextASR-Dialogue_English.jsonl`, expected SHA-256 `4bbf64387d1c581df2c7ab5db9af4461e1112ee489377b67084c9b40cb6d45e8`. The current host exposes only C: and D:; `/mnt/e` is empty. The formal output directory was therefore not created.

After the same data volume is restored, run the frozen CLI once. It fails closed on source hash, exclusion count, and pre-existing output directory. A successful result remains scenario-only because unseen predicate prevalence cannot be measured before new Pass-0 model contact.

```bash
python scripts/e4_disjoint_power.py \
  --jsonl /mnt/e/datasets/contextasr-bench/ContextASR-Dialogue_English.jsonl \
  --discovery-manifest configs/probes/contextasr/2026-08-20-e3-state-audit-12-manifest.json \
  --confirmatory-roster configs/probes/contextasr/2026-08-20-e4-confirmatory-candidate-roster.json \
  --output-dir docs/checks/2026-08-21-e4-disjoint-power
```
