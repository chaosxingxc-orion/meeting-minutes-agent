# EARNINGS22-RUNTIME-DOMINANT-GATE read

Verdict: **`RUNTIME-DOMINANT-GATE-UNSAFE`**.

This was the registered one-shot, zero-model read over the frozen Earnings-22
Sortformer RTTMs. The primary universe contains 76 meetings with adequate aligned
reference coverage and more than four reference speakers.

| Measure | Result | Gate |
|---|---:|---:|
| Runtime-admitted meetings | 57/76 | at least 15 |
| Gold-dominant precision | 38.60% | at least 70% |
| Gold-dominant recall | 73.33% | at least 60% |
| Pooled Top-1 attribution error | 12.36% | at most 20% |
| Pooled Top-2 attribution error | 27.79% | at most 25% |
| Unsafe admitted meetings | 29/57 (50.88%) | at most 10% |

The rule has supply and recall, but not selectivity or routing safety. All 76 primary
meetings passed the occupancy-only diagnostic; temporal stability reduced this to 57,
yet most admitted meetings were not gold-dominant and half had per-meeting Top-2 error
above 40%. Four-speaker compression can therefore create stable-looking dominant
clusters even when those clusters do not represent the two true dominant speakers.

This result rejects this runtime gate. It does not reverse the earlier conditional
finding that routing is usable when dominance is known from reference data. No Omni
call occurred, and no threshold was changed after reading the result.

Audit-trail limitation: the preregistration and verdict are archived in the same Git
commit. Execution order was preregistration and tests first, then the one-shot read,
but that ordering is not independently established by a commit boundary.

Machine-readable verdict SHA-256:
`b201276d7bd652fc3279b113025996d67088ba75467b79afca504d62b09ed62b`.
