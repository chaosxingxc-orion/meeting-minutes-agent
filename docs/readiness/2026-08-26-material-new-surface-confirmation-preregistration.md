# E-MATERIAL-NEW-SURFACE-CONFIRMATION preregistration

## Authorization and question

EuphoriaYan explicitly released the sealed confirmation split on 2026-08-26.
The question is whether the development material-attribution signal survives on
40 untouched confirmation items under the frozen construction and threshold.
This release covers confirmation Pass0, PDF snapshot construction, and encode-only
embedding only. Reference transcripts and Omni correction remain sealed.

## Sequential execution

Stage A runs `transcribe-only-v1` on the two authentic single-speaker clips for
each confirmation item: 80 calls, 1,193.999875 audio seconds, at most 40,960
generated tokens, `temperature=0`, `seed=0`, one slot, and zero retries. Exact
wire requests/responses and an append-only index are mandatory. Empty output is
preserved as data; no clip is replaced.

Stage B parses only the 40 bound confirmation PDFs with the same fixed candidate
extractor, salt, first-occurrence rule, 240-character radius, and width eight used
in development. Any call with fewer than eight candidates stops the experiment.

Stage C embeds 320 keys and 80 Pass0 queries with the same frozen
`Qwen3-Embedding-0.6B-Q8_0.gguf`, float32 L2 normalization, batch size 16, and at
most 25 HTTP calls. Query speaker/history construction and the ascending-call-ID
cyclic derangement are unchanged. It writes exact embedding wire artifacts, 80
append-only trace rows, and 240 query/correct/deranged vector sidecars.

## Frozen confirmation read

The deployment selector uses the development-frozen threshold `0.00`, bound by
the development read SHA-256
`161c5187b7054c74b738de06b3aeac2c2ad80db2bb878c82298dbdb00dd422f6`.
No threshold grid is fitted or selected on confirmation. The confirmation verdict
is `CONFIRMATION_SIGNAL_PRESENT` only if all gates pass:

1. correct-call attribution precision is at least 70%;
2. dispatch coverage is at least 20%;
3. at least 24/40 calls have per-call attribution precision at least 50%; and
4. median correct-minus-deranged cosine is at least 0.01.

The wrong-call score is evaluation-only. The prebuilt reader runs once after a
zero-error complete-trace validation. Any hash/count/vector drift, failed request,
malformed response, non-prefix trace, or prerequisite failure stops without
repairing or substituting data. Passing confirms semantic attribution only; it
does not establish WER gain, a useful abstention policy, or agent-loop stability.

