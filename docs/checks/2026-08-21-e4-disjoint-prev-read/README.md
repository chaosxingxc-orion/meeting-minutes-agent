# E4-DISJOINT-PREV staged read evidence

| Stage | Usable targets | Positive | Prevalence | Cluster bootstrap 80% | Usable carry | Decision |
|---:|---:|---:|---:|---:|---:|---|
| 20 | 54/54 | 34 | 62.96% | 53.45%–72.88% | 100% | `CONTINUE` |
| 40 | 104/104 | 57 | 54.81% | 47.22%–62.63% | 100% | `CONTINUE` |
| 60 | 163/164 | 86 | 52.76% | 46.71%–59.01% | 99.43% | `PREVALENCE-SCREEN-PASS` |

The break-even prevalence is 48.2938%. The final90% cluster interval is44.91%–60.78%. This screen supports using approximately50% as a planning scenario for the current pinned inference stack, but does not measure policy benefit.

The first read attempt failed before creating an output directory because the selected WSL test environment lacked the project-pinned `contractions==0.1.73` dependency. The fixed optional dependencies were installed and the same frozen CLI was rerun; no code or threshold changed.

## Verdict hashes

- Stage20 verdict: `2dcf9ec6848962faaf8efac5796fda80fa9e10f86434a6d9eb6a123529d315a4`; report: `6f7a1f1af05736b3782c629ba812881cac522db7f9335436101b4c52c47be51a`.
- Stage40 verdict: `3fcd32bba838162b627929231578f9252459a7803a8557b2b4dbc5fa9bbaabd8`; report: `4dcd7d3742d5b738cf256c5e38b64fe40878e8d8002ea2559a2a06435a2d5e08`.
- Stage60 verdict: `02a27bbc25a4a35fea21f92b7e0012d706511caf28d7901bf9867a245c573e94`; report: `3ba0a78b46029cd807bafb0eb61a01edc41cd225aa35702d2dd66214dc11b540`.

