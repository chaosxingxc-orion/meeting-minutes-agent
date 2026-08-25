# E-MEETING-MATERIAL-RETRIEVAL-SIGNAL preregistration

## Motivation and transfer boundary

The umbrella SAEA result uses a Q-K-V knowledge plane plus a retain/dispatch policy:
direct output remains primary, while evidence-supported cases are dispatched to a
retrieval-conditioned path. This experiment transfers that structure, not SAEA's
task-specific policy or its reported accuracy gain.

The meeting query `Q` is frozen Pass0 chunk text. Each `K` is an official-material
source span plus its canonical term. `V` is the unembedded canonical term and its
page/document provenance. No value is injected into a model in this experiment.

## Frozen design

Use the three candidate-bearing meetings from
`E-MEETING-MATERIAL-SUPPLY-AUDIT`. Select exactly eight keys per meeting by
SHA-256 ordering with the frozen salt. This equals the smallest meeting inventory
and prevents the larger document from receiving a retrieval-width advantage.

Index word features and character trigrams only for tokens of at least five
characters with deterministic BM25 (`k1=1.2`, `b=0.75`). Tokens shorter than three,
English stop words, and generic earnings-call words are excluded. Short acronyms
never receive fuzzy character features. A query must retain at least three content
tokens and must not contain an exact alias from either compared arm.

For each meeting, compare its eight keys with the next eligible meeting's eight
keys in ascending-ID rotation. A turn dispatches only when either arm has positive
retrieval score. Ties are failures, not half wins. No reference transcript, audio,
candidate correctness label, or result from today's gold read is opened.

## Frozen gates

All gates must pass: three meetings; at least 400 eligible turns; dispatch coverage
at least 20%; correct-material attribution precision at least 70%; at least two
meetings individually reach 60%; and pooled median normalized correct-minus-wrong
margin is at least 0.05.

A pass establishes only that meeting-specific official material supplies a
runtime-visible retrieval signal stronger than an equal-width wrong-meeting
control. It permits a separately registered retain/dispatch capability experiment.
It does not establish term correctness, WER gain, or Omni evidence use. A failure
rejects this lexical Q-K-V construction without reopening today's reference read.
