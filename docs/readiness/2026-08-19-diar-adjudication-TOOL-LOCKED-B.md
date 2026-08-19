# Owner adjudication — DIAR tool lock closes as TOOL-LOCKED(B)

Date: 2026-08-19. Authority: owner decision ("按你的建议走", same day), on the
coordinator's recommendation. This record CLOSES G1 lock #3 (tools/run-flow). The one-shot
read record (`docs/readiness/2026-08-18-diar-smoke-verdict.md`, commit `172d899`) stands
unmodified as NO-REGISTERED-VERDICT; this adjudication is the separate, dated decision the
registered clause set could not produce.

## The uncovered cell and the decision

Measured (pooled, no collar, with overlap, NIST component-sum over six dev-18 meetings):
DER(B) = **20.7405**, DER(A) = **23.7341**; |B−A| = 2.9936 > 2.0 fails the two-sided parity
clause — in B's favor. The registered lattice had no exit for (parity fail ∧ DER(B) ≤ 22 <
DER(A)). Grounds for closing the lock as **TOOL-LOCKED(B)**:

1. B clears the registered absolute quality bar for the lock: 20.7405 ≤ 22.0 (margin 1.2595).
2. The parity clause's registered PURPOSE — guarding against quantization/runtime
   DEGRADATION of B relative to the fp32 reference — is satisfied a fortiori: B is BETTER
   than A by 2.9936 points. The two-sided authorship was a registration drafting error
   (should have been one-sided, DER(B) ≤ DER(A) + 2.0), recorded here as such.
3. The mode confound (A = offline geometry, B = DiarStream streaming geometry after the
   flight's diagnosed `--offline` rel-pos-table refusal) is disclosed; the pin below binds
   the streaming geometry explicitly, so what was measured is what deploys.

## The binding

`PinnedToolDiarization` binds to: `nvidia/diar_streaming_sortformer_4spk-v2` (HF revision
`5240a640…`), the q8_0 GGUF (sha256 `0679cfeb…`), NeMo-Speech.cpp commit `4c749a7`
(binary sha256 `1a3e3f4f…`, CUDA build), **DiarStream streaming geometry**, RTTM output.
Reference numbers travel with the in-domain caveat (AMI in the model's training data;
DER licenses tool use, never generalization) and the collar-convention pair
(B: 20.74 nc / 12.42 collar; JER mean 23.00 nc).

## Unlocked by this record

G1 lock status: architecture ✅ / chunking ✅ / prompt form ✅ / **tools-run-flow ✅ (this
record)**. Next: the PRECOMP production pass registration (the packing-change transport
metric measured SATURATED — 117/117 positional changes on every meeting — so the
deployment-vs-ceiling gap is measured DOWNSTREAM on task metrics in G1, not at
transport-bound equality) and the G1 floors registration.
