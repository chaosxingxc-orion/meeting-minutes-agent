# DIAR-SMOKE — pinned-tool diarization flight record (2026-08-18)

**Flight operations only.** Both required arms flew all six registered dev-18 Mix-Headset
meetings: 12/12 `(arm, meeting)` contacts OK. **Zero frozen-core contact — `llama-server` was
never started.** No DER/JER was computed, the NXT reference was never touched, and no RTTM
content was read beyond structural counts (line counts, distinct speaker labels). Scoring is
the separately gated one-shot read mission (`scripts/diar_smoke_read.py`), which consumes the
run directory named below.

Registration: `docs/readiness/2026-08-18-diar-smoke-preregistration.md` (REGISTERED).
Machinery flown: commit `53bc5e191c56f2125953a7411c9ce9baa64023dd`, clean tree before, during,
and after the flight (`fly-wrapper.log` records the post-flight check).
Acquisition receipt: umbrella `docs/checks/meeting-minutes-agent/2026-08-18-diar-acquisition/`
(umbrella commit `6ca5f50`); asset identity: umbrella `docs/datasets.lock.json` entry
`diar-sortformer-4spk-v2`, HF revision `5240a64075176943f677d30fa2171c780229f341`.

## Tool identity (hash-verified preflight, `preflight-hash-verify.log`)

| item | value |
|---|---|
| Arm A checkpoint | `diar_streaming_sortformer_4spk-v2.nemo`, sha256 `b371afce…3329` — **OK vs lock** |
| Arm A runtime | `~/.venvs/diar` (isolated): nemo_toolkit 3.0.0, torch 2.9.1+cu128; freeze `/home/chao/tmpops/diar-wheels/diar-venv-freeze-2026-08-18.txt`; wrapper `sortformer_diarize_arm_a.py` (archived here), card-default `.diarize()` — no threshold/geometry override |
| Arm B checkpoint | `diar_streaming_sortformer_4spk-v2.q8_0.gguf`, sha256 `0679cfeb…998a` — **OK vs lock** |
| Arm B runtime | `/home/chao/nemo-speech.cpp/build/cuda-diar/bin/nemo-speech` (nemo-speech 1.0.0, commit `4c749a70…ac7d`*, binary sha256 `1a3e3f4f…ca78` — **OK vs receipt**), CUDA0 backend, all 971 GGUF tensors loaded on every contact |

*Full commit: `4c749a700500e077d4732a539eb082bf2208dac7`, re-verified from the checkout at
flight time.

Audio inputs: the six Mix-Headset WAVs. Four hash-verified against the committed pins in
`configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json` (`audio_sha256`): ES2011b,
IS1008b, IS1008d, TS3004b — all OK. **ES2011a and TS3004d had no per-file pin anywhere in
Git**; their computed hashes are first-pinned in `preflight-hash-verify.log`
(ES2011a `130bc421…1c78`, TS3004d `d89950bb…4cdf`) alongside 16 kHz/mono/16-bit header checks
for all six. Total registered audio: 10,941.3 s (3.04 h).

## Preflight

- Full repo pytest: **1119 passed** in 1543.61 s (`preflight-pytest.log`), shared venv
  read-only with `PYTHONPATH` armor, `PYTHONDONTWRITEBYTECODE=1` everywhere.
- `launch_diar_smoke.py --summary-only`: roster/arms/ceilings match the registration exactly
  (`preflight-summary-only.log`); the committed AMI role registry admits all six meetings as
  `asr-eval` (checked again inside the real flight by `assert_registered_meetings_exposable`).
- GPU from Windows: idle P5, 1507 MHz SM, no throttle reasons (`preflight-gpu-windows.log`).

## What flew

Launcher: `scripts/launch_diar_smoke.py --arms A B --resume`, meeting-major order, budget
guard active, per-contact `ToolContactRecord` (tool id/version, checkpoint sha256, full argv,
wall, return code) on every receipt under `receipts/<arm>/`.

| meeting | audio s | A wall s (rc) | A RTTM lines | B wall s (rc) | B RTTM lines |
|---|---|---|---|---|---|
| ES2011a | 1,113.8 | 160.2 (0)* | 462 | 50.0 (0) | 341 |
| ES2011b | 1,581.3 | 33.4 (0) | 607 | 65.2 (0) | 436 |
| IS1008b | 1,768.5 | 30.9 (0) | 424 | 72.3 (0) | 317 |
| IS1008d | 1,480.8 | 30.5 (0) | 511 | 63.2 (0) | 414 |
| TS3004b | 2,246.1 | 33.9 (0) | 919 | 103.1 (0) | 738 |
| TS3004d | 2,750.8 | 37.7 (0) | 1,210 | 114.1 (0) | 1,024 |

