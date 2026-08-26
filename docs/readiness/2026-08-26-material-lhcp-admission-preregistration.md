# E-MATERIAL-LHCP-ADMISSION preregistration

## Question

Can the 72 reference-unread LHCP-ASR evaluation talks be joined one-to-one to their
official CERN Indico contributions, with contemporaneous slide material present for
every admitted talk, without reading reference text, audio bytes, or slide contents?

## Frozen sources and firewall

- Hugging Face: `mllp/LHCP-ASR` at revision
  `1583283ffe91ee22f7e547fc1248c3646f68fe43`; evaluation splits only.
- CERN Indico: event `856696` (2020) and event `1109611` (2022), JSON contribution
  exports and attachment metadata only.
- Allowed HF fields: split identity and `audio.path` only. `transcription`,
  `audio.bytes`, and every other sample payload are forbidden.
- Allowed CERN projection: event/contribution IDs, title, speakers, duration, and
  attachment filename, URL, content type, size, and checksum. The JSON endpoint may
  transport additional metadata fields, but the audit must not persist, print, join
  on, or otherwise use them. Attachment bodies are forbidden.

The audit may issue HTTP range requests for Parquet footer and `audio.path` column
chunks. It must record transferred-byte counts and projected columns. It may not
download a complete shard, audio object, transcript, slide, or recording.

## Frozen join and gates

For each HF path, derive year/split and a normalized basename using Unicode NFKD,
case folding, extension removal, separator collapse, and ASCII alphanumeric tokens.
Create candidates only from exact identifiers, exact normalized CERN attachment
basenames, or exact normalized contribution-title token sequences. No fuzzy score,
manual reassignment, semantic model, or post-read alias may resolve a row. Multiple
candidates are ambiguous and fail closed.

Admission requires exactly 72 unique HF paths with published counts
`14/11/15/32`, 72 unique CERN contributions, a one-to-one 72/72 join, zero orphan or
ambiguous rows, and at least one non-empty `.pdf`, `.ppt`, or `.pptx` attachment on
every joined contribution. Duplicate URLs/checksums fail. HTTP endpoint reachability
may be checked with HEAD/range-zero requests; material bodies must remain unread.

The only passing verdict is `LHCP_METADATA_JOIN_AND_MATERIAL_COVERAGE_CLOSED`.
Otherwise return `LHCP_ADMISSION_INCOMPLETE` with per-reason counts. This experiment
does not authorize slide readability/OCR, candidate extraction, Pass0, embedding,
Omni calls, or reference reading.
