# E-MATERIAL-LHCP-DEVELOPMENT-PASS0 preregistration

## Question and scope

Can the frozen Omni core produce a complete, reference-blind Pass0 trace for the
25-meeting LHCP-ASR development cohort after the corrected fixed frontend? The
unit of contact is one frozen transport slice, not a whole meeting and not an
individual diarization turn. Diarization, slicing, confirmation audio, reference
transcripts, meeting materials, retrieval, embeddings, correction, and quality
scoring are outside this flight.

## Frozen inputs and protocol

The sole audio queue is the 396-entry manifest at
`D:/speechrl-data/derived/lhcp-asr-development-slicer-overlap-fix/2026-08-26-attempt-2/slice-manifest.json`,
SHA-256 `1224f0951c6b255523197974368c54e73fd27c4a9b328bf5c909eaf226d695ce`.
It binds 25 meetings and a 37,547.2558125-second manifest upper bound in manifest
order, with zero adjacent overlap and a 120-second maximum slice. Twelve final
WAVs end 16--80 ms before their planned boundary; their frame-count total is
37,546.6638125 seconds and remains inside that frozen upper bound.

The model is `Qwen3-Omni-30B-A3B-Instruct-Q4_K_M`. Prompt
`transcribe-only-v1` supplies audio only: no speaker label, turn table, prior
transcript, reference, material, or glossary reaches the model. Decoding is
`temperature=0`, `seed=0`, `max_tokens=512`; concurrency is one, retries are
zero, and the per-call timeout is 300 seconds. The hard budget is 396 calls,
37,547.2558125 audio seconds, and at most 202,752 output tokens.

## Prospective trace and read

Before every request, the launcher writes and fsyncs the exact JSON body. It then
writes and fsyncs the raw response before appending one ordered index row. A run
may resume only from an exact validated prefix; hash drift, orphan artifacts,
duplicate or non-prefix rows, and request failure stop the run without retry or
in-place repair. Raw artifacts stay on D outside the repository.

The prebuilt reader checks only structural completion, exact audio-only wire
bindings, prompt and decode locks, one successful attempt per slice, usage, and
receipts. It does not open LHCP references or score transcript quality. Its only
passing verdict is `PASS0_TRACE_COMPLETE`; that verdict establishes replayable
provenance, not transcription accuracy or speaker-specific capability.

## Authorization boundary

This registration and readiness audit are zero-model work. Starting the server
or sending any of the 396 requests requires a new explicit authorization after
readiness passes. Later reference scoring, retrieval, embeddings, correction,
GRPO, GEPA, or EM loops require separate registrations and gates.
