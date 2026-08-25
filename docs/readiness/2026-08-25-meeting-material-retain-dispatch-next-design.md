# Meeting material retain/dispatch: next experiment design

## Objective

Test whether the distributed semantic retrieval signal can improve frozen Omni
transcription without turning correct terms into errors. This is a design
record, not a registration or authority to contact the model.

## Independent data sequence

Select at least six reference-unread Earnings-22 meetings with temporally legal
official material. Freeze meeting identities, material hashes, candidate spans,
audio, diarization, chunks, Pass0 prompt, and Pass0 outputs before any reference
read. Use one development subset for a deployable within-meeting confidence
rule and a disjoint confirmation subset for the one-shot verdict.

## Frozen runtime loop

For each chunk, form `Q = Pass0 text + predicted speaker ID + bounded prior
topic keywords`. Retrieve only from that meeting's official-material K index.
`V` contains a canonical spelling, category, source page, and a short supporting
span; the embedding never becomes the value. If the within-meeting top-1/top-2
confidence rule fails, retain Pass0. Otherwise create equal-dose arms:

- `R0-retain`: no second model call;
- `R1-correct-dispatch`: identical audio plus the selected V;
- `R2-deranged-dispatch`: identical audio plus a V selected with the frozen
  wrong-meeting control.

The prompt states that V is untrusted spelling evidence and must be ignored
unless supported by audio. Candidate count, characters, order, and call budget
are matched between R1 and R2. Diarizer, chunker, preprocessing, model, decoding,
and speaker attribution remain fixed.

## Read and decision

Freeze the reader before reference access. Score candidate wrong-to-correct,
correct-to-wrong, WER, worst-speaker WER, correct-minus-deranged effect, and
episode consistency. Report calls, audio seconds, tokens, latency, and evidence
characters. Require positive correct-vs-retain improvement, correct-vs-deranged
separation, bounded regressions, and distributed meeting support. Only a pass
admits training-free policy search over retain/dispatch; the semantic audit
alone does not.
