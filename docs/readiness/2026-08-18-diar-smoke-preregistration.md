# DIAR-SMOKE — pinned-tool diarization smoke — REGISTERED

Date: 2026-08-18. Status: **REGISTERED** — owner confirmed the v2 pin and authorized the
download the same day ("diar v2 锁定，并且可以下载"); flight waits only for the
umbrella-lock acquisition step (below) and the smoke machinery. Parent:
the selection ticket `docs/plans/2026-08-18-diarization-tool-selection.md` (owner ruling:
NVIDIA-first) and the DiarizationBackend seam (commit `81db918`). This smoke closes the
third G1 lock (tools/run-flow).

## 1. Pin under test

Primary: **`nvidia/diar_streaming_sortformer_4spk-v2`** (ungated, CC-BY-4.0; revision and
per-file hashes exactly as the selection ticket records them — the ticket is the pin source,
not this file). Same-family alternate (contingent): `diar_sortformer_4spk-v1`. Speaker bound
4 fits AMI scenario meetings exactly; ICSI stays out of scope for the primary.

## 2. Arms

- **Arm A (reference)**: NeMo fp32 inference in an isolated venv `~/.venvs/diar`
  (nemo-toolkit 3.0.0, plain install — never the `cu12`/`cu13` extras, which would pull a
  wrong-CUDA torch; documented fallback pin 2.7.0 if 3.0.0 fails checkpoint load). The
  shared `~/.venvs/speechrl` is never touched.
- **Arm B (deployment candidate)**: NeMo-Speech.cpp (CUDA build, pinned commit + binary
  sha256) consuming the official q8_0 GGUF, `--offline --format rttm`.
- **Arm C (contingent, flies only if A and B both fail load or parity)**: v1 via Arm A's
  venv.

Zero frozen-core contact anywhere in this smoke: the Qwen3-Omni server is never started.

## 3. Surface

Six dev-18 Mix-Headset meetings from the usable-discovery pool (four shared with the
oracle-smoke set per the selection ticket): ES2011a, ES2011b, IS1008b, IS1008d, TS3004b,
TS3004d. NXT gold turns are the EVAL REFERENCE ONLY (scoring side); no annotation of any
kind enters tool input — the tool sees audio bytes alone.

## 4. Metrics

Per arm, per meeting, plus pooled: DER and JER vs the NXT reference under BOTH conventions
(0.25 s collar ignoring overlap, AND no collar with overlap — the latter is the published
pyannote-3.1 AMI anchor, 18.8%); speaker-count accuracy; turn-boundary quality for the
transport packer — boundary-displacement distribution vs oracle turns and the fraction of
90 s transport slices whose packing CHANGES when oracle turns are replaced by tool turns
(the number G1's deployment-vs-ceiling gap will ride on); wall time and GPU seconds per
meeting.

## 5. Mechanical verdicts

1. **Parity gate (B vs A)**: |pooled DER(B) − DER(A)| ≤ 2.0 absolute (no-collar convention)
   → the GGUF path is quantization-safe.
2. **TOOL-LOCKED(B)**: parity gate passes AND pooled DER(B) ≤ 22.0 (no collar, with
   overlap) → G1's `PinnedToolDiarization` binds to Arm B (deployment story: 147 MB GGUF,
   no Python ML stack). Preferred outcome.
3. **TOOL-LOCKED(A)**: parity fails but DER(A) ≤ 22.0 → bind to Arm A; the GGUF parity
   failure is recorded and the deployment-footprint claim is dropped.
4. **TOOL-USABLE-WITH-CAVEAT**: best arm DER in (22.0, 30.0] → bind to the best arm, and
   every G1 deployment-tier number must carry the measured DER as an explicit caveat.
5. **FALLBACK-NEEDED**: best arm DER > 30.0 or both arms fail to load → register a pyannote
   3.1 smoke (gated-token friction accepted) before G1.
   In-domain caveat carried in ALL outcomes: AMI appears in the NVIDIA models' training
   data (partition unstated by the card); the smoke DER is therefore an in-domain number
   and is cited as such — it licenses tool USE, never a generalization claim.

## 6. Acquisition prerequisite (before any download)

The model files (v2 `.nemo` + GGUF, ~640 MB) and the NeMo-Speech.cpp pinned build enter the
umbrella `docs/datasets.lock.json` first (program acquisition authority), then land under
`$SPEECHRL_DATA_DIR` via the standard fetch path; nothing is downloaded ad hoc.

## 7. Cost ceilings and discipline

≤1.0 GPU-h total (six ~35-min meetings × three-at-most arms at a few percent of real time
+ margin); ≤2 h wall. One-shot read via a pinned scoring CLI (extends the DiarizationBackend
tests' fixtures; coordinator-reviewed before the read); receipts + archive under
`docs/checks/2026-08-18-diar-smoke-{flight,read}/` mirroring the P-ATTR pair; per-contact
logging (tool version, checkpoint hash, args, wall/GPU) as the frozen-tool rule requires;
AMI CC BY 4.0 carried.
