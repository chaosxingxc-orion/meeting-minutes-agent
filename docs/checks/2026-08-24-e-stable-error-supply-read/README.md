# E-STABLE-ERROR-SUPPLY read

Registered decision: **`STABLE-ERROR-SUPPLY-PRESENT-ANCHOR-LIMITED`**.

| Measure | Result | Registered gate |
|---|---:|---:|
| Complete Pass-0 replies | 1,429 | 1,429 |
| Narrow target occurrences | 406 | descriptive |
| `(meeting, predicted speaker, surface)` groups | 162 | descriptive |
| Stable-correct groups | 14 | descriptive |
| Stable-wrong groups | **13** | at least 10 |
| Meetings with stable-wrong | **4/4** | at least 3 |
| Ticker-anchored stable-wrong groups | **0** | at least 2 |
| Meetings with anchored stable-wrong | **0** | at least 2 |

The 13 stable-wrong groups cover 70 target occurrences; their median majority purity is
100%, and none has deletion as its majority form. Stable exact-form errors therefore do
exist across the full pilot. The registered legal anchor, however, supplies no correction,
so Pass1 and the agent loop remain blocked.

## Post-hoc normalization diagnostic

After inspecting the strict forms, a separator-removal diagnostic found that 9/13
(69.23%) stable-wrong groups are merely spacing/punctuation variants of the reference,
mostly split versus joined abbreviations. This rule was not preregistered and cannot
replace the verdict. It materially limits interpretation: at most four groups remain
non-separator candidates, below the registered supply threshold. Exact reference style
is not the same as professional-term semantic correctness.

Machine artifacts: `verdict.json` SHA-256
`2fb982b101fa0784b363640dec6f54e83728cbd9948c517931514554841a134a`;
`normalization-diagnostic.json` SHA-256
`21f2c8c217d77a02f9fb1723e69d6f0a7994ee71f0cd092644ade0b6ec7fe7e3`.
