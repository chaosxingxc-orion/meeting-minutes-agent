# E-MATERIAL-NEW-SURFACE-ADMISSION preregistration

## Question

Can a new, reference-unread surface supply enough independently frozen speech
chunks with exact references and same-call official material for the next
material-conditioned runtime gate?

## Candidate and evidence boundary

The candidate joins EarningsCallVoice Core-100 to FinCall-Surprise by `call_id`.
Core-100 provides authentic prepared-remark and answer clips, exact transcripts,
same-speaker pairing, hashes, and nine human source-quality gates. FinCall-Surprise
provides the corresponding full call identity and presentation slides. This is a
short-chunk capability surface, not a full-meeting agent-loop benchmark.

`ECV-0001` is excluded before selection because its reference and answer text were
visible in the public dataset-card preview during discovery. All other reference
and answer text fields remain sealed until a separately frozen reader is run.

## Frozen admission and split

An item passes only when both authentic audio roles exist and hash correctly, all
nine human gates pass, the speakers match within the item, the call ID is unique,
and a same-call slide artifact can be acquired and hashed. At least 60 non-exposed
items must pass. Sort admitted item IDs by
`sha256("material-new-surface-2026-08-26-v1:" + item_id)`; assign the first 20 to
development, the next 40 to confirmation, and keep all others as untouched reserve.

Discovery may read identifiers, durations, hashes, license, provenance, and quality
flags only. It must not print, summarize, tokenize, embed, or otherwise inspect
`reference_text` or `answer_text`.

## Prospective complete trace

Before any aggregate gate read, write one append-only JSONL row per audio chunk
against the frozen schema. Preserve raw Pass0 requests and responses, transcript
text, speaker/context inputs, query text, every candidate and score, top-1/top-2,
selector gap and decision, selected correct and deranged values, and artifact hashes.
Persist exact query/key vectors in immutable sidecars and bind them from the row.
Raw trace stays outside Git; the repository receives only its schema, manifest,
hashes, and a validation receipt.

Any missing field, duplicate row identity, score/decision inconsistency, or missing
sidecar fails closed. This registration authorizes only source admission and cohort
freezing. Pass0, embedding, reference reading, and Omni calls require later frozen
runtimes and explicit authorization.
