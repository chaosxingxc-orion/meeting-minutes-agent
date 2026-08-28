# LHCP local-candidate ceiling check

`E-MATERIAL-LHCP-LOCAL-CANDIDATE-CEILING` completed a post-reference,
development-only oracle audit and returned
`LHCP_LOCAL_CANDIDATE_POOL_INSUFFICIENT`.

The frozen reader reused the already acquired 25 development references and
the 396-row semantic trace. It evaluated all eight correct-meeting candidates
per slice, for 3,168 candidate pairs. It made no new source reference request,
read no confirmation data, and made no embedding or Omni call.

The audit found 44 candidate-level wrong-to-correct opportunities. After
deduplicating within each slice, only 39/396 slices (9.85%) contain any
opportunity, spread across 14 meetings. This misses the 50-slice exploratory
gate and the 157-slice primary gate. Semantic top1 captures 12/39 opportunity
slices (30.77%), exactly reconciling with the preceding audit.

The result identifies both a routing loss and a stronger supply ceiling. An
oracle router could recover 27 additional slices, but even perfect selection
within the frozen eight-key inventory cannot reach the exploratory sample
target. The next diagnostic is the complete frozen material candidate pool;
threshold tuning on the eight-key router is stopped.

## Verification

```bash
/home/yansuqing/.venvs/meeting/bin/python -m pytest -q \
  tests/unit/scripts/test_material_lhcp_local_candidate_ceiling.py
# 2 passed
```

Row-level artifacts remain under external storage. See `read.json` and
`artifact-summary.json` for aggregate evidence and hashes.
