# E-MATERIAL-NEW-SURFACE-PASS0 preregistration

## Question and scope

Can the frozen Omni core produce a reference-blind Pass0 transcript for every
development clip on the newly admitted EarningsCallVoice/FinCall surface while
preserving the exact request and response needed by the later material router?
This flight covers the 20 development items only: two authentic, already-cut,
single-speaker WAVs per item. Diarization, slicing, confirmation items, reserve
items, slides, embeddings, material dispatch, reference scoring, and Omni
correction are outside this flight.

## Frozen runtime and budget

The runtime must bind the admission config, frozen cohort, complete-trace schema,
launcher, structural reader, this registration, all 40 WAV hashes, and the exact
model, mmproj, and server-binary hashes. The model is
`Qwen3-Omni-30B-A3B-Instruct-Q4_K_M`; prompt `transcribe-only-v1` contains no
speaker label, reference, material, prior transcript, or supplied text. Decoding
is `temperature=0`, `seed=0`, `max_tokens=512`; one server slot, zero retries,
and a 300-second per-call timeout are fixed.

The hard budget is 40 calls, 592.05 audio seconds, and at most 20,480 generated
tokens. Calls run in the frozen runtime order. No replacement clip or extra call
is allowed.

## Prospective trace and read

Before each HTTP call, write and `fsync` the exact JSON body; after receipt, write
and `fsync` the raw response. Append one ordered index row only after both files
exist and hash correctly. Raw artifacts stay under the external dataset root.
Resume is allowed only from an exact validated index prefix. Orphan artifacts,
hash drift, duplicate/non-prefix rows, request failure, or malformed response stop
the flight without repair in place.

The prebuilt reader is reference-blind. It verifies 40/40 ordered calls, exact
runtime and artifact hashes, audio-only request bodies, fixed prompt/decoding,
one successful non-retry attempt per row, response/text/usage agreement, and the
final receipt. Empty model output is preserved as data. Its only passing verdict
is `PASS0_TRACE_COMPLETE`; this is a provenance verdict, not a WER or capability
claim.

## Authorization and next boundary

EuphoriaYan explicitly authorized actual model execution on 2026-08-26. This
authorization releases this frozen development Pass0 only. Reference reading,
embedding, candidate construction, threshold fitting, confirmation access, and
multi-arm Omni calls require their own frozen runtime and sequential gate.

