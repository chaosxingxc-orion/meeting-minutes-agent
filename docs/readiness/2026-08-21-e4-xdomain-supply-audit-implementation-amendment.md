# E4-XDOMAIN-SUPPLY-AUDIT implementation amendment

Date: 2026-08-21. Status: **FROZEN BEFORE AGGREGATE CARRY READ**. This amendment records the implementation and selected-input manifest built after the preregistration. It changes no corpus, proxy, threshold, or decision rule.

## Frozen implementation

- Core audit SHA-256: `7f5eea1b77bd7d7dcabc9ec7313d442628323a16f79610c4760c73698d859443`.
- Manifest builder SHA-256: `bd3a2b2bdf3d234a6672efdf612144dc693155fbc64f44bdb9b46198802352c8`.
- Sole-read CLI SHA-256: `67885d8a198ecb212d8cf344ce989c186c229ad1e8d43a978c90e65aab8f207a`.
- Synthetic test SHA-256: `fefc5b8cfaaafe9572eef8f2f386fc821c934fe8c010e0df0bbf66580d62f1a1`.

The WSL `~/.venvs/meeting` environment passed all E4 offline unit tests: **34 passed**. The four new tests cover conservative proxy extraction and segment deduplication, exclusive/shared/global-only carry classification, all ordered decisions, and a manifest that persists hashes rather than transcript text.

## Frozen input manifest

- File: `configs/probes/e4_xdomain_supply/2026-08-21-input-manifest.json`.
- File SHA-256: `74cc16b0f894e848f081aa679ea97e151e2aaa538192722b76bb280942e703f1`.
- Canonical content hash: `e9ea0ebd1dbed6f7a6f72d72450c158713327d52df36c522ae82d421f8c2dc09`.
- Roster: 102 train meetings: 61 Product/AMI `glossary-discovery` and 41 Academic/ICSI.

Every row records domain, meeting id, train-relative transcript path and SHA-256, plus joined audio byte size. No transcript text, lexical surface, query, answer, topic, validation row, or test row is persisted. The read rebuilds and exactly compares this manifest, checks the QMSum commit and clean checkout, checks the AMI role-registry hash, and refuses an existing output directory.

The next command is the sole permitted aggregate carry read. No candidate or threshold may be changed afterward.
