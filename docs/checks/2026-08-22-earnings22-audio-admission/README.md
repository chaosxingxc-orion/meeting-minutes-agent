# Earnings-22 audio acquisition and admission

## Outcome

Acquisition succeeded: all 125 official Git LFS MP3 objects were downloaded to the
external data root, totalling 1,908,056,329 bytes. Every file matches its upstream
LFS SHA-256; no `.part` files remain. Audio, metadata, and aligned-reference IDs join
exactly 125/125/125, and `ffprobe` opens every file.

The preregistered admission verdict is nevertheless
`EARNINGS22-AUDIO-NOT-ADMITTED`. The failure is limited to the upstream
`metadata.csv` duration gates: nine files differ by more than 2 seconds, aggregate
relative difference is 0.7847%, and the largest difference is 2691.512 seconds.
For the four largest discrepancies, the aligned reference ends near the probed audio
duration, not the CSV duration:

| File | CSV s | MP3 s | Reference max `endTs` s |
|---|---:|---:|---:|
| `4483733` | 3589 | 6280.512 | 6278.73 |
| `4482110` | 1398 | 2107.011 | 2106.55 |
| `4484088` | 6576 | 6396.320 | 6392.96 |
| `4471606` | 3632 | 3769.008 | 3768.1301 |

This supports an upstream metadata-error diagnosis, but it does not retroactively
change the frozen verdict.

The first audit invocation ended before producing a verdict because the probe reader
treated `sample_rate` as mandatory on every stream. The implementation was corrected
to select audio streams and treat descriptive stream fields as optional; no gate or
threshold changed before the successful read above.

## Front-end consequence

Reference-only diagnostics find more than four speakers in 116/125 meetings (maximum
35). Only nine meetings are within the locked Sortformer four-speaker capacity: five
discovery and four reserve. Thus restricting Earnings-22 to the compatible subset
cannot meet the existing 20-eligible-meeting E4 supply gate, while running the locked
front end on the full corpus would systematically merge speakers.

Do not start an Omni pilot yet. The next decision is either to stop this cross-domain
line under the fixed-front assumption, or separately authorize and register a
corpus-wide unbounded-speaker front-end smoke. Gold speaker counts are diagnostic only
and must never route individual meetings at runtime.

## Reproduction

```bash
python scripts/data/acquire_earnings22_audio.py \
  --data-root "$SPEECHRL_DATA_DIR" --acknowledge-internal-research-only
python scripts/data/audit_earnings22_audio.py \
  --earnings22-root "$SPEECHRL_DATA_DIR/datasets/earnings22"
```

See `acquisition-receipt.json`, `verdict.json`, and the preregistration at
`docs/readiness/2026-08-22-earnings22-audio-admission-preregistration.md`.
