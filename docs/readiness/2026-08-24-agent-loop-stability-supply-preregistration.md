# E-LOOP-STABILITY-SUPPLY preregistration

This zero-model audit asks whether the four completed Earnings-22 Pass-0 meetings contain
enough chronological, cross-window recurrence to support a bounded sliding-memory model
experiment. It reuses all 1,429 frozen replies and does not call Omni.

The frozen configuration is
`configs/probes/agent_loop_stability/2026-08-24-supply.json`. Five-minute windows are used.
At each turn, keyword memory may contain only earlier Pass-0 text. A carry opportunity
requires a current output token to have appeared in an earlier time window; the stricter
speaker measure also requires the same predicted speaker. Reference transcripts, labels,
and score manifests are forbidden inputs.

The verdict is `LOOP-STABILITY-SUPPLY-READY` iff at least three meetings have at least
three windows, at least 100 turns have non-empty bounded global memory, and at least 20
same-speaker cross-window carry opportunities exist. Otherwise the model experiment is
not registered. Passing establishes only measurement supply. It cannot establish that a
remembered form is correct, that summaries improve ASR, or that an agent loop is safe.

The follow-up model design, if admitted, must compare bare, recent-tail, summary plus
global keywords, summary plus speaker keywords, and a provenance-matched deranged control.
It must process every frozen turn, keep audio/front end/decode fixed, and score stability
separately from utility.
