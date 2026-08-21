# E4-SAFETY-GATE-AUDIT verdict

Date: 2026-08-21. Status: **READ ONCE; NO-SAFE-GATE**.

The frozen zero-model audit evaluated four runtime-only policies over all 86 E4-DISJOINT-DIR targets. Each policy selected the already frozen speaker output when its gate accepted and otherwise fell back to the frozen global output; no target was removed from a denominator.

No candidate passed the combined coverage, utility, and safety gate. Requiring every term to have repeated evidence accepted no target. The two recency-based gates accepted only 11 and 10 targets from 10 dialogues, produced zero carry change, and each added one false-hint target over the global fallback policy. Limiting inventory width to two was the only candidate to pass coverage (27 targets, 24 dialogues) and safety (false-hint delta zero; WER delta +0.000816), but it also removed the entire observed carry benefit: both carry hit-rate and carry NE-WER deltas were zero.

The decision is `NO-SAFE-GATE`, not `SCENARIO-DEPENDENT`, because no candidate reached the overall utility-plus-safety gate before internal fold and width transport checks could matter. The result supports the owner's scalability concern: these simple evidence/recency/width thresholds do not yield a useful policy even within the current surface. Cross-domain scalability remains unidentifiable because all targets are ContextASR movie dialogue.

This does not prove that every possible learned or tool-assisted rejection policy must fail. It does reject further tuning of these four hand-built gates on the same responses. Any continuation requires a genuinely independent surface or a materially different runtime signal, a new preregistration, and new authorization. The parent `EXPLORATORY-HARMFUL` verdict, full-flight prohibition, E5 prohibition, and agent-loop prohibition remain unchanged.

Evidence: `docs/checks/2026-08-21-e4-safety-gate-audit-read/`; verdict SHA-256 `7beb811c6944421e1592537e9ec1fc8bc808fcd073365ad9f8aed6c0db2a7d11`; report SHA-256 `2072438c76ef4a410227a3062a4deb82b6e7b696046ecab65f17fe448dec1b03`.

Post-read offline regression: 1,498 passed and 25 skipped in 129.87 seconds in the registered WSL environment.
