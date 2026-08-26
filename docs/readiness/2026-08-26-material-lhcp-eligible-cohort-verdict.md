# E-MATERIAL-LHCP-ELIGIBLE-COHORT verdict

## Decision

`LHCP_70_TALK_ELIGIBLE_COHORT_FROZEN`

The prospectively registered material-compatibility filter froze 70 LHCP-ASR
talks: 25 development talks and 45 one-shot confirmation talks. The development
cohort contains 14 `dev_2020` and 11 `dev_2022` talks. The confirmation cohort
contains 13 `test_2020` and 32 `test_2022` talks.

The exact excluded set is `856696c36.wav` and `856696c52.wav`. Both were excluded
solely because their official PDFs failed the previously frozen parser during the
zero-model supply audit. No OCR, fallback parser, meeting replacement, reference
transcript, model output, or outcome metric contributed to eligibility.

The frozen cohort manifest has SHA-256
`b614e4d9ba63e94a988166d62e9d5e7a2bddc1a31ce7528753f47ebbd4e13733`.
Its machine verdict has SHA-256
`2566041e7459e6b0b1e4a9763a6b9fc95a3ce98ea35cc055a51340fc758299b9`.
Independent offline readback returned `TRACE_COMPLETE` with no errors.

This decision does not revise the earlier
`LHCP_ZERO_MODEL_MATERIAL_SUPPLY_INSUFFICIENT` result under the original 72/72
gate. Future evidence from this cohort applies only to the 70 material-compatible
talks and must not be presented as full-release coverage. The freeze itself
authorizes no Pass0, embedding, Omni, audio processing, or reference access. Any
model flight requires a separate prospective registration, frozen runtime and
reader, and explicit authorization.
