# E4-XDOMAIN-SUPPLY-AUDIT-v3 implementation amendment

Date: 2026-08-22. Status: **FROZEN BEFORE THE SOLE RESERVE READ**. This amendment changes no class, sample, carry rule, threshold, or decision rule.

## Frozen implementation

- Core audit SHA-256: `dde211891dbcb2874f0cd11f9fdf9f9fc8abeb3d96cb51377fdaf2e62a72c301`.
- Reserve-manifest builder SHA-256: `e83309fd60cdb39212feae318e65c7ce134919ff3f15edb8da4aac6e60bf2ad2`.
- Sole-read CLI SHA-256: `0b3dff56a33fd755e582a82fa4df9c9edf23c2c84e2d863162d483e1edee5a99`.
- Synthetic test SHA-256: `400fc6074b1c7d2cf868f05a2a426f82830fc1113db3f33472cc6ef2d6ea2ea4`.

The registered WSL `~/.venvs/meeting` environment passed the v3 and v2 offline unit tests: **10 passed**. Coverage includes narrow-class filtering, same-slice deduplication, exclusive/shared/global-only carry, frozen meeting-level gates, parent-manifest refusal, reserve byte closure without discovery bytes, and explicit rejection of a discovery-contaminated row.

## Frozen reserve manifest

- File: `configs/probes/e4_xdomain_supply_v3/2026-08-22-reserve-manifest.json`.
- File SHA-256: `d2ca079344ffe1ac11f7159efc7c1eeb72f298c3fa45cf013a5c3660ecfc5be8`.
- Canonical content hash: `b7ccad172083e192830285d510fdd0da6622b742c8d6072bf189719cbc831ea5`.
- Roster: exactly 45 parent-manifest reserve files; allowed classes are exactly `ABBREVIATION` and `ALPHANUMERIC`.

The builder validates the frozen 125-row parent manifest but opens and hashes only its 45 reserve paths. Each v3 row contains only file ID, relative path, byte size, and SHA-256; it has no split field, transcript text, surface, entity ID, or per-meeting statistic. The reader reconstructs this manifest, refuses any row-schema change, parses exactly those 45 files, and refuses an existing output directory.

The next command is the sole permitted reserve aggregate read. No schema recovery or second read is authorized under v3.
