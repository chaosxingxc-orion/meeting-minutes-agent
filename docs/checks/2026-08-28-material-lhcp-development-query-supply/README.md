# LHCP development query-supply check

`E-MATERIAL-LHCP-DEVELOPMENT-QUERY-SUPPLY` passed its frozen zero-model
construction and independent reconstruction. The verdict is
`LHCP_DEVELOPMENT_QUERY_SUPPLY_READY`.

The builder reused the SHA-256-bound LHCP candidate pool and selected eight
keys for each of 25 development meetings. It froze 200 keys and 396 ordered
queries from 4,886 available candidates. Of the queries, 371 include keywords
from only the immediately preceding same-meeting slice; the 25 first slices
have no history. The one length-limited Pass0 row remains present and marked.

The cyclic wrong-meeting mapping is bijective, has zero fixed points and keeps
eight keys on both sides of every future comparison. Independent reconstruction
found no count, order, hash, causal-context or forbidden-field error. Reference,
confirmation, embedding and Omni contact were all `NONE`.

Query text is bounded: median 1,620 characters, p95 2,098 and maximum 2,546.
All 396 rows have frontend speaker labels; 133 contain more than one label.
This is a valid meeting-material supply, not evidence that speaker-specific
attribution or transcription improvement is available.

## Verification

```bash
/home/yansuqing/.venvs/meeting/bin/python -m pytest -q
# 1615 passed, 25 skipped
```

The external one-write artifacts are under
`D:/speechrl-data/derived/lhcp-asr-development-query-supply/2026-08-28-v1`.
See `artifact-summary.json` for their hashes and `structural-read.json` for the
machine verdict. No dataset or transcript payload is committed.
