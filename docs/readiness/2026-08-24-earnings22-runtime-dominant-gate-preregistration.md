# EARNINGS22-RUNTIME-DOMINANT-GATE preregistration

Registered: 2026-08-24, before computing any RTTM occupancy or gate metric.

This is a retrospective, zero-model audit over the already frozen 125-meeting Sortformer
flight. It is not a new confirmatory dataset: prior aggregate reference results are known.
No threshold search is permitted. Runtime features are limited to RTTM cluster identities,
segment times, and durations.

The primary gate and decision thresholds are frozen in
`docs/plans/2026-08-24-earnings22-runtime-dominant-gate.md`. The implementation must refuse
to overwrite its output. Gold/reference fields may be joined only for the one-shot scoring
stage. The output must report every meeting, confusion counts, coverage, precision, recall,
pooled Top-1/Top-2 attribution error, and the unsafe-meeting fraction.

An occupancy-only rule (300 seconds and global Top-2 share at least 0.60) and the unfiltered
eligible universe may be reported as labelled diagnostics. They cannot replace the primary
stable-window gate or change the verdict.
