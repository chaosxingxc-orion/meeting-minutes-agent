# E4-DISJOINT-DIR exploratory verdict

Date: 2026-08-21. Status: **READ ONCE; EXPLORATORY-HARMFUL**.

The registered two-arm direction pilot completed 172 cells over 86 targets from 52 dialogue clusters. Attempt 1 stopped after 171 responses because a binary floating-point residue crossed the exact client budget cap before the final network request. The registered amendment authorized one mechanically identified missing cell; it completed with one successful attempt and zero retries. The assembled response set exactly matches the frozen request roster.

`D1-speaker` versus equal-width `D0-global` improved carry exact-hit rate by 0.010753 and reduced carry NE-WER by 0.006993. Overall WER was identical at 0.034694. However, false-hint target rate rose from 0.081395 to 0.116279, a 0.034884 increase that breaches the preregistered +0.02 safety limit. The decision is therefore `EXPLORATORY-HARMFUL`. No output was truncated.

The dialogue-cluster bootstrap intervals cross zero for carry hit rate (95%: -0.052631 to 0.074468) and carry NE-WER (95%: -0.056000 to 0.043478). The observed carry direction is not stable evidence and cannot support a confirmatory or practical-effect claim.

The result rejects direct deployment of the tested equal-width speaker inventory. It does not prove that every speaker-conditioned policy is harmful: a future experiment would need a preregistered runtime-visible rejection or confidence gate that directly targets false hints, an independent sample, and a new safety analysis. It does not authorize the full 31,749-call flight, E5, or an agent loop.

Evidence: flight `docs/checks/2026-08-21-e4-disjoint-dir-flight/`; official read `docs/checks/2026-08-21-e4-disjoint-dir-read/`; complete-response SHA-256 `a15f4af4f8f2c379557c1b5176c23a2755b553a9f513cde6d72111adfcd06bf5`; verdict SHA-256 `a897ea267adca9dc92caecd0ec3fbf02b7bf72556f98130d132e62939d65a32e`.

Post-read offline regression: 1,494 passed and 25 skipped in 140.26 seconds in the registered WSL environment.
