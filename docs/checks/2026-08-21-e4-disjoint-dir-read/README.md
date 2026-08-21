# E4-DISJOINT-DIR official read

Status: **COMPLETE; ONE-SHOT READ**.

- Decision: `EXPLORATORY-HARMFUL`; confirmatory: false.
- Sample: 52 dialogue clusters, 86 targets, 93 carry mentions, 172 calls.
- Speaker minus global: carry hit rate `+0.010753`, carry NE-WER `-0.006993`, overall WER `0.000000`, false-hint target rate `+0.034884`.
- The registered +2 percentage-point false-hint safety limit was breached; no replies were truncated.
- Cluster-bootstrap intervals for both carry contrasts cross zero, so the apparent carry improvement is not stable evidence.
- Complete-response SHA-256: `a15f4af4f8f2c379557c1b5176c23a2755b553a9f513cde6d72111adfcd06bf5`.
- Verdict SHA-256: `a897ea267adca9dc92caecd0ec3fbf02b7bf72556f98130d132e62939d65a32e`.
- Post-read offline regression: 1,494 passed, 25 skipped in the registered WSL environment.

This read does not change the E4-CF confirmatory verdict and does not release E5 or any agent loop.
