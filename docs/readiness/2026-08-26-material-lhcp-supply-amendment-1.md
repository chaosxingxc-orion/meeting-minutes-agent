# E-MATERIAL-LHCP-SUPPLY amendment 1

Attempt 1 stopped before any aggregate verdict while writing the external
`material-pages.jsonl`: a PDF text extractor returned the lone surrogate code point
`U+D835`, which Python correctly refused to serialize as UTF-8. No candidate counts,
per-talk gate results, or aggregate results were emitted or inspected.

The partial 1,836,367-byte trace was moved without modification to
`D:/speechrl-data/derived/lhcp-asr-material-supply/2026-08-26-attempt-1-serialization-failed`.
Its SHA-256 is
`0685f3411713625ad1640c8af8ea04b1f8c87c9ac82dd1d325945ed0c7822072`.

The only prospective repair replaces code points in `U+D800..U+DFFF` with `U+FFFD`
immediately after document extraction and before candidate extraction or JSON
serialization. Legal Unicode code points, document selection, parser versions,
candidate rules, thresholds, split boundaries, and failure rules remain unchanged.
Retry outputs use a new external directory and `verdict-v2.json`; attempt 1 is not
overwritten.

