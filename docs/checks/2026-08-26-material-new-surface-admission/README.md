# Material new-surface admission receipt

## Verdict

`NEW_SURFACE_COHORT_FROZEN`

The reference-blind admission audit mapped all 100 EarningsCallVoice Core-100
call IDs to FinCall-Surprise. The frozen 2019+2020 scope contained 70 items.
`ECV-0001` was excluded for known dataset-card text exposure; the remaining 69
items all passed authentic audio, same-speaker, nine-human-gate, unique-call,
audio-hash, and same-call-PDF checks.

The deterministic split is 20 development, 40 one-shot confirmation, and 9
untouched reserve. The external snapshot contains 138 WAV files (65,228,466
bytes) and 69 selected PDFs (117,765,681 bytes). Only selected PDF members were
fetched through ZIP range reads; two interrupted full-archive temporary parts
totalling 767,557,632 bytes were deleted after this audit passed and can be
recreated from the pinned public archives.

No sealed transcript value was projected into the cohort or verdict. Model
contact was 0 Pass0, 0 embedding, and 0 Omni. The source containers retain their
sealed text fields outside Git for a later frozen reader.

## Frozen hashes

- admission config: `d6ba164abc9863b27e5565d047b7c672a916e044e6cf36f1d478433199c68622`
- cohort: `1b51dd273c15237e8bb4ce210aed3f2929d54f9d5e873c30f9f17deb747a0662`
- admission verdict: `72c8aa2eda16b211beaf5858c09944309f7ccc7bea238a5a6b83ed62ef814456`
- trace schema: `f535205a75f42dde93a3c23af145fae8a8ab065b7a6dce2c6b426cc0d13f601d`
- admission audit: `92070e6ebca1d3cb88ce98e37b2f5233b8615980a02a9cecc017a71efedd3ae7`
- trace validator: `856f2367640868d359e2b3ca3c2ed2c0e3cfa4a89256355e739c9f8335d424c8`
- append-only trace module: `5eeabe317a5d473f2c63635c021bd8be2a00be696f14a3d5548b9f8a56359fa8`

Machine-readable evidence: [verdict.json](verdict.json). The frozen item IDs,
audio/PDF hashes, and split assignments are in the
[cohort](../../../configs/probes/material_new_surface/2026-08-26-cohort.json).

Verification passed: 9 focused trace/admission tests, JSON Schema Draft 2020-12
validation against a complete row, `git diff --check`, and the shared WSL
`~/.venvs/meeting` full offline suite (`1568 passed, 25 skipped`).
