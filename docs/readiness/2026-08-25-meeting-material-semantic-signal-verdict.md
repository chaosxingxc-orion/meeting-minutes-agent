# E-MEETING-MATERIAL-SEMANTIC-SIGNAL verdict

## Decision

`SEMANTIC-RETRIEVAL-SIGNAL-PRESENT` — admit design work for an independent
retain/dispatch Omni capability experiment. Do not yet admit GRPO, GEPA, EM,
multimodal policy search, or a deployment claim.

The semantic construction dispatches on 393 of 751 eligible turns. Correct
material wins 306 times, for 77.86% attribution precision. It improves on the
frozen lexical result by 15.997 percentage points and clears the per-meeting
floor in all three meetings. The result is distributed rather than driven only
by Galp.

This is the first current material-routing construction to pass both a wrong-
meeting control and a cross-meeting distribution gate. It shows that the useful
SAEA transfer is encode-only semantic K ranking plus selective dispatch, not
broadcast context, character similarity, or positive retrieval score alone.

## Next boundary

The next experiment must use independent, reference-unread meetings. It freezes
Pass0 before building a semantic retrieval manifest, then compares:

1. `R0-retain`: keep the direct Pass0 transcript;
2. `R1-correct-dispatch`: re-transcribe the identical audio with the selected
   official-material value as explicitly untrusted spelling evidence;
3. `R2-deranged-dispatch`: re-transcribe with an equal-dose wrong-meeting value.

Primary evidence must include WER, candidate wrong-to-correct, correct-to-wrong,
speaker tails, correct-vs-deranged separation, calls, tokens, and latency. The
deployment selector must use only within-meeting information; the deranged pool
is an experimental control, not a runtime dependency. A model flight remains
blocked until this independent manifest, prompt, sample, budget, and gates are
separately preregistered.

- [Runtime receipt](../checks/2026-08-25-qwen3-embedding-runtime/README.md)
- [Preregistration](2026-08-25-meeting-material-semantic-signal-preregistration.md)
- [Structural evidence](../checks/2026-08-25-meeting-material-semantic-signal-read/README.md)
