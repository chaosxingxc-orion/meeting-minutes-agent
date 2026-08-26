# E-MATERIAL-LHCP-DEVELOPMENT-FRONTEND reader defect

## Trigger

The frozen flight completed 25/25 Sortformer contacts and emitted 397 slices.
Before invoking the one-shot structural reader, a reference-free aggregate check
noticed that total slice seconds exceeded source seconds. An adjacent-boundary
inspection then found overlapping slices, despite the preregistered zero-overlap
gate.

The prebuilt reader subsequently returned `FRONTEND_TRACE_COMPLETE`: all file,
RTTM, receipt, and slice hashes closed. Inspection of its frozen code showed that
it enforced positive and at-most-120-second slices but omitted the separately
registered adjacent-slice zero-overlap assertion. Therefore its trace verdict is
valid only for artifact integrity and cannot be used as the experiment's passing
decision.

## Fail-closed adjudication

Do not modify the RTTMs, slicer, existing reader, or 397 frozen slices. Add a
separate deterministic audit over the already hashed slice manifest. It may only
compare each adjacent pair within a meeting and report overlap count, duration,
maximum, and affected meeting IDs. It reads no audio, transcript, material, or
model output content.

Any overlap greater than `1e-9` seconds fails the already registered gate and
yields `FRONTEND_SLICE_ZERO_OVERLAP_GATE_FAILED`. This post-flight audit repairs
reader enforcement, not the experimental output. A corrected slicer requires a
new experiment and cannot replace this verdict.
