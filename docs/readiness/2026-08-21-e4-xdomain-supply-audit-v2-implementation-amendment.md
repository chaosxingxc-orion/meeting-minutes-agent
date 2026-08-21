# E4-XDOMAIN-SUPPLY-AUDIT-v2 implementation amendment

Date: 2026-08-21. Status: **FROZEN BEFORE DISCOVERY AGGREGATE READ**. This amendment changes no split, proxy, threshold, reserve rule, or decision rule.

## Frozen implementation

- Core audit SHA-256: `bf49c9b815bf5669eea7cab8798d28b911d867e33de9282768de60d5d32838d2`.
- Manifest builder SHA-256: `cb0e6a3c56e3d4ef0b23a34b0345872931d7b63d466c191e2fc4833264f55509`.
- Sole-read CLI SHA-256: `1092460ef2922063baef289d9c249832917458387520cf1f1ea8499540d1c1fa`.
- Synthetic test SHA-256: `7ca8bd6b015321c6e4f49fb79db307ab60f3587fb9430dd675598e2c253288ed`.

The registered WSL `~/.venvs/meeting` environment passed the new v2 tests together with the existing v1 supply tests: **9 passed**. Coverage includes deterministic 80/45 splitting, multi-token entity reconstruction, fail-closed schema and non-contiguous-ID handling, same-slice deduplication, excluded-class handling, unaligned-mention exclusion, and exclusive/shared/global-only carry classification.

## Frozen input manifest

- File: `configs/probes/e4_xdomain_supply_v2/2026-08-21-input-manifest.json`.
- File SHA-256: `96d009584615afd1c1c487a2207f0fcb00da667f579e90f8e7ceabb69c8143ee`.
- Canonical content hash: `67f0fc955ff9057ee5819ee3f05957ad1a04d2603564ba75366d4d319e2bd313`.
- Roster: exactly 125 force-aligned references; 80 discovery and 45 reserve.

Every manifest row contains only file ID, split, relative path, byte size, and SHA-256. Hashing the reserve locks identity but does not parse its transcript content. The read reconstructs and exactly compares the manifest, refuses any MP3 under the audit root, parses only discovery rows, and refuses an existing output directory.

The next command is the sole permitted discovery aggregate read. No class, split, candidate rule, or threshold may change afterward.
