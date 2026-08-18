# Diarization tool selection (ticket)

Date: 2026-08-18. Status: selection ticket, resolves the open decision recorded in
`docs/plans/2026-08-18-agent-backbone-and-layout.md` SS5.2 and named by the honest stub
`PinnedToolDiarization` in `src/meeting_minutes_agent/chunking/diarization.py`. Scope: verify the
owner-ruled primary, document one fallback, and plan (not execute) install + smoke. No installs,
downloads, or model contacts were performed for this ticket; all facts below come from public
web sources cited inline and from repository files at HEAD.

## 1. Owner ruling and requirements recap

**Owner ruling (2026-08-18, binding): NVIDIA-first.** The primary candidate is NVIDIA's
Sortformer diarizer (`nvidia/diar_sortformer_4spk-v1`, or a newer NVIDIA successor if one
exists). This ticket verifies the primary, documents exactly one fallback
(pyannote.audio 3.x `speaker-diarization-3.1`), and produces the install and smoke plan.
No exhaustive multi-candidate matrix; the SS5.2 three-way evaluation
(pyannote vs NeMo vs wespeaker) is superseded by this ruling.

Requirements the selected tool must satisfy (from SS5.2 and the chunking seam):

- **Offline, WSL2 Ubuntu-24.04, Python 3.12**; no paid API; large bytes under
  `SPEECHRL_DATA_DIR`, never in Git.
- **Pinnable frozen tool**: exact HF revision + checkpoint hash + package versions freezable;
  a frozen, pinned, logged TOOL-level pre-pass — answer authority stays with the frozen core;
  the tool only segments.
- **Speaker-labelled turns with timestamps**, consumable as `TurnSpan` rows by
  `build_turn_aware_slice_plan` for 90 s turn-aware transport packing
  (`TRANSPORT_SLICE_TARGET_S = 90.0`, min 60 / max 120 / snap 3 s,
  `src/meeting_minutes_agent/chunking/constants.py`).
- **Per-contact logging**: every diarizer invocation is a logged tool contact with a receipt
  (C9 instrumentation discipline); output tagged `TOOL_DIAR` (Tier-M0) at the
  `DiarizationBackend` seam, distinct from the `ORACLE_TURN` (Tier-M1) ceiling arm.
- **No gated access** if avoidable — collaborator reproduction must not require per-user HF
  token-gated acceptance.

## 2. NVIDIA primary — verification

A newer NVIDIA successor **exists**: `nvidia/diar_streaming_sortformer_4spk-v2`
(same Sortformer family, last modified 2026-08-12, permissive CC-BY-4.0, offline mode
supported, plus a first-party GGUF + C++ runtime). Under the ruling's successor clause, this
ticket pins **v2 as the primary checkpoint** and keeps v1 as the same-family alternate.
Both are verified below.

### 2.1 Identity, revision, format, size, gating

| | `diar_sortformer_4spk-v1` | `diar_streaming_sortformer_4spk-v2` |
|---|---|---|
| HF repo id | `nvidia/diar_sortformer_4spk-v1` | `nvidia/diar_streaming_sortformer_4spk-v2` |
| Latest revision (API `sha`) | `9f17b10df44c0a4c8f3c86fbddc9ee2d6ab9ac08` (2025-12-15) | `5240a64075176943f677d30fa2171c780229f341` (2026-08-12) |
| Checkpoint | `diar_sortformer_4spk-v1.nemo`, 493,434,880 B (~471 MiB); also `model.safetensors`, 494,206,256 B | `diar_streaming_sortformer_4spk-v2.nemo`, 471,367,680 B (~450 MiB); also `diar_streaming_sortformer_4spk-v2.q8_0.gguf`, 147,075,776 B (~140 MiB) |
| Params | ~0.1 B (fp32) | 117 M |
| Gated | **No** (`gated: false`) | **No** (`gated: false`) |

Neither repo requires token-gated acceptance — anonymous download works, which is the
collaborator-reproduction property the fallback lacks. Sources:
<https://huggingface.co/api/models/nvidia/diar_sortformer_4spk-v1> (add `?blobs=true` for
sizes), <https://huggingface.co/api/models/nvidia/diar_streaming_sortformer_4spk-v2>,
<https://huggingface.co/nvidia/diar_sortformer_4spk-v1>,
<https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2>.

### 2.2 License

- v1: **CC-BY-NC-4.0** (model card) — research use permitted; non-commercial restriction
  acceptable for this academic program.
- v2: **CC-BY-4.0** — permissive attribution-only; strictly better for reproduction and any
  later release. Another point in favour of pinning v2.

### 2.3 Speaker-count bound vs our corpus

Both checkpoints detect **a maximum of 4 speakers**; the cards state performance degrades on
recordings with 5+ speakers. **AMI scenario meetings have exactly 4 speakers, so our G1
discovery surface (AMI dev-18, all-scenario subset) sits exactly at the model's design
point** — this is a fit, not a compromise. **ICSI (3–10 speakers) is OUT of the primary's
bound**; any ICSI diarization goes to the fallback (pyannote 3.1 has no speaker-count cap).
Input: 16 kHz mono WAV (AMI Mix-Headset condition complies). Output: per-frame speaker
activity, post-processed to `begin_seconds, end_seconds, speaker_index` segments — exactly
the speaker-labelled timestamped turns the slicer seam needs.

