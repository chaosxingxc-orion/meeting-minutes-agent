# E4-XDOMAIN-SUPPLY-AUDIT-v2 preregistration

Date: 2026-08-21. Status: **REGISTERED BEFORE DISCOVERY AGGREGATE READ**. The owner authorized a zero-model Earnings-22 supply audit. No model contact, audio acquisition, audio decoding, or reserve analysis is authorized.

## Question and frozen identity

The audit asks whether a new business-domain surface has enough upstream-labelled, speaker-exclusive professional-entity recurrence to replace Product/AMI in later design work. Following the pre-read schema amendment, it uses only `transcripts/force_aligned_nlp_references/*.aligned.nlp` from Rev's Earnings-22 commit `c05ab6fd8b4b627d123c922a22a39e993dd37635`. The text acquisition was independently verified as 422 Git blobs with zero mismatch; the audit expects exactly 125 force-aligned NLP references and no audio.

The deterministic split salt is `e4-xdomain-supply-v2-2026-08-21`. Files are ranked by `SHA256(salt + "\0" + file_id)`, then `file_id`; the first 80 are discovery and the remaining 45 are reserve. A manifest may hash reserve bytes for identity closure, but the audit must never parse reserve content or report reserve statistics.

## Frozen proxy, units, and gates

The parser reconstructs upstream entity mentions by contiguous entity ID and class within each speaker stream. It normalizes the surface with Unicode NFKC, lowercase, and whitespace collapse. Temporal and numeric classes (`DATE`, `TIME`, `YEAR`, `MONEY`, `PERCENT`, `CARDINAL`, `ORDINAL`, `QUANTITY`, `DURATION`, `MEASURE`) are excluded; every other explicitly tagged class is admitted as a professional-entity proxy. Mentions without a valid aligned `ts` are conservatively excluded and only their aggregate count may be reported.

Tokens are assigned to fixed 90-second pseudo-slices. A `speaker × pseudo-slice × surface` is counted once. A later unit is speaker-exclusive carry exactly when the same speaker used the surface earlier and no other speaker had used it earlier. The output may contain only aggregate counts, distributions, class counts, hashes, gates, and a decision; tokens, surfaces, entity IDs, and per-file results are prohibited.

Discovery passes only if it has at least 20 meetings, at least 20 meetings with two or more exclusive units, at least 100 exclusive units, and no single surface above 20% of exclusive supply. The ordered outcomes are `INVALID-AUDIT`, `EARNINGS22-SUPPLY-FEASIBLE`, and `INSUFFICIENT-EARNINGS22-SUPPLY`.

## Interpretation and sole-read discipline

A pass is not an effect estimate and does not establish audio availability, transcription benefit, speaker-routing benefit, or false-hint safety. Combined with the already frozen Academic/ICSI v1 pass, it permits only a separately preregistered cross-domain design after audio licensing and acquisition are resolved. It cannot retroactively change the v1 `DOMAIN-LIMITED-SUPPLY` verdict.

Implementation and synthetic tests follow this registration. Before the sole read, an amendment must freeze implementation hashes, the input manifest hash, and offline test results. The CLI must refuse an existing output directory and any manifest, schema, split, or source-identity mismatch.
