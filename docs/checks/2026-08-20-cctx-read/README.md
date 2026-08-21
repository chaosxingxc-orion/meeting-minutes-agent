# C-CTX frozen read

This directory is the one-shot scoring read of the 160 completed C-CTX responses.

- Registration: `docs/readiness/2026-08-20-cctx-preregistration.md`
- Human-readable verdict: `docs/readiness/2026-08-20-cctx-verdict.md`
- Machine verdict: `verdict.json`
- Compact report: `report.txt`
- Decision: `CONTEXT-SENSITIVE-BUT-UNCONTROLLED`

The correct entity arm improved NE-WER by 4.93 percentage points versus the bare arm,
with a paired bootstrap 95% interval of [-8.37, -1.78] points. The registered materiality
threshold was 5.00 points, so the near miss was not promoted after the read.
