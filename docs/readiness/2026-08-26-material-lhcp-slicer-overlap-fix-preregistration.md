# E-MATERIAL-LHCP-SLICER-OVERLAP-FIX preregistration

## Question and evidence boundary

Can a deterministic slicer correction remove every adjacent-slice duplicate
interval from the already frozen 25-meeting LHCP-ASR development front end while
preserving the 120-second transport cap and turn-boundary semantics? This is an
engineering correction experiment, not a diarization or transcription-quality
experiment.

The only admitted inputs are the frozen conversion manifest, 25 converted WAVs,
25 Sortformer RTTMs, and their receipts under
`D:/speechrl-data/derived/lhcp-asr-development-frontend/2026-08-26`. Bind the
conversion manifest SHA-256
`7e654c2229839c1da12ae9ccc32d249c87197aacf44b343f2b7695759fdae128`, flight
summary SHA-256
`9d8d5e1faed8abdac72c75f5e2e33fa256f685ba0f2599b59fa5b53d086b30fa`, and
failed slice manifest SHA-256
`e77d75cdb40c6db6cb5c7c2cada6bbc85ee373d94cec9f8af5d8c99cfe0df917`.
Do not run Sortformer, read reference or confirmation data, or contact Omni.

## Single admitted change

Replace per-turn greedy packing with overlap-component-aware packing. After
sorting turns by `(start, end)`, merge every half-open interval-connected run
(`next.start < current maximum end`) into one atomic component. Greedily pack
those components with the existing target/min/max values `90/60/120` seconds.
Use the maximum end over all turns in a group, not the last sorted turn's end.

An ordinary multi-turn overlap component must never be divided across transport
slices. If such a component itself spans more than 120 seconds, fail closed.
The existing exception for one individual turn longer than 120 seconds remains:
it may use the already defined signal/VAD internal split. Add a final slicer
post-condition rejecting any positive adjacent-slice overlap greater than
`1e-9` seconds in every mode.

No RTTM repair, speaker relabelling, VAD fallback for ordinary components,
meeting replacement, parameter tuning, or change to audio bytes is allowed.

## Frozen execution and gates

Before reslicing, freeze a runtime configuration containing the corrected slicer,
dedicated reslice runner, prebuilt validator, this preregistration, source
artifact hashes, output root, and the unchanged `90/60/120/3`, zero-overlap,
16 kHz mono PCM16 parameters. Write corrected outputs to a new external root;
never overwrite the 397 failed slices.

Pass only if all 25 frozen RTTM hashes and converted WAV hashes revalidate; all
25 meetings produce at least one slice; indices are contiguous; every slice is
positive and at most 120 seconds; every adjacent pair has overlap at most
`1e-9`; all audio files match their manifest hashes and format; and a second run
of the pure planning path is deterministic. Report old/new slice counts and
seconds, but do not interpret them as quality metrics.

## Authorization and stopping rule

EuphoriaYan's instruction to proceed authorizes this zero-model engineering
experiment, including code changes, tests, and one reslice over the frozen RTTMs.
It does not authorize Sortformer reruns, Pass0, embedding, Omni, confirmation
audio, or any reference access. Stop on any source-hash mismatch, overlong
multi-turn overlap component, output collision, failed gate, or non-determinism.
