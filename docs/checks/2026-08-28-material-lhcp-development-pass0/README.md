# E-MATERIAL-LHCP-DEVELOPMENT-PASS0 evidence

The zero-model readiness audit passed all 21 frozen checks and returned
`LHCP_DEVELOPMENT_PASS0_READY_AWAITING_AUTHORIZATION`.

- Runtime SHA-256: `bf64f560c41f59ce7746930efaee1ce8430478674d60eb06b189b2e1e235194c`
- Slice-manifest SHA-256: `1224f0951c6b255523197974368c54e73fd27c4a9b328bf5c909eaf226d695ce`
- Queue: 25 meetings, 396 slices
- Manifest audio upper bound: 37,547.2558125 seconds
- Actual WAV frames: 37,546.6638125 seconds
- Maximum output budget: 202,752 tokens
- Transport: one slot, zero retries, 300-second timeout
- External trace requirement: 2,339,136,911 bytes minimum
- D free space at audit: 2,763,922,886,656 bytes
- E-drive dependency: none

The audit rehashed every WAV plus the model, mmproj, and server binary. At that
checkpoint it made zero model contacts, read no reference or confirmation data,
and confirmed that the reserved external flight root did not yet exist. Model
execution remained blocked until the later explicit authorization recorded
below.

Offline verification completed with 13/13 focused Pass0 tests and the full
repository suite at 1,612 passed and 25 skipped.

See [`readiness.json`](readiness.json) for the machine-readable checks.

## Authorized flight result

EuphoriaYan authorized the unique 396-call flight after readiness. The run
completed all 25 meetings and the prebuilt reference-blind reader returned
`PASS0_TRACE_COMPLETE`: 396/396 ordered responses, zero empty outputs, zero
retries, and exact request/response/runtime/receipt bindings. Reference,
material, and confirmation access remained `NONE`.

- Wall time: 15,379.128 seconds (4 h 16 m 19 s)
- Latency: 22.077-second median, 120.004-second p95, 201.425-second maximum
- Usage: 527,747 prompt, 113,459 completion, 641,206 total tokens
- External trace: 1,604,584,502 bytes
- Index SHA-256: `037c8eaf5284c4dffa88dad1a58438e0697ca963117870d355a46881e21228f8`
- Receipt SHA-256: `1c995d83f7455fe27ca5366241d9629e4b660d6dec00f82d52d19c11b45cd103`

The server used the frozen binary/model/mmproj with
`-c 49152 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0` on
`127.0.0.1:8080`; the complete argv is in `flight-summary.json`. The server was
stopped after the structural read.

The response metadata contains 395 `stop` finishes and one `length` finish at
position 301 (`1109611c537`, slice 13). This does not invalidate trace
provenance, but that slice must be treated as potentially truncated in any later
quality read. No transcript quality or speaker-capability claim follows from
this structural verdict.

See [`structural-read.json`](structural-read.json) and
[`flight-summary.json`](flight-summary.json).
