# Meeting Material Retrieval Signal Read

`E-MEETING-MATERIAL-RETRIEVAL-SIGNAL` completed its sole structural read on
2026-08-25 without reference, audio, or model contact. The verdict is
`RETRIEVAL-SIGNAL-INSUFFICIENT`.

## Result

| Metric | Gate | Observed | Pass |
|---|---:|---:|---|
| Eligible turns | at least 400 | 751 | yes |
| Dispatch coverage | at least 20% | 97.07% (729/751) | yes |
| Correct-material attribution | at least 70% | 61.87% (451/729) | no |
| Meetings at 60% precision | at least 2 | 1 | no |
| Median normalized margin | at least 0.05 | 0.1332 | yes |
| Provenance / reference contact | complete / zero | 49/49 / zero | yes |

Per-meeting attribution is heterogeneous: Jeronimo Martins 40.97%, Galp
77.12%, and TeamViewer 46.94%. The lexical Q-K-V construction therefore finds
a useful signal for Galp but is below chance on two of three meetings.

## Interpretation

The SAEA mechanism is not reproduced by merely adopting Q-K-V field names.
Its strong result used a richer, train-built key space, ranking, and a
conservative retain/dispatch blend. Here, eight balanced official-material
snippets per meeting provide broad lexical overlap, but generic topic overlap
makes positive retrieval score almost universal. Positive score is therefore
not a safe dispatch predicate.

This result rejects the frozen BM25 word/long-token-trigram key construction.
It does not reject semantic text embeddings, a richer meeting-material key
space, or retain/dispatch itself. A successor must use a separately frozen
retriever and keep the same equal-width wrong-meeting control. It must not tune
on this read or reopen the earlier reference result.

The complete result is [verdict.json](verdict.json).
