# E4-XDOMAIN-SUPPLY-AUDIT-v2 schema amendment

Date: 2026-08-21. Status: **FROZEN BEFORE DISCOVERY AGGREGATE READ**.

The post-registration schema check inspected only headers and the first timestamp-bearing rows; it did not compute entity, carry, class, speaker, or reserve statistics. It found that `transcripts/nlp_references/*.nlp` has blank `ts` fields in actual files, despite the upstream README describing timestamps. Therefore the registered 90-second pseudo-slice rule cannot be implemented from that layer.

The audit input changes to the same release's `transcripts/force_aligned_nlp_references/*.aligned.nlp`. This layer preserves the upstream speaker/entity fields and supplies aligned timestamps. Rows or reconstructed entity mentions without a valid timestamp are excluded conservatively, with only an aggregate exclusion count reported. The source commit, 80/45 deterministic split, entity-class policy, carry definition, thresholds, reserve prohibition, and decision rule do not change.

This amendment is a fail-closed schema correction before any aggregate read, not a response to observed supply. The implementation manifest must lock the 125 force-aligned files and the CLI must parse discovery files only.
