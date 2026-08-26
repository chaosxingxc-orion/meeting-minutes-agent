# E-MATERIAL-LHCP-DEVELOPMENT-FRONTEND verdict

## Decision

`FRONTEND_SLICE_ZERO_OVERLAP_GATE_FAILED`

The authorized fixed-front-end flight completed all 25 audio-only Sortformer
contacts in frozen manifest order. All 25 contacts produced non-empty RTTMs and
the frozen run produced 397 hashed 16 kHz mono PCM16 slices. There were no
retries, meeting replacements, parameter changes, reference reads, confirmation
reads, Pass0 calls, embedding calls, or Omni calls.

This is not a passing front-end supply result. A separate deterministic audit of
the frozen slice manifest found 15 adjacent-slice overlaps in 10 of 25 meetings,
totalling 35.900 seconds; the maximum overlap was 14.948 seconds. The registered
gate required zero overlap, so Pass0 remains blocked.

## Evidence interpretation

The frozen structural reader returned `FRONTEND_TRACE_COMPLETE`: 25 conversions,
25 contact receipts, 25 RTTMs, 397 slice files, and all recorded hashes closed.
That verdict describes artifact integrity only. The prebuilt reader omitted the
already registered adjacent-slice assertion; the defect and fail-closed handling
are recorded separately. The post-flight overlap audit reads only slice bounds
and enforces the original gate without modifying any output.

The observed mechanism is deterministic. Sortformer can emit overlapping
speaker turns. The current turn-aware slicer sorts turns by start time, groups
consecutive turns, then uses one group's final turn end and the next group's first
turn start as adjacent slice bounds. When a speaker overlap crosses the group
boundary, those bounds overlap. For example, meeting `856696c62` has a
speaker-4 turn `[1474.251, 1493.199)` crossing the next group's speaker-1 turn
start at `1478.251`, creating the maximum 14.948-second duplicate interval.

## Frozen evidence

- configuration SHA-256: `4841b0f94f2e14e054c737b7286980a2900a88577d2ab55a39ad0f4171a3f055`
- conversion manifest SHA-256: `7e654c2229839c1da12ae9ccc32d249c87197aacf44b343f2b7695759fdae128`
- flight summary SHA-256: `9d8d5e1faed8abdac72c75f5e2e33fa256f685ba0f2599b59fa5b53d086b30fa`
- slice manifest SHA-256: `e77d75cdb40c6db6cb5c7c2cada6bbc85ee373d94cec9f8af5d8c99cfe0df917`
- trace validation: `docs/checks/2026-08-26-material-lhcp-supply/development-frontend-validation.json`
- zero-overlap audit: `docs/checks/2026-08-26-material-lhcp-supply/development-frontend-overlap-audit.json`

## Next boundary

Do not rerun Sortformer and do not reinterpret the 397 slices as Pass0-ready.
A slicer correction must be a separately registered engineering experiment with
overlapping-RTTM fixtures, an explicit boundary policy, and a prebuilt
zero-overlap validator. It may reuse these frozen RTTMs only after that scope is
registered; any corrected slice manifest is a new artifact and cannot replace
this failed verdict.
