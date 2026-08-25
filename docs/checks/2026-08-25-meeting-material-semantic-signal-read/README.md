# Meeting Material Semantic Signal Read

`E-MEETING-MATERIAL-SEMANTIC-SIGNAL` completed its sole encode-only structural
read on 2026-08-25. The verdict is `SEMANTIC-RETRIEVAL-SIGNAL-PRESENT`; every
preregistered gate passed. No reference, audio, or Omni model was accessed.

## Result

| Metric | Gate | Observed | Pass |
|---|---:|---:|---|
| Eligible turns | exactly 751 | 751 | yes |
| Dispatch coverage | at least 20% | 52.33% (393/751) | yes |
| Correct-material attribution | at least 70% | 77.86% (306/393) | yes |
| Meetings at 60% precision | at least 2 | 3 | yes |
| Median correct-minus-deranged cosine | at least 0.01 | 0.0559 | yes |
| Precision gain over lexical | at least 8 pp | +15.997 pp | yes |

Per-meeting attribution precision is 69.05% for Jeronimo Martins, 84.33% for
Galp, and 70.65% for TeamViewer. The tool produced 775 embeddings in 49 batched
calls over 17.41 seconds; vectors were 1024-dimensional.

## Interpretation

Replacing lexical BM25 with the umbrella-pinned encode-only Qwen3 text
embedding changes the result from scene-dependent to distributed signal under
the same Q, balanced K/V inventory, and deranged rotation. This supports the
transfer of semantic K ranking and conservative retain/dispatch structure.

The read does not establish term correctness, WER gain, or safe deployment.
Its confidence gap is measured across correct and deranged experimental pools;
a production gate must be rebuilt without depending on a deliberately wrong
meeting. The current three meetings have also consumed their reference read,
so a confirmatory model claim requires independent meetings.

The complete result is [verdict.json](verdict.json).
