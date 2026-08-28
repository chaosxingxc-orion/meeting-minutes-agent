# LHCP development opportunity and power audit

`E-MATERIAL-LHCP-DEVELOPMENT-OPPORTUNITY-POWER-AUDIT` completed its
pre-registered, zero-model development-reference read and returned
`LHCP_CORRECTION_OPPORTUNITY_INSUFFICIENT`.

The acquisition projected only `audio.path` and `transcription` from the six
frozen development Parquet files. It closed all 25 expected identities using
666,630 transferred bytes. It read no audio body, confirmation reference, or
test split. Reference text remains in external storage and is not committed.

The one-shot reader evaluated all 396 frozen semantic top1 activations. It
classified 56 as retain, 12 as wrong-to-correct opportunities, and 328 as
locally unsupported. The 12 opportunities span eight meetings, and local
reference support is 17.17%. All primary gates failed: the registered target
requires 157 opportunities, 15 meetings, and 70% local support. The weaker
50-opportunity/10-meeting exploratory gate also failed.

Across the complete 200-key meeting inventories, only 44 keys occur in the
reference and only seven are absent from Pass0. Concatenated Pass0 has a
descriptive micro-WER of 14.81% (14,677 errors over 99,107 reference tokens).
This baseline is not a correction result.

The evidence rejects the planned 1,188-call retain/correct/deranged Omni
flight. High correct-meeting attribution did not imply that the retrieved
canonical was locally spoken or incorrectly transcribed. Any successor must
pre-register a rejectable local entity proposal or material-span retrieval
design; it may not use these gold-derived categories to select calls.

## Verification

```bash
/home/yansuqing/.venvs/meeting/bin/python -m pytest -q \
  tests/unit/scripts/test_material_lhcp_development_opportunity_power.py
# 3 passed

/home/yansuqing/.venvs/meeting/bin/python -m pytest -q
# 1620 passed, 25 skipped
```

External references and row-level census artifacts are under
`D:/speechrl-data/derived/lhcp-asr-development-reference-opportunity/`.
See `artifact-summary.json` and `read.json` for aggregate metrics and hashes.
