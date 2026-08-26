# E-MATERIAL-LHCP-DEVELOPMENT-FRONTEND preregistration

## Question and scope

Can the frozen deployment front end turn all 25 reference-blind LHCP-ASR
development talks into complete, bounded, speaker-labelled transport slices for a
later Pass0/material-routing experiment? This flight measures structural supply
only. It does not score diarization, read a transcript, contact Omni, or estimate a
transcription effect.

## Frozen inputs and tool

Bind the external 25-WAV manifest with SHA-256
`f82e9958ed81527c89a6922bce6155488fde183699c77a11fee31a22d1661e1f`:
2,469,998,494 source bytes and 37,556.964789 audio seconds. Normalize every file
with WSL FFmpeg 6.1.1 to mono 16 kHz PCM16 WAV. No enhancement, channel selection,
VAD preprocessing, or content filtering is allowed.

Run TOOL-LOCKED(B) only: `nvidia/diar_streaming_sortformer_4spk-v2` revision
`5240a64075176943f677d30fa2171c780229f341`, q8_0 GGUF SHA-256
`0679cfeb1ce356d0dea9470b31274f4bfc7eb927497d82005483770666da998a`,
NeMo-Speech.cpp commit `4c749a7`, CUDA binary SHA-256
`1a3e3f4fe7db4c48e5d6e44a76d5adf2bbfef80024c023b0eab2766eb61aca78`,
default DiarStream geometry. Run exactly one audio-only contact per development
talk, in manifest order, one job at a time, with no parameter override.

## Slice construction and gates

Parse each non-empty RTTM as `TOOL_DIAR` (M0) and call the existing turn-aware
slicer with target/min/max/snap `90/60/120/3` seconds, zero overlap, 16 kHz mono
PCM16 output. Freeze every slice's meeting, index, absolute bounds, predicted
speaker table, bytes, and SHA-256 before Pass0 selection.

Pass only if all 25 conversions and all 25 tool contacts succeed; every meeting
has a parseable non-empty RTTM and at least one slice; all slices are positive and
at most 120 seconds; slice indices are contiguous; and all frozen hashes validate.
No meeting replacement, VAD-only fallback, retry with altered parameters, manual
speaker repair, or reference-based screening is permitted.

The Sortformer budget is exactly 25 contacts over 37,556.964789 input seconds,
with one job, zero semantic retries, a 3,600-second per-contact timeout, and a
two-hour campaign ceiling. Pass0 calls and tokens are deliberately not frozen yet:
their exact budget is derived only after the complete slice manifest exists.

## Authorization boundary

Configuration, conversion preflight, code tests, and zero-model readiness are
authorized. Actual Sortformer execution is a tool-model contact and remains
blocked until EuphoriaYan explicitly releases this registered flight. Pass0,
embedding, Omni correction, confirmation audio, and all reference access remain
outside this registration.
