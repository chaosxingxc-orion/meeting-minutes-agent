# E-MEETING-MATERIAL-SEMANTIC-SIGNAL preregistration

## Question

Can an encode-only semantic text retriever transfer the useful part of the
umbrella SAEA Q-K-V mechanism to meeting-material routing, while retaining the
same runtime query, balanced inventory, and wrong-meeting control that the
lexical audit used?

## Frozen comparison

This is a new exploratory construction, not a repair of the consumed lexical
read. It inherits exactly the same 751 expected non-exact Pass0 queries, three
meetings, eight SHA-selected keys per meeting, canonical values, source spans,
and ascending-ID deranged rotation. It changes only the ranking representation:
BM25 word/trigram features are replaced by Qwen3-Embedding-0.6B-Q8_0 cosine
similarity.

The model is the umbrella-pinned GGUF with SHA-256
`06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`.
It runs through the existing llama.cpp server binary with SHA-256
`22755a59472da16358ed513b6720d1c0238614b18a1e2cc4e3a968aa010f4abd`.
The process is structurally encode-only (`--embedding --pooling last`); it has
no answer-generation authority. The query instruction and key prefix are frozen
in configuration.

A turn dispatches only when the cosine gap between the best and second-best key
across the two compared eight-key inventories is at least 0.02. This gate is
defined before corpus embedding and does not inspect the correct-meeting label.
Reference transcripts, audio, the earlier gold-read result, and Omni remain
unavailable.

## Frozen gates

The eligible query count must equal 751. All other gates must pass: dispatch
coverage at least 20%; correct-material attribution precision at least 70%; at
least two meetings individually reach 60%; median correct-minus-deranged cosine
at least 0.01; and attribution precision improves by at least eight percentage
points over the frozen lexical 61.87% result.

A pass permits only a separately registered Omni capability experiment with
three arms: retain-direct, correct-material dispatch, and equal-dose deranged
dispatch. It does not establish term correctness or WER improvement. A failure
rejects this semantic key representation on the current three-meeting surface.
