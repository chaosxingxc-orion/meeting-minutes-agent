# Earnings-22 audio admission — preregistration

## Scope

This is a zero-model acquisition and integrity audit. It may read MP3 container
metadata and aggregate speaker counts from reference files, but it must not run ASR,
contact the frozen core, run diarization, expose reference words to runtime code, or
estimate a transcription effect.

The source is `revdotcom/speech-datasets` at commit
`c05ab6fd8b4b627d123c922a22a39e993dd37635`, directory `earnings22/media`.
Audio is handled as internal-research-only and must not be redistributed because the
upstream license file explicitly names transcripts and associated alignment text, not
audio.

## Frozen checks

The audit passes only if all conditions hold:

1. The official Git LFS tree contains exactly 125 objects totalling 1,908,056,329
   bytes, and every local MP3 matches its LFS SHA-256 and byte count.
2. Audio IDs, `metadata.csv` IDs, and force-aligned NLP reference IDs form an exact
   125-way join with no extras or omissions.
3. `ffprobe` opens all 125 files and reports at least one audio stream.
4. Each probed duration differs from the integer metadata duration by at most 2.0
   seconds, and aggregate duration differs by at most 0.1%.

Reference speaker counts may be reported only as a distribution and as the number of
meetings above the locked Sortformer four-speaker capacity. They are diagnostic gold,
never an input to diarizer routing or transcription.

## Decision

- `EARNINGS22-AUDIO-ADMITTED`: all frozen checks pass. Proceed only to a separately
  registered fixed-front compatibility smoke.
- `EARNINGS22-AUDIO-NOT-ADMITTED`: any check fails. Repair acquisition or stop; do not
  compensate by changing scoring thresholds after reading results.

Passing does not authorize a model pilot, prompt optimization, or an agent loop.
