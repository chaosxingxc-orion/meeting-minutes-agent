# E-MATERIAL-LHCP-ADMISSION verdict

## Decision

`LHCP_METADATA_JOIN_AND_MATERIAL_COVERAGE_CLOSED`

The pinned LHCP-ASR long-form evaluation surface contains exactly 72 unique audio
paths with the published split counts: 14 `dev_2020`, 11 `dev_2022`, 15
`test_2020`, and 32 `test_2022`. Every path encodes an exact CERN event ID and
contribution friendly ID. All 72 identifiers joined one-to-one to distinct official
Indico contributions, with zero orphan, ambiguous, or duplicate bindings.

Every joined contribution has at least one non-empty official PDF/PPTX attachment.
The inventory contains 77 unique attachments: 74 PDF and 3 PPTX; 67 talks have one
attachment and five have two. Their aggregate declared size is 1.536 GiB. All 77
URLs returned HTTP 206 to a zero-byte-consumption range probe, and the advertised
object sizes matched the frozen Indico metadata.

## Firewall and transfer receipt

Only `audio.path` was projected from the 17 pinned Parquet shards. Although their
remote aggregate size is 6,705,900,572 bytes, the footer and selected column reads
transferred 1,116,237 bytes in 34 range requests. Reference, audio-body, material-body,
Pass0, embedding, and Omni contact are all zero. Offline readback reports
`TRACE_COMPLETE`, including 77/77 unique URLs and checksums.

This closes source admission only. It does not establish slide readability, usable
candidate supply, material attribution, transcription improvement, or meeting-loop
generalization. The next experiment must separately register material acquisition,
readability, and zero-model candidate-supply gates before any model contact.

