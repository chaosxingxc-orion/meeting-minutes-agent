# E4-XDOMAIN-SUPPLY-AUDIT-v2 attempt 1: invalid schema refusal

Date: 2026-08-21. Result: `INVALID-AUDIT`; no aggregate verdict or output directory was produced.

The frozen sole-read CLI stopped at discovery file `4484563.aligned.nlp` with `header drift`. A header-only follow-up found that 124 force-aligned files use the registered 11-column header, while this one file uses the upstream-documented 12-column variant with `wer_tags` between `tags` and `oldTs`. The file's SHA-256 remains the manifest-locked `8caabd863640ee550bca8e5e434df28117fbb51213f41d5657b540d2f751c5a9`.

No result directory, entity count, carry count, class count, surface, or reserve statistic was emitted. This failed attempt is retained rather than hidden. Any retry requires a committed pre-read recovery amendment and a new implementation hash.
