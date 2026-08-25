# E-CHUNK-RETRIEVAL preregistration

## Question and frozen surface

This experiment tests whether an output-only, speaker-routed, per-chunk retrieval loop
can improve transcription-form consistency without the copying, divergence, or quality
damage observed under broadcast recent-tail and summary context. The frozen runtime is
`configs/probes/chunk_retrieval/2026-08-24-runtime.json`, content hash
`7b54bb6a1e38d7d8a84f0dcb0556df13f389438247d95e6d6cde58fe9015d855`.

It binds four Earnings-22 meetings, 1,429 turns, the prior complete Pass0, score manifest,
retriever, launcher, one-shot reader, prompt, decoding settings, and the passing v3
zero-model supply audit. Gold and reference transcripts are available only to the reader
after both model phases finish.

## Arms and state transition

Each Phase-1 arm reruns every frozen turn with counter-rotated request order.

- `R0-bare`: no text context.
- `R1-global`: at most four candidates retrieved from the meeting output pool.
- `R2-speaker`: at most four candidates from the predicted-speaker output pool.
- `R3-deranged`: equal-cardinality, non-overlapping candidates from exactly one other
  speaker selected by deterministic cyclic first-fit.
- `R2-round2`: rebuild pools and same-chunk queries from the complete `R2-speaker` pass,
  then rerun the same policy once.

The previous pass's same-chunk transcript is a retrieval query only and is never rendered.
No recent transcript tail or meeting summary is supplied. Candidate context is capped at
256 characters and explicitly marked untrusted. All pools use model outputs only.

## Registered decisions

Structural validity requires complete ledgers, 100% context replay and budget compliance,
and 100% distinct, equal-cardinality `R2/R3` controls on eligible turns. Stability requires
R2 consistency to beat bare by at least 2 points and in at least 3/4 meetings, beat R3 in
at least 3/4 meetings, and achieve an R2-round2/R2 edit delta no more than 80% of the
R2/R0 delta.

Safety requires overall WER increase at most 1 point, worst-speaker WER increase at most
2 points, unsupported candidate activation at most 2%, and no increase in language drift.
Only all-gate success returns `CHUNK-RETRIEVAL-STABLE`; stable but unsafe output is
`SPARSE-CONTEXT-STABLE-BUT-HARMFUL`.

## Budget and stopping

Phase 1 is 5,716 calls and 60,308.612 audio seconds. Round 2 is 1,429 calls and
15,077.153 seconds. Total budget is 7,145 calls and 75,385.765 audio seconds, zero retries,
temperature 0, seed 0, and 512 output tokens. An incomplete phase may resume only from
its append-only ledger. No partial scoring is permitted; the frozen reader runs once after
both phases complete.
