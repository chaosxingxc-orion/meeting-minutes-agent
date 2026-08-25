# E-MEETING-MATERIAL-RETRIEVAL-SIGNAL verdict

## Decision

`RETRIEVAL-SIGNAL-INSUFFICIENT` — do not admit a retain/dispatch Omni flight
from the lexical BM25 construction.

The construction has high reachability but insufficient attribution. It
dispatches on 729 of 751 eligible turns and selects the correct meeting's key
451 times (61.87%). Only Galp passes the 60% per-meeting floor; Jeronimo Martins
and TeamViewer are below chance. The pooled median margin passes because Galp's
positive margins dominate, so the failed distribution gate is substantive.

The result supports a narrower statement: meeting-material retrieval signal is
possible in at least one observed scene, but does not yet generalize across the
three meetings. This matches the owner's concern that a route may be highly
scene-dependent.

The next admissible comparison is the same frozen Q, balanced K/V inventory,
and deranged control with a separately registered encode-only semantic text
retriever. It is a new exploratory construction, not a threshold repair. Only
if semantic attribution passes may a model experiment test SAEA-style
retain-direct versus dispatch-revision behavior.

- [Preregistration](2026-08-25-meeting-material-retrieval-signal-preregistration.md)
- [Structural evidence](../checks/2026-08-25-meeting-material-retrieval-signal-read/README.md)
