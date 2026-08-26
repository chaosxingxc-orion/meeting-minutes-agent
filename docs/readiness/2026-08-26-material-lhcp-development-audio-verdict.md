# E-MATERIAL-LHCP-DEVELOPMENT-AUDIO verdict

## Decision

`LHCP_DEVELOPMENT_AUDIO_ACQUIRED`

All 25 frozen development talks were acquired from the six registered
`dev_2020` and `dev_2022` Parquet files. The run projected only `audio.path`
and `audio.bytes`; no test shard or `transcription` column was opened.

The 25 WAV files total 2,469,998,494 bytes and 37,556.964789 decoded seconds
(10.4325 hours). Per-talk duration ranges from 1,060.032 to 2,172.032 seconds,
with median 1,491.008 seconds. Fourteen files belong to `dev_2020` and eleven
to `dev_2022`. Twenty-three files are 32 kHz, one is 44.1 kHz, and one is
48 kHz; a later fixed front end must therefore normalize them prospectively.

The first attempt stopped after five complete WAV files when a large HTTP Range
response disconnected. Amendment 1 split ranges into at most 16 MiB and required
the five existing files to match newly downloaded source payloads exactly before
reuse. The second attempt completed all files. No partial output entered the final
manifest.

The external download manifest has SHA-256
`f82e9958ed81527c89a6922bce6155488fde183699c77a11fee31a22d1661e1f`.
Offline readback rehashed and decoded every WAV and returned `TRACE_COMPLETE`
with no errors. Reference reads, confirmation audio reads, Sortformer, Pass0,
embedding, and Omni calls all remained zero.

This verdict supplies real audio identities and durations only. It does not
authorize or establish diarization quality, slicing adequacy, transcription
quality, material-routing gain, or complete 72-talk coverage. The next gate is a
separately registered fixed Sortformer and slice-supply run on these 25 files.
