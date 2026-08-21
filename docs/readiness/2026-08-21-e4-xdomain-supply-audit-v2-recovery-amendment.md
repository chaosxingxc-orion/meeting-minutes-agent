# E4-XDOMAIN-SUPPLY-AUDIT-v2 recovery amendment

Date: 2026-08-21. Status: **REGISTERED AFTER FAIL-CLOSED ATTEMPT; BEFORE REPLACEMENT AGGREGATE READ**.

Attempt 1 stopped before producing any aggregate output because one discovery file has the 12-column header documented by the upstream README, including `wer_tags`; the other 124 files have the 11-column header observed during initial schema inspection. A header-only census found no third variant. The failed attempt and locked file hash are recorded in `docs/checks/2026-08-21-e4-xdomain-supply-audit-v2-attempt-1-invalid/README.md`.

The replacement parser accepts exactly those two headers and continues to use only the `tags` column; `wer_tags` is ignored. All other headers, row-width mismatches, malformed tags, split changes, hashes, and source-identity changes still fail closed. The corpus, 80/45 split, discovery roster, entity proxy, pseudo-slices, thresholds, reserve prohibition, and decision rule remain unchanged.

Because attempt 1 emitted no aggregate information, one replacement discovery read is authorized after its new implementation hash and offline test result are committed. Its output directory must be new and absent. No further schema recovery is authorized under v2.

Frozen replacement core SHA-256: `69b2597a8d45523a547b6ea81e0254eb8cbb78d475b0c784a61dfaf569caee9e`. Frozen replacement test SHA-256: `25399711b7276dc8dcc3aea11e72b2d2409bbd968d9d5587e0b8bc7065bcf05a`. The manifest builder, sole-read CLI, and input manifest are unchanged from the implementation amendment. The WSL `~/.venvs/meeting` environment passed the replacement v2 tests together with the existing v1 supply tests: **10 passed**.
