# E-MATERIAL-RUNTIME-GATE-CI preregistration

## Evidence status and question

This is a deliberately weaker replacement for the blocked history-unread
experiment. It asks whether a within-meeting semantic top-1/top-2 gap transfers
under a construction-isolated six-meeting reuse. A pass is labeled
`CONSTRUCTION_ISOLATED_SIGNAL_PRESENT`; it is not an independent confirmation.

All 125 Earnings-22 references were exposed by earlier E4 v2/v3 lexical supply
reads. This registration preserves that fact and does not revise
`E-MATERIAL-SEMANTIC-ADMISSION`. The current constructor, material retriever,
threshold fitter, and runtime inputs must nevertheless remain reference-blind.

## Frozen cohort

The frozen registration JSON has SHA-256
`67ff8ae1fb6afe7652c7d06a56de065a9ee6e4bf2a4401c2a6e0e8800c4cb4af`.
Development is `4474506` Costco, `4479944` HDFC Bank, and `4483506` Sony.
Confirmation is `4483633` Ferrari, `4484563` Sanofi, and `4485244` KKR. Each
split contains one historical reserve meeting and two historical discovery
meetings. Selection used only IDs, issuer/ticker, date/period, and official
material availability. Reference words, reference-derived entities, speaker
shares, prior per-meeting audit outcomes, WER, and retrieval scores are barred.

There are no replacements. Before processing any Pass0, each meeting must have
at least one issuer or regulated-filing document published no later than the
meeting date and at least eight deterministically extracted candidates. Call
transcripts, analyst transcripts, and post-meeting recaps are forbidden. A
single failure returns `COHORT_ADMISSION_FAILED`.

## Frozen construction and runtime gate

Freeze source URLs, raw hashes, candidate spans, audio/chunks, predicted
speaker IDs, T1-A1 Pass0 outputs, and all query rows before fitting. Pass0 does
not currently exist for this cohort; producing it requires a separate flight
registration and owner authorization. This registration authorizes zero model,
embedding, download, and reference calls.

The query is Pass0 text plus predicted speaker ID and bounded prior topic
keywords. Retrieval uses only the query meeting's official-material index. The
deployable selector is its top-1 minus top-2 cosine gap. The wrong-meeting index
is a fixed ascending-ID rotation within each split; it is an equal-width
experimental control and is unavailable to the selector.

## Development, confirmation, and claims

On development, choose the lowest threshold in
`[0.00, 0.01, 0.02, 0.03, 0.04, 0.05]` reaching 70% attribution precision and
20% coverage with all three meetings represented. Freeze it before the sole
confirmation read. Confirmation requires 70% precision, 20% coverage, at least
two meetings individually at 60%, and median correct-minus-deranged cosine of
0.01.

A pass permits only a separately preregistered exploratory Omni
retain/correct/deranged capability flight. It does not establish external
generalization, term correctness, WER benefit, or training-free policy search.
