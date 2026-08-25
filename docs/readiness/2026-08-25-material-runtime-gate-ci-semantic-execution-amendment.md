# E-MATERIAL-RUNTIME-GATE-CI semantic execution amendment

Date: 2026-08-25. Status: **REGISTERED BEFORE EMBEDDING CONTACT**. The owner explicitly
authorized the frozen embedding run, development threshold fit, and sole confirmation
read after Pass-0 completed 1,639/1,639 calls.

The executable configuration is
`configs/probes/material_runtime_gate_ci/2026-08-25-semantic-gate.json`, SHA-256
`a6d3f9aac019e07e2a53535f71a193b67712e065a349371dacdfaa20eb716fa4`. The runner
SHA-256 is `9357c6c7fc0b3f3c8a63c4789cbb9f451853e0d29a61474cf1bd572704af5b72`.
It binds all six Pass-0 response hashes, the material candidate/page snapshots, runtime
manifest, Qwen3-Embedding-0.6B Q8_0 model, and current llama-server binary.

## Frozen runtime construction

Each meeting receives eight deterministically salted material candidates. A key contains
the candidate surface and a whitespace-normalized source excerpt of at most 240 characters
on either side. Each query contains the current Pass-0 text, predicted Sortformer speaker
ID, and at most eight topic keywords. Keywords use only the previous 20 turns in the same
meeting, require occurrence in at least two earlier turns, and sort by descending evidence
then lexical order. No reference, future turn, material match, or outcome defines query
eligibility. A query requires at least three runtime content tokens.

The zero-embedding preflight froze 622 development queries plus 24 keys (646 embeddings,
at most 41 HTTP calls) and 850 confirmation queries plus 24 keys (874 embeddings, at most
56 calls). Total authorization is 1,520 embeddings and 97 batched calls. The wrong-meeting
control is an equal-width ascending-ID rotation within each split and is unavailable to
the deployment selector.

## One-way decision protocol

Development evaluates the fixed gap grid `[0, .01, .02, .03, .04, .05]` and freezes the
lowest threshold reaching 70% attribution precision, 20% coverage, and nonzero dispatch
in all three meetings. If none passes, confirmation is not contacted. If development
passes, confirmation runs exactly once with the frozen threshold. It requires 70%
precision, 20% coverage, at least two meetings at or above 60% precision, and median
correct-minus-deranged cosine at least .01.

No threshold may be changed after development and no confirmation retry or second read is
authorized. A pass remains `CONSTRUCTION_ISOLATED_SIGNAL_PRESENT`, not independent
confirmation, WER benefit, correction controllability, or permission for policy search.
