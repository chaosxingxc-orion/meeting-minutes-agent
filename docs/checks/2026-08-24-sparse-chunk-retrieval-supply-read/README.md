# E-CHUNK-RETRIEVAL-SUPPLY v1 read

Decision: **`SPARSE-CHUNK-RETRIEVAL-SUPPLY-INSUFFICIENT`**.

The output-only audit found 1,056/1,429 turns with at least one sparse same-speaker
candidate, spanning all four meetings. Every rendered context stayed below 256
characters. Correct-speaker and deranged lists differed on 932/1,056 eligible turns
(88.26%), below the fixed 90% control-separation gate.

The failure is structural: common meeting terms can occur in both speaker pools, so the
deranged arm sometimes receives the same list as the correct arm. The threshold will not
be lowered. A v2 control must explicitly exclude correct-speaker candidates from the
deranged pool and separately require equal list cardinality. No model contact is admitted
by this result.
