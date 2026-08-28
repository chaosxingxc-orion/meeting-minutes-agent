# LHCP full material-pool ceiling check

`E-MATERIAL-LHCP-FULL-POOL-CEILING` completed its post-reference,
development-only source-coverage audit and returned
`LHCP_FULL_MATERIAL_POOL_POWER_READY`.

The frozen reader reused the 25 locally acquired development references, 396
Pass0 slices, and the original reference-blind material pool. It evaluated
4,886 development candidates across their own meeting slices, totaling 81,634
slice-candidate pairs. It acquired no new reference, read no confirmation data,
and made no embedding or Omni call.

The full pool contains 416 candidate-level wrong-to-correct opportunities from
300 unique candidates. These form 206/396 opportunity-bearing slices (52.02%)
across all 25 meetings, passing the 157-slice/15-meeting primary supply gate.
At least one locally supported candidate exists for 379/396 slices.

This reverses the eight-key ceiling diagnosis at the source-pool level: the
material source is sufficiently rich, while salted-hash width-eight extraction
discarded most local supply. Runtime safety remains unresolved. Of 416
opportunity pairs, 316 use one-token canonicals, 68 use two, 23 use three, and
9 use four. The next experiment must test a reference-blind local extractor and
must not treat oracle membership as a runtime dispatch signal.

## Verification

```bash
/home/yansuqing/.venvs/meeting/bin/python -m pytest -q \
  tests/unit/scripts/test_material_lhcp_full_pool_ceiling.py
# 1 passed
```

Row-level artifacts remain in external storage. Aggregate evidence and hashes
are recorded in `read.json` and `artifact-summary.json`.
