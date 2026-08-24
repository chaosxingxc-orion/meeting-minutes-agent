# E-CHUNK-RETRIEVAL-SUPPLY v2 read

Decision: **`SPARSE-CHUNK-RETRIEVAL-SUPPLY-INSUFFICIENT`**.

Excluding correct-speaker candidates made the routed and deranged lists distinct on
1,056/1,056 eligible turns. However, the fixed cyclic wrong-speaker pool could supply
an equal number of non-overlapping candidates on only 970/1,056 turns. The fixed
cardinality gate therefore failed.

No threshold was changed and no model was contacted. v3 keeps a single wrong speaker
per turn but selects the first other speaker, in deterministic cyclic order, that can
supply the matched candidate count.
