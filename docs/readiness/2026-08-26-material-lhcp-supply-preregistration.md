# E-MATERIAL-LHCP-SUPPLY preregistration

## Question

Do the 72 admitted LHCP-ASR talks have machine-readable official materials with
enough deterministic professional-term candidates to support a later fixed-width
material-routing experiment?

## Frozen acquisition and split boundary

Download all 77 attachments in the admitted manifest from `indico.cern.ch` to
`D:/speechrl-data/datasets/lhcp-asr-materials/2026-08-26`. Verify every declared
byte size and Indico MD5, then bind a local SHA-256. The total registered download
is 1,648,976,797 bytes. Do not download audio or access any LHCP reference field.

The published development cohort is `dev_2020 + dev_2022` (25 talks); the future
one-shot confirmation cohort is `test_2020 + test_2022` (47 talks). This audit may
parse runtime-visible materials from both cohorts once, but it must emit the full
machine verdict before any human result inspection. No model threshold or prompt is
selected here.

## Frozen extraction and gates

Parse every frozen PDF with `pypdf.PdfReader(strict=False)` and every PPTX by reading
slide XML text with the standard library. Aggregate all registered attachments for a
talk and deduplicate candidates case-insensitively. Candidate extraction reuses
`meeting_minutes_agent.state.meeting_materials.extract_candidate_surfaces`; no new
lexicon, OCR, fuzzy repair, manual alias, meeting replacement, or attachment
substitution is allowed.

A talk passes only if at least one registered attachment yields text, combined
visible text has at least 200 characters, and the existing extractor yields at least
eight unique candidates. Attachment-level parse failures remain visible, but the
experiment passes only when all 72 talks pass, including all 25 development and 47
confirmation talks. Any failed talk yields
`LHCP_ZERO_MODEL_MATERIAL_SUPPLY_INSUFFICIENT` and blocks model contact.

Material pages and candidate strings remain outside Git under
`D:/speechrl-data/derived/lhcp-asr-material-supply/2026-08-26`; Git receives only
aggregate/per-talk counts, hashes, and receipts. This registration authorizes only
material acquisition and zero-model extraction. Pass0, embedding, Omni, reference
reading, OCR, and audio acquisition remain unauthorized.

