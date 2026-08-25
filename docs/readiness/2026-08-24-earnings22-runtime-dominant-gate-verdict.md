# EARNINGS22-RUNTIME-DOMINANT-GATE verdict

Decision: **`RUNTIME-DOMINANT-GATE-UNSAFE`**.

The frozen RTTM-only gate admitted 57 of 76 meetings. It met supply, recall, and
pooled Top-1 requirements, but failed dominance precision (38.60% versus 70%), pooled
Top-2 attribution error (27.79% versus 25%), and unsafe-meeting rate (50.88% versus
10%). See the [read artifact](../checks/2026-08-24-earnings22-runtime-dominant-gate-read/README.md).

Stable predicted occupancy is not a valid proxy for stable true-speaker identity under
a four-speaker capacity limit: stable merging is observationally compatible with true
dominance. Do not use this gate to select an Earnings-22 Omni pilot, and do not search
new thresholds on the same 125 meetings.

The preregistration and verdict enter Git in the same commit. The experiment was run
after the rule and tests were written, but no separate commit boundary proves that
ordering; this is an explicit audit-trail limitation.

The next admissible experiment is a separately registered Pass-0 transcription supply
audit whose unit is a repeated meeting/speaker/term cluster. It must distinguish stable
correct, stable wrong, and unstable outputs, and a stable wrong cluster is actionable
only when an independent legal anchor supplies the correction. That experiment still
requires a new model-contact authorization and budget.
