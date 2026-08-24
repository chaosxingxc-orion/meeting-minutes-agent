# E-CHUNK-RETRIEVAL registered read

Decision: **`CHUNK-RETRIEVAL-NOT-REACHED`**.

All structural gates passed: 7,145/7,145 expected rows were present, every context hash
replayed, every context stayed within budget, and all 1,056 eligible R2/R3 controls were
distinct with equal cardinality. The loop also converged: the R2-round2/R2 edit delta was
27.99% of the R2/R0 delta, below the registered 80% limit.

Convergence did not imply useful stability. R2 consistency was 68.58% versus 75.00% for
bare (-6.42 points), improved in 0/4 meetings versus bare, and beat deranged retrieval in
only 1/4 meetings. Overall WER was noninferior (22.00% versus 22.04%), but worst-speaker
WER increased by 4.17 points and failed its 2-point guardrail. Unsupported candidate
activation was 54.98%, far above the 2% ceiling. Language drift was unchanged.

The registered result rejects same-chunk, prior-output spelling retrieval as the stable
layer for this agent loop. It tends to reproduce model-proposed forms and reaches a
fixed state without improving consistency or speaker-routing value. GRPO, GEPA, EM-style
policy search, and multimodal injection remain blocked. A next design must first obtain
independent corrective evidence; it may not tune thresholds on this read.
