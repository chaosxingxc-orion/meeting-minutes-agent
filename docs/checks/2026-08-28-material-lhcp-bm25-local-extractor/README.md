# LHCP BM25 local extractor check

`E-MATERIAL-LHCP-BM25-LOCAL-EXTRACTOR` completed its post-reference
development discovery and returned `BM25_LOCAL_EXTRACTION_INSUFFICIENT`.

Ranking was reference-blind. The frozen per-meeting BM25 index used three
canonical copies plus the lowest-page source span, with `k1=1.2` and `b=0.75`.
Gold opportunity IDs entered only the one-shot evaluator. No new reference,
confirmation, embedding, or Omni contact occurred.

At the primary width of eight, `current_only` retrieved an opportunity for
44/206 oracle opportunity slices (21.36%) across 23 meetings.
`current_plus_prior` reached 47/206 (22.82%), also across 23 meetings. Both miss
the 50-slice exploratory gate and the 157-slice primary gate. Frozen prior
keywords add only three hits.

Width 16 reaches 71 and 73 slices descriptively, but width eight was the
pre-registered primary and cannot be changed after the read. Even width 16
remains far below the primary power target. Lexical source-span retrieval is
therefore not an adequate full-pool extractor. A full-pool semantic embedding
experiment may be prepared, but requires separate model-contact authorization.

## Verification

```bash
/home/yansuqing/.venvs/meeting/bin/python -m pytest -q \
  tests/unit/scripts/test_material_lhcp_bm25_local_extractor.py
# 3 passed

/home/yansuqing/.venvs/meeting/bin/python -m pytest -q
# 1626 passed, 25 skipped
```

Row-level rankings remain in external storage. Aggregate evidence and hashes
are recorded in `read.json` and `artifact-summary.json`.
