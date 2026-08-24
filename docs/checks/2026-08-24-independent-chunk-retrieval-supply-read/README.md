# E-CHUNK-RETRIEVAL-LOO-SUPPLY registered read

Decision: **`INDEPENDENT-CHUNK-SUPPLY-INSUFFICIENT`**.

Structural isolation succeeded. Across 1,429 turns, the leave-one-chunk-out policy found
novel candidates on 980 turns and 628 unique forms. No candidate copied an exact current
query term, no current turn contributed its own evidence, and every context stayed within
the 256-character budget.

Relevance failed decisively. Only 57/2,961 candidates occurred in the target reference
interval (1.93% precision), and only 53 turns contained any reference-supported candidate,
below the registered 100-turn gate. No meeting reached the 20-supported-turn requirement.

The posthoc descriptive diagnostic shows that string similarity primarily retrieves
inflectional alternatives such as `thank/thanks`, `question/questions`, and
`customer/customers`, regardless of which form occurs in the audio. It also creates unsafe
semantic confusions such as `million/billion` and `next/net`. This diagnostic does not
change thresholds or the verdict.

The output-only fuzzy retrieval branch is stopped. The result does not prove that all
per-chunk retrieval is impossible; it shows that prior hypotheses plus edit similarity do
not provide independent corrective evidence. No model flight or policy search is admitted.
