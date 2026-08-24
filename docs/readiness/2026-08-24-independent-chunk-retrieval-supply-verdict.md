# E-CHUNK-RETRIEVAL-LOO-SUPPLY verdict

The registered zero-model read returned `INDEPENDENT-CHUNK-SUPPLY-INSUFFICIENT`.
Coverage, diversity, isolation, and prompt-budget gates passed, but reference relevance
failed: candidate precision was 1.93%, only 53 turns had a supported candidate, and zero
meetings reached the registered 20-turn supported-supply floor.

This rejects output-only lexical fuzzy matching as the next stable per-chunk loop. Raising
the similarity threshold or selecting successful pairs from this read is forbidden
posthoc tuning. A future branch needs an independent evidence source with its own provenance
and precision audit, such as legal meeting metadata or an externally supplied glossary.
GRPO, GEPA, EM updates, multimodal injection, and a new model flight remain blocked.

See the [registered read](../checks/2026-08-24-independent-chunk-retrieval-supply-read/README.md).