### 2.4 Runtime path

**(a) NeMo toolkit inference (reference path).** Both cards say "install NeMo main branch"
and pin no toolkit version. PyPI `nemo-toolkit` latest is **3.0.0** (Python >=3.10; latest
2.x is 2.7.0). Its base torch requirement is an open bound **`torch>=2.6.0`** — no upper
pin — so a cu128 torch build (sm_120 / RTX 5090; our shared venv already runs one) satisfies
it with **no conflict**. One trap: the optional `cu12` / `cu13` extras pin
`torch==2.12.0+cu126` / `+cu132`; installing those extras would replace the cu128 build.
**Do not install the cu12/cu13 extras** — install torch from the cu128 index first, then
`nemo_toolkit[asr]` on top. Source: <https://pypi.org/pypi/nemo-toolkit/json>.
Inference class: `nemo.collections.asr.models.SortformerEncLabelModel.from_pretrained(...)`
(both model cards).

**(b) Export path without the full NeMo runtime.** **ONNX/TensorRT export of Sortformer is
NOT confirmable**: neither model card mentions ONNX or TensorRT, and a GitHub code search for
`sortformer onnx` in `NVIDIA/NeMo` returns zero hits. However, a **first-party non-NeMo
runtime exists and supersedes the ONNX idea**: the v2 card ships a `q8_0` GGUF consumed by
**NeMo-Speech.cpp** (<https://github.com/NVIDIA/NeMo-Speech.cpp>) — NVIDIA's native C++
runtime built on ggml/llama.cpp (git submodules), Apache-2.0 for NVIDIA-authored code, with
CUDA/CPU/Metal/Vulkan backends (build: CMake >=3.26, Ninja, C++17, CUDA toolkit). Its CLI:
`nemo-speech diarize meeting.wav --model diar_streaming_sortformer_4spk-v2.q8_0.gguf
--offline --format rttm --output meeting.rttm`, with segmentation-threshold flags
(`--onset`, `--offset`, `--pad-onset`, `--pad-offset`, `--min-duration-on`,
`--min-duration-off`) — see
<https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/cli.md>. **This is the PREFERRED
deployment story**: 140 MiB model file, no Python ML stack at inference time, same
ggml/llama.cpp lineage as our pinned Qwen3-Omni `llama-server` transport. GGUF exists for v2
only (v1 ships none) — a further reason the pin is v2. Caveat: q8_0 is quantized; the smoke
(SS5) measures fp32-vs-GGUF DER parity before the GGUF path is frozen as the deployment pin.

### 2.5 Published DER on AMI

**NVIDIA publishes NO AMI DER for either checkpoint.** Card-reported numbers (all conditions
**include overlapping speech**, post-processing enabled):

- v1: DIHARD3-Eval 14.76 % (collar 0.0 s); CALLHOME-part2 2/3/4-spk 5.85 / 8.46 / 12.59 %
  (collar 0.25 s); CH109 6.27 %.
- v2 (1.04 s latency setting): DIHARD III 1–4-spk 13.24 %, full 18.91 %; CH109 4.88 %
  (collars as above per dataset).

AMI appears in **both models' training-data lists** ("AMI Meeting Corpus", real-conversations
section of each card; the partition used is not stated). Two consequences, stated honestly:
(i) our AMI dev DER should benefit from in-domain training, and no third-party AMI number can
substitute for our own measurement — the smoke measures it against the NXT oracle; (ii) this
is tool-training exposure, not task-label leakage — the diarizer never sees our task gold —
but the unverifiable partition overlap with dev-18 must be recorded as a caveat in the smoke
receipt.

### 2.6 Streaming variant

v2 **is** the streaming variant (speaker-cache, arrival-order-preserving Sortformer;
arXiv:2507.18446, cited by the card) and also supports offline full-attention inference
(`--offline` in NeMo-Speech.cpp); relevant to future online meeting-notes use only — this
ticket pins it for offline batch use.

## 3. Fallback — pyannote.audio 3.x `speaker-diarization-3.1`

`pyannote/speaker-diarization-3.1` (pipeline for pyannote.audio >=3.1; pure PyTorch in 3.1 —
the 3.0-era ONNX dependency was removed; no hard torch pin, so cu128 torch is compatible).
License **MIT**, but the HF repo is **GATED**: the user must accept conditions and present an
HF token, and the pipeline additionally requires accepting `pyannote/segmentation-3.0` —
per-collaborator friction that is precisely why it is the fallback, not the primary.
Published AMI DER (model card, **no forgiveness collar, overlapped speech evaluated**):
**18.8 %** on AMI headset-mix (only_words), 22.4 % on AMI array1-channel-1 — these are the
comparison anchors for our smoke. No speaker-count cap, so it also covers **ICSI (3–10
speakers)**, which is outside the primary's 4-speaker bound. Source:
<https://huggingface.co/pyannote/speaker-diarization-3.1>.

