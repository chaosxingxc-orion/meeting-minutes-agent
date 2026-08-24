# E-CHUNK-RETRIEVAL-SUPPLY v3 read

Decision: **`SPARSE-CHUNK-RETRIEVAL-SUPPLY-READY`**.

The output-only audit found 1,056/1,429 eligible turns across all four meetings.
Correct-speaker and deranged retrievals were distinct on 1,056/1,056 eligible turns,
and every deranged list matched the correct list's cardinality. Every rendered context
stayed within the 256-character budget.

The deranged arm uses one other speaker per turn. Speakers are considered in fixed
cyclic lexical order, and the first with enough non-overlapping candidates is used.
This audit used only prior-pass outputs. It establishes experimental supply and control
separation, not ASR correctness, stability, or utility.
