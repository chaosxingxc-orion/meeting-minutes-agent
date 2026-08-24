# E-LOOP-STABILITY read

Registered verdict: **`LOOP-STABILITY-NOT-REACHED`**.

| Gate | Result | Pass? |
|---|---:|:---:|
| Complete responses | 8,574/8,574 | yes |
| Context hash replay / budget | 8,574/8,574 | yes |
| L3 consistency vs bare | 86.42% vs 75.00%; +11.42 points, 4/4 meetings | yes |
| L3 better than deranged | 2/4 meetings | **no** |
| Round2/L3 convergence ratio | 1.040 | **no**, required at most 0.80 |
| L3 WER vs bare | 41.30% vs 22.02%; +19.28 points | **no** |
| L3 worst-speaker WER non-inferiority | 15.625 vs 10.958 | **no** |
| L3 unsupported activation | 3.13% | **no**, required at most 2% |
| L3 language-drift outputs vs bare | 106 vs 126 | yes |

The context manager strongly increased exact-form consistency, but this was not a safe
fixed point. L3 failed to separate from provenance-matched deranged memory in the required
number of meetings, and the second L3 pass changed slightly more than the first
(`0.2479` versus `0.2383` normalized edit distance). GRPO, GEPA, EM, and multimodal
knowledge-injection search remain blocked.

## Post-hoc mechanism diagnostic

The hypothesis/reference word ratio rose from 1.039 for bare to 1.568 for recent-tail;
L3 was 1.175. Outputs with at least 80% recent-tail echo rose from 1.10% for bare to
16.17% for recent-tail, 14.02% for global, and 9.05% for L3. This supports context echo
as a failure mechanism. It does not replace the registered verdict.

Machine verdict SHA-256:
`e34d5a3f5e981973c7a68fe77a8db4aad56070235834f19167782dcbb096cdc3`.
Post-hoc diagnostic SHA-256:
`8aa7bea605b821ee32d7cac4cdbfc89da9ef53c4417f925d0c22475a24872d6e`.