## 4. Install plan (never touches `~/.venvs/speechrl`)

Two routes; the smoke needs Route A (reference numbers) and builds Route B (deployment
parity). Nothing here is executed under this ticket.

**Route A — isolated NeMo venv `~/.venvs/diar`** (WSL2 Ubuntu-24.04, ext4):

```bash
python3.12 -m venv ~/.venvs/diar
source ~/.venvs/diar/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu128   # cu128 = sm_120; mirror the shared venv's proven build; record exact version in the receipt
pip install "nemo_toolkit[asr]==3.0.0"    # NO cu12/cu13 extras (they pin torch cu126/cu132)
pip install pyannote.metrics              # DER scoring only; ungated PyPI package
```

Fallback pin if 3.0.0 fails to load the checkpoints: `nemo_toolkit[asr]==2.7.0` (last 2.x).
Downloads: torch cu128 wheel ~3 GB (estimate), `nemo_toolkit[asr]` + dependencies ~2–3 GB of
wheels (estimate), model `diar_streaming_sortformer_4spk-v2.nemo` **471,367,680 B exact**
(plus, only if the contingent v1 arm triggers, `diar_sortformer_4spk-v1.nemo`
**493,434,880 B exact**). Model files land under
`SPEECHRL_DATA_DIR/models/diarization/<repo>@<revision>/`, never in Git.

**Route B — NeMo-Speech.cpp (CUDA backend), the smaller reproduction footprint**:
`git clone --recursive https://github.com/NVIDIA/NeMo-Speech.cpp` (pin the commit +
ggml/llama.cpp submodule commits in the receipt), build with CMake >=3.26 + Ninja + C++17 +
CUDA toolkit already present in WSL2; download only the **147,075,776 B** q8_0 GGUF via
`hf download nvidia/diar_streaming_sortformer_4spk-v2 diar_streaming_sortformer_4spk-v2.q8_0.gguf
--revision 5240a64075176943f677d30fa2171c780229f341`. No Python ML stack at inference; DER
scoring still uses the tiny `pyannote.metrics` install from Route A (CPU-only). Do not
install ffmpeg (program pin); AMI Mix-Headset WAVs are read directly.

## 5. Bounded smoke plan on AMI dev (PLAN ONLY — to be separately registered before any model contact)

- **Meetings (6, all from the frozen dev-18 discovery surface, Mix-Headset, exactly 4
  speakers each):** ES2011a, **ES2011b, IS1008b, IS1008d, TS3004b** (the four already
  registered for the G1 oracle smoke — maximizes comparability with the measured
  oracle-ceiling economics), plus TS3004d; covers all three scenario sites (ES/IS/TS).
- **Arms:** **A** (required): v2 `.nemo` fp32, NeMo offline inference, card-default
  post-processing. **B** (required): v2 q8_0 GGUF via NeMo-Speech.cpp CUDA, `--offline
  --format rttm`, same thresholds — parity gate: |DER(B) − DER(A)| within a registered bound
  (indicative: <= 1.0 absolute point median) before the GGUF path becomes the deployment pin.
  **C** (contingent, runs only if A's median DER exceeds pyannote's published AMI array
  anchor 22.4 %): v1 `.nemo` fp32; if C also exceeds it, the fallback ticket activates.
- **Reference and metrics:** reference RTTM derived from the NXT oracle turn table
  (`chunking.adapters.turn_table_from_resolved_meeting` — no model contact). Score with
  `pyannote.metrics`: (i) DER at collar 0.0 s with overlap (pyannote-card-comparable) and at
  collar 0.25 s; (ii) turn-boundary precision/recall at ±0.25 s and ±0.5 s tolerance after
  optimal (Hungarian) speaker mapping, plus detected-speaker-count correctness (target:
  exactly 4 on >= 5/6 meetings); (iii) **consumer-level check**: build the `SlicePlan`
  through the seam with `TOOL_DIAR` provenance and report slice-boundary displacement
  (mean/max) and slice-count delta vs the oracle-backend plan on the same meetings — the
  metric the 90 s packing actually cares about.
- **Runtime/GPU ceiling (registered caps):** <= 30 min total GPU wall-clock across all arms,
  <= 10 GB peak VRAM, <= 2 h total flight wall-clock including venv build; per-meeting
  wall-clock and peak VRAM are receipt deliverables.
- **Pin set the smoke must freeze (receipt contents):** HF repo id + revision sha (SS2.1
  values) + **sha256 of every downloaded checkpoint byte-stream** (`.nemo`, `.gguf`);
  `pip freeze` of `~/.venvs/diar` (torch/nemo/pyannote.metrics exact versions);
  NeMo-Speech.cpp git commit + ggml/llama.cpp submodule commits + CMake flags; all
  post-processing threshold values; per-contact receipts for every diarizer invocation
  (tool contact, `TOOL_DIAR`); the SS2.5 training-data-overlap caveat, restated.
- **Wiring after a passing smoke:** implement `PinnedToolDiarization` over the pinned runtime
  (RTTM/segment table -> `TurnSpan` rows, provenance `TOOL_DIAR`), leaving
  `NxtOracleDiarization` as the untouched ceiling arm.
