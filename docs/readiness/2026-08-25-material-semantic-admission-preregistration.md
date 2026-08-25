# E-MATERIAL-SEMANTIC-ADMISSION preregistration

## Question

Does the frozen Earnings-22 roster still contain at least six meetings whose
reference lexical surfaces have never been available to a completed experiment
read? A passing cohort is required before acquiring official materials or
constructing a development/confirmation split.

## Frozen exclusion rule

A meeting is excluded when its reference lexical surfaces were available to a
completed repository experiment. The E4 v2 discovery read and E4 v3 reserve
read are the only exclusion inputs. Sortformer speaker counts, speaker timing,
audio duration, and byte hashes do not exclude a meeting because they expose no
reference words. The audit reads manifests and IDs only; it must not reopen any
reference transcript.

## Gates and consequence

The roster must contain 125 unique IDs; v2 must contribute exactly 80 discovery
IDs; v3 must contribute exactly 45 reserve IDs; and the two sets must be
disjoint subsets of the roster. Admission requires at least six remaining IDs,
which would be frozen as three development and three one-shot confirmation
meetings before source discovery.

If fewer than six remain, return
`ADMISSION_FAILED_NO_REFERENCE_UNREAD_MEETINGS`. Do not download materials,
decode audio, inspect Pass0, contact Omni, or weaken “reference-unread” to
“outcome-unread.” The dependent runtime-gate experiment must stop at its
prerequisite check.
