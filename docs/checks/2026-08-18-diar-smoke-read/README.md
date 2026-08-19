# DIAR-SMOKE — registered one-shot scoring read (2026-08-19)

The single registered read of the flight in `../2026-08-18-diar-smoke-flight/` (run dir
`$SPEECHRL_DATA_DIR/derived/meeting-minutes/diar-smoke/runs/2026-08-18-diar-smoke/`,
verified 33/33 against the flight `MANIFEST.sha256` before the first attempt; never
modified). Registration: `docs/readiness/2026-08-18-diar-smoke-preregistration.md`.
Verdict document (the decision record, clause margins, all tables):
`docs/readiness/2026-08-18-diar-smoke-verdict.md`.

Execution: `scripts/diar_smoke_read.py` at study commit `5a762cb`, WSL Ubuntu-24.04,
`~/.venvs/speechrl` (read-only, `PYTHONPATH` armor, `PYTHONDONTWRITEBYTECODE=1`), exactly
one exit-0 run (2026-08-19T08:29:41Z) writing `verdict.json` + `report.txt` once. NXT gold
turns entered SCORING SIDE ONLY. Zero model/tool contact; the six meeting WAVs were read
for header duration + energy pause transitions (signal-derived slicer inputs) only.

Headline: **no prereg §5 clause fires** — pooled no-collar DER(A) 23.7341 / DER(B) 20.7405
points; parity gap 2.9936 > 2.0; the cell (parity fail, DER(B) ≤ 22 < DER(A) ≤ 30) is
uncovered by the registered clause set. The `status` field inside `verdict.json`
(`TOOL-LOCKED(B)`) is VOID — the shipped evaluator was fed DER fractions against
percentage-point thresholds (verdict doc §0.1); `verdict.json` is kept byte-exact as the
read wrote it, defect and all. G1 lock #3 stays open pending owner adjudication.

## Files

- `verdict.json` — the read's machine record (per-meeting DER/JER both conventions,
  pooled components, displacement distributions, packing results, speaker mappings,
  audio-derived slicer inputs, the as-run clause block noted above).
- `report.txt` — the read's own text summary (carries the same void as-run status).
- `attempt-1-transportbound-crash.log` / `attempt-2-transportbound-crash.log` — the two
  pre-read harness crashes (exit 1, zero metrics produced), their diagnosis chain, and the
  fixes (`ec829d4` audio-input wiring; `5a762cb` slicer interior gap-tiling room cap).
- `MANIFEST.sha256` — fingerprints of the four artifact files above.
