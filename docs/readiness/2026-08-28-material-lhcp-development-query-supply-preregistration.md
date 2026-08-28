# E-MATERIAL-LHCP-DEVELOPMENT-QUERY-SUPPLY preregistration

## Question and scope

Can the frozen LHCP material inventory and completed Pass0 trace produce a
complete, causal and reference-blind retrieval supply for all 396 development
slices? This experiment freezes inputs for a later semantic retrieval gate. It
does not run embeddings or Omni correction and cannot establish material
attribution, WER improvement or agent-loop stability.

## Frozen construction

The source is the existing SHA-256-bound LHCP candidate pool; PDFs are not
reparsed and failed documents are not repaired or replaced. For each of the 25
development meetings, select exactly eight candidates by a salted SHA-256 order.
Each value retains canonical form, category, document-relative path, page and
source span. The control maps sorted meeting IDs to the next ID cyclically, so it
is an equal-width fixed-point-free bijection.

Each query contains the current Pass0 transcript, current fixed-frontend speaker
labels and at most eight content keywords from only the immediately preceding
slice in the same meeting. It must never use a future slice, another meeting,
reference text or confirmation data. Position 301 is retained but explicitly
marked potentially truncated; no selective re-listen or replacement is allowed.

## Passing gates

- exactly 25 meetings, 200 selected candidates and 396 ordered queries;
- at least eight source candidates and exactly eight selected keys per meeting;
- zero derangement fixed points and a bijective wrong-meeting mapping;
- exact reconstruction from the frozen cohort, candidate pool and Pass0 index;
- zero forbidden gold/reference fields and zero confirmation, embedding or Omni
  contact.

Only `LHCP_DEVELOPMENT_QUERY_SUPPLY_READY` passes. A passing result authorizes a
separate embedding-runtime registration; it does not authorize that model call.

## Artifacts and stopping rules

Large selected-candidate and query traces are written once under
`D:/speechrl-data/derived/lhcp-asr-development-query-supply/2026-08-28-v1`.
The repository stores the frozen config, aggregate readout and hashes only.
Any source or script hash drift, count mismatch, candidate underflow, causal
history violation, invalid control, or existing output directory stops the run.
