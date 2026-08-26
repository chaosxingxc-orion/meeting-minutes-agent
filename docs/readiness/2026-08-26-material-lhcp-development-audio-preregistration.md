# E-MATERIAL-LHCP-DEVELOPMENT-AUDIO preregistration

## Question and scope

Can the 25 frozen LHCP-ASR development talks be acquired and decoded without
reading reference transcripts or touching the 45-talk confirmation cohort? This
is a zero-model acquisition and integrity audit. Passing only supplies measured
audio identities and durations for a later fixed-front Pass0 registration.

The `duration_s` field inherited from the Indico contribution metadata is an
agenda duration expressed in minutes despite its historical field name. It must
not be used as an audio-seconds or model-call budget. Only decoded audio duration
may enter a later runtime budget.

## Frozen acquisition

Use `mllp/LHCP-ASR` revision
`1583283ffe91ee22f7e547fc1248c3646f68fe43`. Read only the six Parquet files whose
published split is `dev_2020` or `dev_2022`; their registered remote total is
2,276,036,639 bytes. Project only `audio.path` and `audio.bytes`. The
`transcription` leaf is forbidden. Do not open any `test_2020` or `test_2022`
Parquet file.

The exact expected set is the 25 development items in the frozen 70-talk cohort.
Write audio outside Git under
`D:/speechrl-data/datasets/lhcp-asr-development-audio/2026-08-26`, preserving
split and filename. Existing complete files may be reused only when their local
manifest binding matches; partial or unexpected files fail closed.

## Integrity gates

Pass only if all 25 expected paths occur exactly once, no confirmation path is
read, every payload is non-empty and opens as WAV, every decoded duration is
positive, and every output has a local SHA-256. Persist an external download
manifest and commit only counts, hashes, duration summaries, transfer accounting,
and the machine verdict.

The passing verdict is `LHCP_DEVELOPMENT_AUDIO_ACQUIRED`. Any mismatch yields
`LHCP_DEVELOPMENT_AUDIO_INCOMPLETE` and blocks front-end or model work.

## Authorization boundary

The instruction to proceed on 2026-08-26 releases this development-only audio
acquisition and zero-model decode audit. It does not authorize reference access,
confirmation audio, Sortformer, slicing, Pass0, embedding, Omni correction, or
model-based selection. Those stages require their own frozen inputs and gates;
actual model contact additionally requires explicit authorization.
