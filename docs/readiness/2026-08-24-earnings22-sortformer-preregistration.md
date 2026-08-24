# EARNINGS22-SORTFORMER-SMOKE — preregistration

Date: 2026-08-24. Status: **REGISTERED**. Owner requested a full Earnings-22
Sortformer accuracy check, specifically testing the hypothesis that one or two dominant
speakers may remain usable even when a call contains more than four reference speakers.

## Fixed inputs and tool

- All 125 Earnings-22 MP3 objects from
  `revdotcom/speech-datasets@c05ab6fd8b4b627d123c922a22a39e993dd37635`.
- Frozen roster: `configs/probes/earnings22_sortformer/2026-08-24-roster.json`.
- Deterministic adapter: FFmpeg mono 16 kHz PCM16 WAV. No enhancement, VAD, channel
  selection, or threshold tuning.
- Locked deployment tool B: `nvidia/diar_streaming_sortformer_4spk-v2`, q8_0 GGUF
  SHA-256 `0679cfeb...da998a`, NeMo-Speech.cpp commit `4c749a7`, binary SHA-256
  `1a3e3f4f...1aca78`, default DiarStream geometry. No model parameter or
  post-processing override.

The tool receives audio only. Reference files are opened only by the scoring pass after
all 125 RTTMs exist.

## Populations

The flight includes every meeting. Metrics are reported for speaker-count strata
`<=4`, `5–8`, `9–16`, and `>16`, plus all `>4` meetings.

The primary hypothesis population was frozen from a zero-model reference-availability
profile before tool contact: aligned-token fraction >= 0.80, at least 300 aligned word
seconds, more than four reference speakers, and Top-2 aligned speech share >= 0.60.
Exactly 30 meetings qualify. This isolates the user's proposed “few dominant speakers,
many rare participants” case without selecting on Sortformer output.

## Metrics and thresholds

Primary metric is aligned-word-duration speaker attribution error after an exact
one-to-one reference/hypothesis mapping. Report all-speaker, Top-1, Top-2, and tail error,
plus predicted speaker count. Secondary proxy DER reconstructs reference turns by merging
only consecutive same-speaker aligned words separated by <=1.0 s; report no-collar and
0.25 s collar variants. It is explicitly not human-RTTM DER.

On the 30-meeting primary population:

- `MAIN-SPEAKER-DIARIZATION-USABLE` if pooled Top-2 error <=25% and Top-1 error <=20%.
- `MAIN-SPEAKER-DIARIZATION-POOR` if Top-2 error >40% or Top-1 error >35%.
- otherwise `MAIN-SPEAKER-DIARIZATION-UNCERTAIN`.

## Budget and validity

Maximum four wall-clock hours for 125 tool contacts; each meeting has a resumable receipt.
Conversion and scoring are zero-tool passes. Missing/failed RTTM, hash mismatch, roster
change, threshold change, gold exposure to the tool, or a second score read invalidates
the claimed verdict. No Omni contact is authorized by this experiment.
