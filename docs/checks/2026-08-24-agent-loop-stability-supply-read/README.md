# E-LOOP-STABILITY-SUPPLY read

Registered decision: **`LOOP-STABILITY-SUPPLY-READY`**.

| Measure | Result | Registered gate |
|---|---:|---:|
| Meetings with at least three 5-minute windows | **4/4** | at least 3 |
| Existing Pass-0 turns read | **1,429** | 1,429 |
| Turns with non-empty prior keyword memory | **1,424** | at least 100 |
| Global cross-window carry turns | **727** | descriptive |
| Same-speaker cross-window carry turns | **554** | at least 20 |

The audit uses only chronologically earlier Pass-0 output. After a first diagnostic exposed
function words in the keyword list, the pre-model implementation was corrected to remove
English stopwords and fillers while retaining uppercase abbreviations and alphanumeric
forms. The final lists contain content-bearing items such as `sales`, `enterprise`,
`billings`, `quarter`, `gas`, `revenue`, and `SK`.

This is an experiment-admission result, not an ASR result. Recurrence does not establish
correctness, and no summary, keyword, language constraint, or agent policy has yet been
sent to Omni. The next model experiment must score stability separately from utility and
must include a provenance-matched deranged-memory control.

Frozen config SHA-256: `a6500220063c076fb0c7d1162cbb84358ca3c9568879c5627f83ee3a83e5cf55`.
Machine verdict SHA-256: `dc31782fd2f0a1c21a0296959254564e4c409ed3fbdf84372b833d7e7f31c7d5`.
