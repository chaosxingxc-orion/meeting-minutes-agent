# E-MATERIAL-NEW-SURFACE-RUNTIME-GATE development receipt

The zero-model snapshot admitted all 20 development calls: 475 PDF pages yielded
3,672 deterministic candidates, of which 160 (eight per call) were frozen. The
embedding flight then completed 13/13 batches for 160 keys and 40 Pass0 queries.
It produced 1024-dimensional float32 vectors and a prospective 40-row trace.

The independent validator returned `TRACE_COMPLETE` with zero errors. It checked
all Pass0 request/response bindings, candidate snapshot, row hashes, and 120 query,
correct-key, and deranged-key vector sidecars.

The prebuilt development reader returned `DEVELOPMENT_SIGNAL_PRESENT`:

- frozen threshold: `0.00` (lowest passing threshold)
- correct-call attribution: 30/40, precision 75.00%
- dispatch coverage: 40/40, 100.00%
- represented calls: 20/20
- median correct-minus-deranged cosine: 0.0760913

All four registered gates pass. At threshold 0.02, descriptive precision is
81.48% at 67.50% coverage, but that threshold is not selected because the frozen
rule requires the lowest passing value. Therefore this result supports semantic
material attribution, not a useful abstention boundary: threshold 0.00 dispatches
everything.

- Runtime SHA-256: `64873a5332b8036fe05471441675eb15867f3d6cf6eb1330035f926e5e3b38fe`
- External trace SHA-256: `e342cf7c22005c67ca013fbdd2950bc622597204e42d3d3976a202265e0a75fb`
- External flight receipt SHA-256: `247b26b7f20d971e3ecbb78953fbd734126d22540b57fa4ff007861c4995a5a5`
- [Trace validation](trace-validation.json)
- [Development read](development-read.json)

Reference reads, confirmation access, and Omni correction calls were all zero.
No WER or transcription-improvement claim is made. Confirmation requires a new
frozen snapshot/runtime/reader and explicit release of the sealed split.

