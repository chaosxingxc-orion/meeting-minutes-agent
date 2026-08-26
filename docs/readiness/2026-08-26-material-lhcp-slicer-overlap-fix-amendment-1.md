# E-MATERIAL-LHCP-SLICER-OVERLAP-FIX amendment 1

## Trigger

The first registered reslice attempt stopped during meeting 24 of 25 with
`SliceOverlapViolation`: slice 11 ended at `1100.079` while slice 12 started at
`1099.851`. No aggregate manifest or verdict was emitted. The 23 completed
meeting directories were preserved at
`D:/speechrl-data/derived/lhcp-asr-development-slicer-overlap-fix/2026-08-26-attempt-1-failed`:
360 files, 1,097,540,314 bytes, inventory SHA-256
`03e3c5f5d1e92116a679459c7f771938fc26143ccf296bad12c3a26d8c759234`.

## Implementation defect

The preregistered policy required an overlap-connected turn component to be one
atomic packing unit. The first implementation detected and size-checked those
components but still fed their member turns individually into the greedy packer.
When the preceding group lacked room for the complete component, the code could
close between two component members. The final post-condition correctly caught
the resulting overlap and stopped the run.

## Admitted repair

Keep the registered policy unchanged and repair only its implementation: iterate
over overlap components, never their member turns, when choosing groups. Add a
component as a whole when it fits; otherwise close the preceding group and start
the complete component in the next group. Preserve the existing single-overlong-
turn exception and fail closed for an over-120-second multi-turn component.

Freeze the corrected slicer hash in a new runtime configuration and write the
second attempt to a distinct `2026-08-26-attempt-2` root. Do not resume, delete,
or reinterpret attempt 1. The source WAVs, RTTMs, parameters, gates, validator,
and all model/reference prohibitions remain unchanged.
