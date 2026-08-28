# E-MATERIAL-LHCP-DEVELOPMENT-OPPORTUNITY-POWER-AUDIT preregistration

## Question and authorization boundary

Does the frozen 25-meeting LHCP development trace contain enough distributed,
material-supported transcription opportunities to justify a 1,188-call
retain/correct/deranged Omni experiment? The owner explicitly authorized the
first development-reference read on 2026-08-28. Confirmation remains sealed.
This audit makes no model or embedding calls and may not select future calls by
gold outcome.

## Frozen reference acquisition

Read only `audio.path` and `transcription` from the six `dev_2020` and
`dev_2022` Parquet files in `mllp/LHCP-ASR` revision
`1583283ffe91ee22f7e547fc1248c3646f68fe43`. Match exactly the 25 frozen
development audio paths. Do not project audio bytes or any test split. Persist
the 25 references once under external storage with source-file transfer
receipts and artifact hashes; repository artifacts contain aggregates only.

## Frozen opportunity definitions

Normalize text to lowercase ASCII alphanumeric token sequences. Compute
meeting-level baseline WER with exact word edit distance over the concatenated
Pass0 slices and the whole reference.

For inventory coverage, test every one of the 200 frozen material keys against
its own meeting reference and concatenated Pass0. A key is a meeting-level
candidate opportunity only when its exact normalized canonical phrase occurs
in reference and not in Pass0.

For the primary 396-row census, localize each Pass0 slice to a reference token
span using a deterministic `difflib.SequenceMatcher` boundary proxy over the
whole meeting, then add 12 reference tokens of padding on each side. For the
already frozen semantic top1 candidate:

- `retain`: exact canonical phrase occurs in both current Pass0 slice and the
  localized reference window;
- `wrong_to_correct_opportunity`: it occurs in the localized reference window
  but not the current Pass0 slice;
- `unsupported_activation`: it does not occur in the localized reference
  window.

This proxy is not timestamp gold and cannot establish actual correction. All
396 identities remain eligible for any future model flight; gold categories
are reader-only strata.

## Power and decision rules

Use a paired two-sided normal approximation with alpha 0.05 and 80% power.
Report required pairs for absolute effects 5, 10, 15 and 20 percentage points
under discordant fractions 10%, 20% and 30%. The primary planning target is a
10-point effect at 20% discordance, requiring 157 paired opportunities.

Return `LHCP_CORRECTION_OPPORTUNITY_POWER_READY` only if all are true:

- at least 157 primary wrong-to-correct opportunities;
- those opportunities cover at least 15 of 25 meetings;
- at least 70% of all 396 frozen activations are locally reference-supported
  (`retain` plus `wrong_to_correct_opportunity`).

If at least 50 opportunities cover 10 meetings but a main gate fails, return
`LHCP_CORRECTION_OPPORTUNITY_EXPLORATORY_ONLY`. Otherwise return
`LHCP_CORRECTION_OPPORTUNITY_INSUFFICIENT`. No threshold, padding, phrase rule,
candidate width or trace identity may be changed after reference access.

## Stopping rules

Stop on input/script hash drift, source-size drift, any non-development row,
missing or duplicate identity, empty reference, output collision, or failure to
bind all 25 references and 396 trace rows. Never read confirmation reference or
use reference content in a runtime prompt.