*First contact carries CUDA context/warm-up. Every RTTM reports exactly **4 distinct speaker
labels** on every meeting under both arms (structural count only). Label alphabets differ by
emitter convention — Arm A `speaker_0..speaker_3`, Arm B `speaker_1..speaker_4` — a naming
fact for the read mission's speaker mapping, not a quality statement. Line counts equal the
launcher-parsed turn counts (`n_turns`) on all 12 receipts.

## Attempt 1 failure and the diagnosed single retry (Arm B)

The registered Arm B invocation sketch (prereg §2: `--offline --format rttm`) failed on all
six meetings in attempt 1: the tool **loaded the GGUF successfully** (CUDA0, 971 tensors)
and then refused long-form input in full-attention mode —
`diarize_offline: 13924 encoder frames exceeds the rel-pos table (5000 = ~6 min); use
DiarStream for long-form audio`. This is a mode/geometry cap on `--offline`, not a load
failure, so the Arm C contingency was not triggered. One retry (the registered maximum) was
flown with the single diagnosed change: **drop `--offline`**, using the tool's default
DiarStream streaming mode — the documented long-form path and the v2 model's native mode.
All six contacts then succeeded. Everything about attempt 1 is preserved: its six error
receipts (full stderr), flight summary, launcher/wrapper/GPU logs, and the exact failing
`arm-config.attempt1-offline.json`, under `attempt-1-offline-mode/`. The read mission and
any later pin freeze must treat "Arm B geometry = streaming (default), not `--offline`" as
a recorded deviation from the prereg §2 command sketch (tool, checkpoint, RTTM output, and
every hash pin unchanged).

## Budget vs the registered ceilings

| ceiling | registered | used | headroom |
|---|---|---|---|
| wall | ≤ 2.0 h | 833.4 s launcher-metered (365.5 attempt 1 + 467.9 attempt 2); 887 s wrapper wall including sampler/setup | ≥ 1.75 h |
| GPU-hours | ≤ 1.0 | 0.082 GPU-h utilisation-integrated (55.8 s attempt 1 + 239.7 s attempt 2, 30 s sampling); conservative upper bound 0.25 GPU-h (= total wrapper wall) | ≥ 0.75 |

## GPU health

30 s sampler, both attempts (`gpu-health.log`, `attempt-1-offline-mode/gpu-health.log`).
Under load: utilization up to 96%, memory ≤ 1,072 MiB, peak 52 °C, the known benign 232 MHz
reading with throttle word 0x4 — throughput judgment applied: Arm B ran at 4.1–4.6% of real
time per meeting and Arm A at ~2% (post-warm-up), so no clock override was needed. GPU
returned to idle (P8/180 MHz, 0 MiB) after each attempt.

## Handoff to the read mission

Run directory (raw artefacts — deliberately NOT in Git):
`$SPEECHRL_DATA_DIR/derived/meeting-minutes/diar-smoke/runs/2026-08-18-diar-smoke/`
(`rttm/{A,B}/<meeting>.rttm`, `receipts/{A,B}/`, `flight-summary.json`,
`attempt-1-offline-mode/`, tooling under `../../tooling/`). `MANIFEST.sha256` here
fingerprints every run-dir artefact — all 12 RTTMs, all receipts, both flight summaries —
with paths relative to the run directory; the RTTM bytes themselves stay on E:.

## Boundary statement

Zero frozen-core contact (no `llama-server` process at any point). The diarizers saw audio
bytes only — no NXT annotation, no gold label, no reference RTTM exists anywhere in tool
input or in this record. No DER, JER, parity, or verdict computation ran; the prereg §5
verdicts remain entirely undecided. The shared `~/.venvs/speechrl` was used read-only; no
package was installed anywhere. The SAEA study repository was not touched. Paid spend: 0.

## Files here

`README.md` · `MANIFEST.sha256` (run-dir artefact hashes) · `arm-config.json` (flown, attempt
2) · `arm-config.attempt1-offline.json` · `sortformer_diarize_arm_a.py` (Arm A wrapper
flown) · `script-preflight.sh` / `script-fly.sh` · `preflight-hash-verify.log` ·
`preflight-pytest.log` · `preflight-summary-only.log` · `preflight-gpu-windows.log` ·
`fly-wrapper.log` / `launcher.log` / `gpu-health.log` / `structural-stats.log` (attempt 2)
· `flight-summary.json` · `receipts/{A,B}/*-receipt.json` (12) ·
`attempt-1-offline-mode/` (six error receipts, summary, logs, failing arm-config).
