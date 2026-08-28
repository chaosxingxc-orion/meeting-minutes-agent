# LHCP full-pool semantic extractor check

`E-MATERIAL-LHCP-FULL-POOL-SEMANTIC-EXTRACTOR` completed its unique authorized
flight and returned `FULL_POOL_SEMANTIC_EXTRACTION_EXPLORATORY_ONLY`.

The reference-blind supply is frozen at 4,886 material keys and 396 ordered
current-plus-prior queries across 25 development meetings. Candidate keys use
the canonical and frozen lowest-page source span. Queries contain current Pass0,
current frontend speaker labels, and at most eight keywords from only the
immediately preceding same-meeting slice. They contain no reference or oracle
field.

The flight used the frozen Qwen3 embedding GGUF and llama server with
last-token pooling, float32 L2 normalization, batch size 16, and zero retry.
It produced 5,282 embeddings in 331 local HTTP calls and persisted all
request/response batches, key and query matrices, top-16 rankings, server log,
and an exact receipt. The prebuilt reader uses width eight as primary and
requires 157 opportunity-hit slices across 15 meetings.

The fail-closed audit passed 22/22 checks: all supply, model, server, oracle,
script and budget hashes match; counts and firewalls close; D-drive space is
sufficient; CUDA is visible; and the one-shot flight directory is absent.
The authorized flight then completed 331/331 request/response/index batches,
5,282 embeddings, two 1,024-dimensional vector matrices, and 396 top-16 ranking
rows with zero retry. All receipt hashes close and the server is stopped.
Confirmation and Omni access remain zero.

At the primary width of eight, semantic retrieval hits 53/206 oracle
opportunity slices (25.73%) across 23 meetings. This passes the 50-slice
exploratory floor but misses the 157-slice primary target. Widths 1, 2, 4 and 16
hit 9, 17, 35 and 86 slices. Compared with the current-plus-prior BM25 top-eight
result, semantic retrieval adds only six slices. No correction or confirmation
flight is released.

## Verification

```bash
/home/yansuqing/.venvs/meeting/bin/python -m pytest -q \
  tests/unit/scripts/test_material_lhcp_full_pool_semantic_supply.py \
  tests/unit/scripts/test_material_lhcp_full_pool_semantic_extractor.py
# 3 passed

/home/yansuqing/.venvs/meeting/bin/python -m pytest -q
# 1629 passed, 25 skipped
```

See `readiness.json` and `read.json` for machine-readable preflight and result
evidence. Row-level wire artifacts remain in external storage.
