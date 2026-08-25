# E-MATERIAL-RUNTIME-GATE-CI confirmation read

The sole preregistered confirmation read passed all four frozen gates at the development-
selected threshold **0.01**. It processed 850 eligible turns using 874 embeddings and 56
batched embedding calls; no threshold was retuned and no second confirmation read occurred.

The selector dispatched 636/850 turns (74.82% coverage). Correct-meeting attribution won
484/636 dispatched comparisons (76.10% precision), and the median correct-minus-deranged
cosine margin was 0.06154. Two of three meetings exceeded the frozen 60% per-meeting
precision floor; the third reached 58.64%, showing material between-meeting variation even
though the preregistered distributed gate passed.

The machine verdict is `CONSTRUCTION_ISOLATED_SIGNAL_PRESENT`. This establishes only an
exploratory semantic routing signal under construction isolation. It is not independent
confirmation and does not show WER gain, safe correction, or deployability. A separate
preregistration and authorization are required before any Omni retain/correct/deranged flight.

- [Execution amendment](../../readiness/2026-08-25-material-runtime-gate-ci-semantic-execution-amendment.md)
- [Development read](../2026-08-25-material-runtime-gate-ci-development-read/README.md)
- [Machine result](confirmation.json)

Machine-result SHA-256: `945fdb71d870377183d1611c1148e18cba631385480413441e8e520faf4d394f`.
