# Reproducing this repository's meeting-line work

Single entry point for reproducing this repository's pipeline end to end on a machine that is
**not** the primary dev machine and does **not** have access to the umbrella governance repo
(`exploring-l4-intelligence`) or either sibling study repo. Everything this file references is
either public (upstream source, public HF/AMI/ICSI downloads) or vendored into this repository
(`third_party/llama.cpp-featcache/`, `docs/assets.lock.json`, `scripts/data/datasets.lock.json`,
`requirements-freeze.txt`).

Read order if you are new here: this file, then `README.md` (research framing), then
`docs/decisions.md` (why the pipeline is shaped the way it is) only if you need the rationale
behind a specific design choice.

## 0. What you are reproducing

Four layers, each independently reproducible and independently verifiable against a committed
receipt:

1. **The patched `llama-server` build** (`third_party/llama.cpp-featcache/`) -- the frozen
   Qwen3-Omni core's serving binary, patched with an on-disk feature cache.
2. **Model assets** (`docs/assets.lock.json`) -- the Qwen3-Omni Q4_K_M GGUF + mmproj pair the
   server loads, and the pinned diarization tool's checkpoint(s).
3. **Corpus assets** (`scripts/data/datasets.lock.json`, `scripts/data/README.md`) -- AMI, ICSI,
   MeetingQA, QMSum, M3-SLU, MeetingBank.
4. **This repository's own Python code** -- offline (parsers, chunking, metrics, tests, no model
   contact) plus the two real-flight drivers, `scripts/run_precomp.py` (PRECOMP: diarize + slice
   + feature-cache warm) and `scripts/run_g1.py` / `scripts/g1_read.py` (G1: the floors campaign
   and its one-shot scoring read).

Layers 1-3 are needed only if you intend to run a real flight (PRECOMP/G1) yourself. Layer 4's
offline half (the pytest suite) needs none of them.

## 1. Environment assumptions

The primary dev machine is **WSL2 Ubuntu-24.04, Python 3.12, an RTX-class NVIDIA GPU with the
CUDA 12.8 (`cu128`) toolkit, sm_120 (Blackwell / RTX 5090)**. What changes on a different setup:

- **Different GPU generation.** `-DCMAKE_CUDA_ARCHITECTURES=120` (llama.cpp) and
  `CMAKE_CUDA_ARCHITECTURES=120` (NeMo-Speech.cpp) target sm_120 specifically. Set this to your
  own GPU's compute capability (e.g. `86` for RTX 30-series/A100 sm_86, `89` for RTX 40-series
  sm_89) and use a CUDA toolkit version your driver actually supports -- the patch series and the
  Python code have no sm_120-specific logic; only the two CMake invocations do.
- **No GPU at all.** The offline half of this repository (parsers, chunking, metrics, the whole
  pytest suite) needs no GPU. A real PRECOMP/G1 flight needs a GPU to be practical (both
  `llama-server` and NeMo-Speech.cpp can build CPU-only, but per-slice encode/diarize wall time
  documented in this repository's receipts assumes CUDA).
- **Native Linux instead of WSL2.** Nothing in this repository's own Python code is WSL-specific.
  The only WSL-specific items are operational conventions recorded in historical receipts
  (`docs/checks/*/script-*.sh`) -- e.g. paths like `/home/chao/...` are that machine's own layout,
  not a requirement; substitute your own paths throughout.
- **Windows without WSL2.** Untested by this repository. `soundfile`/`librosa`/`numpy` are
  cross-platform; the two C++ binaries build with a native Windows CMake+CUDA toolchain in
  principle, but no receipt in this repository was produced that way.

## 2. Clone

```bash
git clone https://github.com/chaosxingxc-orion/meeting-minutes-agent.git
cd meeting-minutes-agent
```

## 3. Build the patched `llama-server`

Full account: `third_party/llama.cpp-featcache/README.md` (what the patch does, why, and the
complete build recipe) and `third_party/llama.cpp-featcache/COLD-CACHE.md` (the on-disk cache
tier in detail). Summary:

```bash
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
git checkout fdbd6abee20e408de21e90ca77a24cd50a6ea073   # third_party/llama.cpp-featcache/UPSTREAM
git am /path/to/meeting-minutes-agent/third_party/llama.cpp-featcache/patches/*.patch
# expected resulting tip: 5d9dfcb58ea860295da8fc93c7b5bed9e2c71151

cmake -S . -B build -G Ninja \
      -DGGML_CUDA=ON -DCMAKE_CUDA_COMPILER=<path-to-nvcc> \
      -DCMAKE_CUDA_ARCHITECTURES=120 -DLLAMA_CURL=OFF   # adjust 120 for your GPU (Section 1)
cmake --build build -j 6
```

Before building, verify the patch series applies cleanly and reproduces the pinned tip hash with
**no CUDA build required**:

```bash
bash /path/to/meeting-minutes-agent/third_party/llama.cpp-featcache/verify.sh
```

This clones upstream into a scratch directory, applies the four patches, diffs against the
pinned base, and reports `OK: tip hash matches.` or a mismatch explanation. It never touches this
repository's own tree and makes no network calls beyond `git clone`/`git fetch`.

**Expected binary behavior once built:** `./build/bin/llama-server -m <core.gguf> --mmproj
<mmproj.gguf> -c 49152 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0` (this repository's pinned
server flags, e.g. `docs/checks/2026-08-19-precomp-wave1/script-serve.sh`) should start and
serve an OpenAI-shaped HTTP API on the given host/port. Compiled binary bytes are toolchain-
dependent and are **not** a reproduction target -- only the source tip hash above is pinned; see
`third_party/llama.cpp-featcache/README.md`'s own note on this.

## 4. Build the pinned diarization tool (NeMo-Speech.cpp)

The production pipeline (PRECOMP, G1) diarizes with **Arm B**: NVIDIA's native C++ runtime over
the diar-sortformer q8_0 GGUF, locked by owner adjudication
(`docs/readiness/2026-08-19-diar-adjudication-TOOL-LOCKED-B.md`). Unlike llama.cpp, this
repository vendors **no patch series** for it -- it is a public NVIDIA repo, built unmodified
with its own CMake preset:

```bash
git clone --recursive https://github.com/NVIDIA/NeMo-Speech.cpp
cd NeMo-Speech.cpp
git checkout 4c749a700500e077d4732a539eb082bf2208dac7   # this program's pinned commit
git submodule update --init --recursive
bash scripts/configure.sh   # applies NVIDIA's OWN pinned CUDA patch series to the ggml submodule
                             # (not vendored by this repository -- see docs/assets.lock.json's
                             # deployment_runtime_for_diar_sortformer_gguf note); consult that
                             # project's own docs/ if this script has moved or renamed
cmake --preset cuda-diar   # Ninja, Release, GGML_CUDA=ON, CMAKE_CUDA_ARCHITECTURES=120 -- adjust for your GPU
cmake --build --preset cuda-diar
```

This program's pinned build additionally used `cmake 4.3.4` with
`-DCMAKE_POLICY_VERSION_MINIMUM=3.5` for the bundled `sentencepiece` sub-build and GCC 13.3.0; if
your `cmake`/GCC differ, that sub-build is the most likely place to hit a policy-version error
first.

CLI shape: `nemo-speech diarize meeting.wav --model
diar_streaming_sortformer_4spk-v2.q8_0.gguf --offline --format rttm --output meeting.rttm`
(full flag reference: <https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/cli.md>).
Production flights actually run the tool's **DiarStream streaming** mode, not `--offline` (the
`--offline` full-attention mode is hard-capped at ~6 minutes of audio and refuses longer
meetings -- `docs/checks/2026-08-18-diar-smoke-flight/README.md`); the exact pinned argv this
repository's own Python wraps is `chunking/diarization.py`'s `ToolDiarizationConfig`, loaded from
an `--arm-config` JSON (see `docs/checks/2026-08-19-precomp-wave1/script-env.sh`'s
`ARM_CONFIG` for a worked example path).

Full submodule/commit pin detail (including the `ggml` submodule's own CUDA patch series --
NVIDIA's own, not this repository's): `docs/assets.lock.json`'s
`deployment_runtime_for_diar_sortformer_gguf` block.

**Optional, historical-only:** the isolated NeMo-toolkit venv (`~/.venvs/diar`, `nemo_toolkit[asr]
==3.0.0` + `torch` cu128 + `pyannote.metrics`) that produced the one-shot Arm A fp32 reference
number during tool selection (`docs/plans/2026-08-18-diarization-tool-selection.md` Section 4,
Route A) is **not** needed to reproduce the locked, production Arm B pipeline -- it exists only
in the historical `docs/checks/2026-08-18-diar-smoke-flight/` comparison. Skip it unless you are
specifically trying to reproduce that one-shot comparison.

## 5. Fetch model assets

`docs/assets.lock.json` is a vendored, model-only extract of the umbrella program's asset lock
(which this repository's external collaborators do not have access to), carrying exactly the two
model entries this repository's receipts reference: the Qwen3-Omni Q4_K_M GGUF + mmproj pair, and
the diar-sortformer-4spk-v2 checkpoint pair (fp32 `.nemo` + q8_0 `.gguf`). Each entry carries
source repo/revision, exact filenames, byte sizes, sha256, and license. **The umbrella lock
remains the program-level authority; this file is a read-only, provenance-stamped subset of it**
-- do not hand-edit it to change an identity field.

```bash
export SPEECHRL_DATA_DIR=/path/to/your/data-root   # Section 8

# Qwen3-Omni Q4_K_M core + mmproj (fetch the two files named in docs/assets.lock.json
# from ggml-org/Qwen3-Omni-30B-A3B-Instruct-GGUF on Hugging Face)
hf download ggml-org/Qwen3-Omni-30B-A3B-Instruct-GGUF \
    Qwen3-Omni-30B-A3B-Instruct-Q4_K_M.gguf mmproj-Qwen3-Omni-30B-A3B-Instruct-bf16.gguf \
    --local-dir "$SPEECHRL_DATA_DIR/models/qwen3-omni-30b-a3b-instruct-gguf-q4km"

# diar-sortformer-4spk-v2 (both payloads; the .nemo is optional -- see Section 4)
hf download nvidia/diar_streaming_sortformer_4spk-v2 \
    diar_streaming_sortformer_4spk-v2.q8_0.gguf diar_streaming_sortformer_4spk-v2.nemo \
    --revision 5240a64075176943f677d30fa2171c780229f341 \
    --local-dir "$SPEECHRL_DATA_DIR/models/diar-sortformer-4spk-v2"

# verify every sha256 in docs/assets.lock.json against what you downloaded, e.g.:
python3 - <<'PY'
import hashlib, json, os, pathlib
lock = json.load(open("docs/assets.lock.json", encoding="utf-8"))
root = pathlib.Path(os.environ["SPEECHRL_DATA_DIR"]).expanduser() / "models"
for model in lock["models"]:
    for f in model["files"]:
        p = root / model["local_subdir"].split("/", 1)[1] / f["filename"]
        got = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
        ok = "OK" if got == f["sha256"] else f"MISMATCH (got {got})"
        print(f"{p}: {ok}")
PY
```

There is **no separate VAD model asset** -- the no-diarization ablation is a pure,
signal-derived energy-pause detector over the decoded waveform (`docs/assets.lock.json`'s
`no_separate_vad_asset` note; `chunking/slicer.py::build_vad_slice_plan`).

## 6. Fetch corpus assets (AMI, ICSI, MeetingQA, QMSum, M3-SLU, MeetingBank)

Full detail (source URLs, revisions, licenses, sizes, expected layouts, per-file hashes) is in
`scripts/data/README.md` and `scripts/data/datasets.lock.json` -- itself a meeting-scoped extract
of the umbrella lock, already vendored in this repository. Quick start:

```bash
export SPEECHRL_DATA_DIR=/path/to/your/data-root
bash scripts/data/setup.sh --list          # see all six datasets, download nothing
bash scripts/data/setup.sh                 # download + verify all six (idempotent, resumable)
python scripts/data/verify.py              # re-check what's on disk, stdlib-only, no network
```

This repository's own flown receipts consume **AMI only** (Mix-Headset WAVs + manual v1.6.2
NXT annotations); the other five datasets exist for the wider research program's QA/summarization
surfaces and are not required to reproduce a PRECOMP/G1 flight. AMI's audio download is a
form-gated official mirror (`setup.sh` prints the exact steps); everything else is open HTTP or
public git/HF clones. Read each dataset's license notice before downloading, especially
MeetingBank's (CC BY-NC-ND 4.0 -- see `scripts/data/README.md`).

## 7. Python environment

```bash
python3.12 -m venv ~/.venvs/mma-repro
source ~/.venvs/mma-repro/bin/activate
pip install uv
uv pip install -e ".[dev]"
```

This installs `pyproject.toml`'s declared surface: runtime deps `soundfile`, `librosa`, `numpy`,
plus dev dep `pytest`. **This alone reproduces the offline half of the pytest suite, but with
MORE skips than the primary dev machine's own 6-skip baseline** (Section 9) -- several test files
`pytest.importorskip` on packages `pyproject.toml` deliberately does not declare (openjiuwen never
enters `pyproject.toml` by design -- `client/component.py`'s own docstring). To match the full
1550/6 baseline exactly, also install:

```bash
pip install meeteval==0.4.3 jiwer==4.0.0 rouge_score==0.1.2 openjiuwen==0.1.16.post2
```

All four are public on PyPI (verified 2026-08-20). `requirements-freeze.txt` (repo root) is the
primary dev machine's exact `pip freeze` of its **shared, multi-repo** venv on the capture date --
read its own header comment before using it; it is a version-pin reference, not a file meant for
a literal `pip install -r` (it carries several sibling-repo editable installs that will not
resolve on your machine). The subset relevant to this repository is called out at the top of that
file.

**Do not `pip install` anything into a venv you did not create for this reproduction.** In
particular, never repurpose another repository's shared venv -- this repository's own
`conftest.py` and the sibling studies' own tooling assume exclusive control of whichever venv
they run against.

## 8. Environment variable contract

Every environment variable this repository's own code (`src/`, `scripts/`, `conftest.py`) reads,
found by grepping `os.environ`/`os.getenv` across the whole tree, plus the ones the *compiled*
`llama-server` reads (fixed by the C++ patch, not by Python):

| Variable | Read by | Purpose | Default if unset |
|---|---|---|---|
| `SPEECHRL_DATA_DIR` | `scripts/data/verify.py`, `scripts/run_precomp.py --data-dir`, `scripts/run_g1.py --data-dir`, `tests/integration/*` | Data root: `datasets/`, `models/`, `derived/` all live under it. Never committed to Git. | none (required where read; integration tests fall back to this machine's own historical path, see below) |
| `AMI_ANNOTATIONS_ROOT` | `tests/integration/test_real_ami_meeting.py` | Overrides the AMI NXT annotations path for that one gated integration test. | `$SPEECHRL_DATA_DIR/datasets/ami/annotations/manual_1.6.2`-shaped path (the test's own hardcoded fallback references the primary dev machine's own `/mnt/e/...` path -- override it) |
| `MMA_RUN_AMI_INTEGRATION` | `tests/integration/test_real_ami_meeting.py` | Set to `1` to opt into the one real-AMI-bytes integration test (skipped otherwise). | unset (skip) |
| `MMA_RUN_MEETINGQA_INTEGRATION` | `tests/integration/test_meetingqa_real_release.py` | Set to `1` to opt into the one real-MeetingQA-bytes integration test. | unset (skip) |
| `MMA_RUN_G1_QA_ROUTING_INTEGRATION` | `tests/integration/test_g1_qa_routing_real_release.py` | Set to `1` to opt into the three real-release G1-QA-routing integration tests. | unset (skip) |
| `MMA_FEAT_CACHE_ROOT` | `src/meeting_minutes_agent/client/featcache.py` | This repository's own override for the feature-cache root directory (`<root>/<dataset>-<encoder>/`). | `/home/chao/feat-cache` (the primary dev machine's own path -- **always override this**) |
| `LLAMA_MTMD_FEAT_CACHE_DIR` | the **compiled `llama-server`** (fixed by the C++ patch, not by this repository's Python) | On-disk feature-cache directory for the running server process; unset means RAM-only for that process's lifetime. Set this to exactly what `featcache.py`'s `server_env()` resolves (or `MMA_FEAT_CACHE_ROOT`-relative) before launching the server. | unset (RAM-only cache) |
| `LLAMA_MTMD_FEAT_CACHE_VALIDATE` | the compiled `llama-server` | Audit mode: encode every chunk AND byte-compare against the cache (never skips the encoder). Debugging only -- never leave set for a timed run. | unset (normal cache-skip mode) |
| `PYTHONDONTWRITEBYTECODE` | the Python interpreter itself | Prevents `.pyc` writes under the frozen scoring/pipeline packages during a flight or a read. Not read by this repository's code directly, but every historical receipt sets it and you should too. | unset (bytecode caching on -- harmless for tests, but avoid it for anything touching a "frozen" package during a registered flight/read) |
| `PYTHONPATH` | the Python interpreter itself | Needed only if you run `pytest`/scripts without `pip install -e .` first (`conftest.py`'s own shim also inserts `src/` onto `sys.path` as a fallback). | n/a |
| `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE` | not read by this repository's own code; set defensively in every historical flight's `script-env.sh` | Prevents an accidental network call if some transitively-imported package (huggingface_hub/transformers, pulled in by a sibling package in a shared venv) tries to phone home mid-flight. Harmless to set even though nothing in `src/` needs it. | unset |

## 9. Run pytest

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$(pwd)/src"     # skip if you `pip install -e .`
pytest -q
```

**Expected baseline (measured directly for this audit, 2026-08-20, `HEAD ca3857c`, clean tree,
shared-venv extras all present per Section 7): `1550 passed, 6 skipped, 3 warnings` in ~60 s.**
The 6 skips, verbatim:

```
SKIPPED [3] tests/integration/test_g1_qa_routing_real_release.py: gated behind MMA_RUN_G1_QA_ROUTING_INTEGRATION=1
SKIPPED [1] tests/integration/test_meetingqa_real_release.py: gated behind MMA_RUN_MEETINGQA_INTEGRATION=1
SKIPPED [1] tests/integration/test_real_ami_meeting.py: gated behind MMA_RUN_AMI_INTEGRATION=1
SKIPPED [1] tests/unit/client/test_component.py: the absent-install refusal path only exists when openjiuwen is not installed
```

The first four require real corpus bytes under `$SPEECHRL_DATA_DIR` and the matching
`MMA_RUN_*_INTEGRATION=1` flag (Section 8) to run instead of skip. The fifth is **expected to
skip when `openjiuwen` IS installed** (it specifically tests the absent-install error path) --
this is not a gap, it is the baseline's own designed shape.

**If your count differs from 1550/6, the most likely cause is an extras mismatch (Section 7),
not a real regression:**

- Fewer than 1550 passed, with skips beyond the 6 above → you are missing one of `meeteval`,
  `jiwer`, `rouge_score`, `openjiuwen` (each gates a whole test file or specific tests via
  `pytest.importorskip`; see `tests/unit/metrics/test_wer.py`, `test_pins.py`,
  `test_rouge_legacy.py`, `tests/unit/probes/test_*_scoring.py`,
  `tests/unit/scripts/test_g1_read.py`, `test_pprompt_read.py`, and `tests/unit/client/
  test_component.py`, `tests/unit/controller/test_loop.py`, `tests/unit/harness/test_episode.py`
  for `openjiuwen`).
- More than 6 skipped with `openjiuwen` installed → check whether `test_component.py`'s absent-
  install-refusal test is somehow still counted a skip; that would mean `openjiuwen` failed to
  import for a reason other than absence (version mismatch -- pin exactly `0.1.16.post2`).

## 10. Run the PRECOMP pipeline

`scripts/run_precomp.py` is the diarize → slice → feature-cache-warm driver. It never starts,
stops, or health-checks the `llama-server` itself -- point `--server-url` at one you already
launched (Section 3), and never starts a diar subprocess beyond the one `--arm-config` names.

**Safe right now, no model/diar contact** (prints the resolved roster + registered ceilings):

```bash
python scripts/run_precomp.py --wave 1 --data-dir "$SPEECHRL_DATA_DIR" --summary-only
```

**A real wave** needs an `--arm-config` JSON naming the pinned Arm B tool invocation
(`load_arm_b_config` refuses a file with no top-level `"B"` key -- PRECOMP flies Arm B only).
This repository ships no pre-built one (it names machine-local binary/model paths, so a fresh
copy is not portable); write your own from this shape, substituting your own paths from
Sections 4-5 (this is the same shape `docs/checks/2026-08-18-diar-smoke-flight/arm-config.json`
used, "B" entry only):

```json
{
  "B": {
    "tool_name": "nemo-speech.cpp-cuda-q8_0",
    "tool_version": "nemo-speech 1.0.0; commit 4c749a700500e077d4732a539eb082bf2208dac7",
    "checkpoint_sha256": "0679cfeb1ce356d0dea9470b31274f4bfc7eb927497d82005483770666da998a",
    "command_template": [
      "/path/to/NeMo-Speech.cpp/build/cuda-diar/bin/nemo-speech",
      "diarize", "{audio_path}",
      "--model", "/path/to/models/diar-sortformer-4spk-v2/diar_streaming_sortformer_4spk-v2.q8_0.gguf",
      "--format", "rttm", "--recording-id", "{meeting_id}", "--output", "{rttm_path}", "--force"
    ],
    "timeout_seconds": 3600
  }
}
```

`{audio_path}`/`{rttm_path}`/`{meeting_id}` are substituted per-meeting by
`chunking/diarization.py`'s `PinnedToolDiarization`; leave them exactly as shown. Then:

```bash
python scripts/run_precomp.py \
    --wave 1 --data-dir "$SPEECHRL_DATA_DIR" \
    --arm-config /path/to/your/arm-config.json \
    --server-url http://127.0.0.1:8080 \
    --model-path "$SPEECHRL_DATA_DIR/models/qwen3-omni-30b-a3b-instruct-gguf-q4km/Qwen3-Omni-30B-A3B-Instruct-Q4_K_M.gguf" \
    --model-sha256 0751c279498785c0b07130ae7748038d1e2cfd04617928e4557063807f98066d \
    --out-dir docs/checks/<your-run-id> --resume
```

**Wave profiles and ceilings** (`src/meeting_minutes_agent/precomp/budget.py`, registered in
`docs/readiness/2026-08-19-precomp-preregistration.md`):

| Wave | Roster | Diar GPU-h | Encode GPU-h | Cutting wall-h | Encode calls |
|---|---|---|---|---|---|
| 1 | the frozen "dev-18" AMI meetings | ≤0.5 | ≤2.0 | ≤2.0 | ≤900 |
| 2 | the remaining usable-discovery roster minus dev-18 (76 meetings) | ≤2.0 | ≤8.0 | unchecked | ≤4,500 |
| `g1-supplement` | any `--turn-sources vad` invocation (the Z-nodiar ablation's own slice set) | ≤0.1 (never binds -- VAD never contacts the diar tool) | ≤1.0 | ≤1.0 | ≤500 |

A `PrecompBudgetExceeded` on any axis stops the wave immediately and still writes a wave summary
for whatever already completed -- never a partial-write crash. `--stop-file <path>` gives you a
clean, in-flight way to end a long wave early: its mere presence, checked before every meeting
(including the first), ends the run cleanly and the wave resumes at meeting granularity with
`--resume` once the file is cleared. Every meeting receipt is fsynced before the next meeting
starts, so a crash costs at most the in-flight meeting.

## 11. Run G1

`scripts/run_g1.py` (the flight) and `scripts/g1_read.py` (the one-shot scoring read) run over
PRECOMP's already-cut slices and already-produced RTTMs -- G1 itself never diarizes or cuts
audio; `resolve_slice_plan` **rebuilds** each (meeting, arm)'s slice plan deterministically from
PRECOMP's on-disk cache on every invocation (CPU-only, no model contact).

**Safe right now** (prints the resolved roster/arms/QA-cap count, no PRECOMP-cache I/O, no model
contact):

```bash
python scripts/run_g1.py --mode floors --data-dir "$SPEECHRL_DATA_DIR" --summary-only
```

**The flight, one invocation per chunk** (chunk-granularity server ownership: each invocation
starts its own `llama-server` as a direct child, does that chunk's work, tears the server down in
a `finally`, and exits -- so the whole invocation finishes well inside a 60-minute background-job
reap window):

```bash
python scripts/run_g1.py --mode floors --data-dir "$SPEECHRL_DATA_DIR" \
    --run-chunk 0 --resume --stop-file docs/checks/<campaign>/G1_YIELD \
    --server-cmd llama-server --host 127.0.0.1 --port 8080 -m <core.gguf> --mmproj <mmproj.gguf> \
        -c 49152 -np 4 -fa on -ngl 999 -ctk q8_0 -ctv q8_0 \
    --base-url http://127.0.0.1:8080 \
    --model-path <core.gguf> --model-sha256 0751c279498785c0b07130ae7748038d1e2cfd04617928e4557063807f98066d \
    --meetingqa-root "$SPEECHRL_DATA_DIR/datasets/meetingqa" \
    --ami-root "$SPEECHRL_DATA_DIR/datasets/ami" \
    --out-dir docs/checks/<campaign>/<release-id>
```

Campaign ceilings (`probes/g1_campaign.py`): ≤2,900 core calls / ≤6.0 GPU-hours / ≤8.0 wall-hours,
chunks bin-packed to ≤50 minutes each.

**The read** (registered, one-shot, refuses to overwrite a prior read's output unless `--force`):

```bash
python scripts/g1_read.py \
    --data-dir "$SPEECHRL_DATA_DIR" \
    --responses-dir "$SPEECHRL_DATA_DIR/derived/meeting-minutes/g1/runs/<run-id>" \
    --vad-manifest-dir "$SPEECHRL_DATA_DIR/derived/meeting-minutes/precomp/slices/vad-manifest" \
    --meetings ES2011a IS1008a \
    --out-dir docs/checks/<campaign>/<release-id>
```

Omitting `--vad-manifest-dir` fails closed on the Z-nodiar arm (`G1VadSupplementMissingError`)
rather than silently scoring three of the four registered arms.

## 12. Verify against the committed receipts

Every historical flight/read under `docs/checks/` is a real, hash-manifested receipt
(`MANIFEST.sha256` per directory) -- rerunning the machinery on the SAME already-fetched corpus
and model bytes should reproduce it, in two different senses depending on the artifact:

**Byte-identical (deterministic, exact-hash-comparable):**
- **RTTM diarization output.** The pinned Arm B tool is deterministic: `ES2011a.rttm` and
  `ES2011b.rttm` from the DIAR-SMOKE flight are byte-identical to PRECOMP wave-1's own outputs
  for those same meetings, one day and a different invocation apart
  (`docs/checks/2026-08-19-precomp-wave1/README.md`, "Diar reproducibility" section). Wave-2's
  own resume/retry passes reproduced byte-identical RTTM across every re-run
  (`docs/checks/2026-08-19-precomp-wave2/README.md`).
- **Slice-WAV bytes** cut from the same source audio with the same slicer constants/algorithm
  (see Section 13's cache-invalidation note) -- hashed per-directory in each receipt's
  `rttm-artefacts*.sha256` / `slice-wav-count*.txt`.
- **`verdict.json`/`report.txt`** from a given `--responses-dir` -- the scoring path itself is
  pure, deterministic Python over already-flown replies (no model contact at read time), so
  re-running `g1_read.py --force` over the SAME response JSONLs reproduces byte-identical output.

**Tolerance-compared, not byte-identical:**
- **Feature-cache entry counts and `.feat` file bytes.** Reproducing a flight with a COLD cache
  will re-encode everything (a legitimate outcome, just slower); reproducing with a WARM cache
  populated by your own prior run should show the same hit/miss pattern but not necessarily
  identical entry *counts* if your run order or retry history differs from the original receipt's.
- **Wall-clock/GPU-second fields** in every receipt (`encode wall s`, `diar wall s`, `gpu_seconds`
  estimates) -- hardware- and load-dependent by construction; never a reproduction target.
- **Model replies themselves are never checked for byte equality against anything** -- this
  repository's own discipline is pre-registration + one-shot read, not golden-output diffing; a
  re-flown reply is expected to differ from the archived one at the token level even with an
  identical prompt (sampling, batching, and GPU float non-determinism all contribute -- see e.g.
  `docs/datasets.lock.json`'s own note on llama.cpp CUDA batching float jitter for the sibling
  study's embedding model, an observed fact about this exact serving stack).

## 13. Known reproduction hazards

- **Do not install `ffmpeg`.** Every slice this repository has ever cut used the `librosa`
  decode fallback (`chunking/slicer.py`'s own docstring: "ffmpeg is absent by design").
  Installing `ffmpeg` changes which decoder `soundfile`/`librosa` reach for on some inputs, which
  can change decoded sample bytes at the margins -- and because the feature cache's key is a
  content hash of the audio bytes actually sent (`third_party/llama.cpp-featcache/COLD-CACHE.md`,
  "Cache key" section), a byte change cold-starts every affected cache entry rather than failing
  loudly. If you must have `ffmpeg` for an unrelated reason on the same machine, keep it off
  `PATH` (or use a container) for any process that runs this repository's slicer.
- **Set `PYTHONDONTWRITEBYTECODE=1`** for any flight or read (Section 8). A stray `.pyc` under a
  package treated as "frozen" for a registered run is a discipline violation this program's own
  checks treat as closing the gate on that run, even though it has no functional effect on plain
  reproduction.
- **`pip` vs `python -m pip` inside an activated venv.** Discovered while producing
  `requirements-freeze.txt` for this audit: on at least one machine in this program, `source
  <venv>/bin/activate; pip freeze` silently resolved to `/usr/bin/pip` (the system pip, listing
  system/OS packages) rather than the venv's own pip, while `python` in the same shell correctly
  resolved to the venv's interpreter. If a `pip`/`pip freeze`/`pip install` inside an "activated"
  venv looks suspicious (wrong package count, OS packages you never installed), run `which pip`
  and prefer `python -m pip ...` (or the venv's `bin/python -m pip` explicitly), which is not
  subject to this `PATH`-ordering issue.
- **GPU stuck at a low P-state under sustained mixed load.** Multiple flights in this repository's
  `docs/checks/` observed SM clocks pinned near 232 MHz under 90%+ utilization for extended
  stretches, distinct from ordinary power-limited throttling (`docs/checks/2026-08-19-precomp-
  wave2/README.md` explicitly distinguishes the two: "the GPU clock state, not the workload... the
  laptop 5090's normal power-limited behaviour, not the pathological stuck-P-state case"). If
  throughput looks anomalously low, check `clocks.sm` via `nvidia-smi` FIRST. Live workaround used
  throughout this program's own flights: `nvidia-smi -lgc 1200,2500` (locks an SM clock floor;
  run from a context with permission to set GPU clocks, e.g. an elevated shell on the Windows
  host if the GPU is WSL2-passthrough).
- **The 120 s transport bound and its float-epsilon tolerance.** Every transport slice this
  repository sends is hard-capped at `TRANSPORT_SLICE_MAX_S = 120.0` seconds
  (`chunking/constants.py`); a slice whose computed duration exceeds that cap raises
  `TransportBoundViolation` rather than silently truncating or padding. Packing arithmetic can
  accumulate a slice duration like `120.00000000000011s` against the `120.0s` cap purely from
  floating-point summation -- an overrun of `~1.1e-13s`, six orders of magnitude below the
  tolerance. `TRANSPORT_SLICE_MAX_EPSILON_S = 1e-9` (commit `baaf41c`, "fix(chunking):
  float-epsilon tolerance at the transport bound") absorbs exactly this class of overrun and
  nothing more -- it widens the acceptance check by 1e-9 s, never the bound itself; a slice that
  is actually too long by any humanly-meaningful margin still raises. Two prior crashes in
  `docs/checks/2026-08-18-diar-smoke-read/` (`attempt-1-transportbound-crash.log`,
  `attempt-2-transportbound-crash.log`) were diagnosed and fixed by this same discipline before
  the epsilon existed; see `docs/readiness/2026-08-18-diar-smoke-verdict.md` Section 0.2 for the
  full diagnosis chain if you hit a similar-looking crash while reproducing an older commit.
- **Feature-cache invalidation is per-axis, only one of which needs YOU to act** (full account:
  `third_party/llama.cpp-featcache/COLD-CACHE.md`, "Invalidation"). Encoder/GGUF changes need a
  new `<dataset>-<encoder>` directory (never reuse a directory name across two different GGUF
  builds). A slicer constant or algorithm change (a different snap window, sample rate, or
  channel count) is self-invalidating -- the changed bytes produce a different content-hash key,
  so old entries just go inert, never served stale. Manual invalidation (delete `.feat` files or
  the whole directory) only takes effect for a NEW server process; an already-running process's
  RAM tier keeps serving what it already loaded regardless of disk-side deletions.
- **`/mnt/<drive>` (Windows-drive-backed) I/O inside WSL2 can be slow enough to look like a
  hang.** This audit observed a `pytest` run against this repository checked out under
  `/mnt/d/...` sit for over ten minutes with almost no CPU time consumed (I/O-wait, process state
  `D`) before a clean rerun completed in 60 s. If a run seems stuck with low CPU usage, check
  `ps aux` for the process's state before assuming a real hang; consider checking the repository
  out onto the WSL2 ext4 filesystem (`~/...`) rather than a `/mnt/<drive>` mount if this recurs.
- **WSL2's `/tmp` does not survive VM idle-shutdown.** A background job that logs to `/tmp/...`
  across two separate `wsl.exe` invocations can lose its log silently if the VM was torn down and
  restarted in between (`/tmp` is `tmpfs`; `/home/<user>` is the persistent ext4-backed disk and
  survives). Log long-running reproduction steps to a path under your own home directory or a
  host-mounted drive, not `/tmp`, if you need the log to outlive a single `wsl.exe` process.

## 14. Not reproducible without contacting us

Everything in this repository's own pipeline is reproducible from public sources plus this
repository's vendored lock files, with two narrow, honestly-disclosed exceptions:

- **Exact HF LFS per-shard hashes for M3-SLU's 155 audio parquet shards and AMI's 171 individual
  WAVs.** `scripts/data/datasets.lock.json`'s own `hash_coverage_note` fields say so explicitly:
  the umbrella lock records an aggregate manifest hash and file-count/total-size closure for these
  subtrees, but not a per-file hash for every payload file (the per-shard LFS SHA-256 values live
  only in the umbrella's private acquisition receipt, never extracted into this repository).
  `verify.py` falls back to file-count + total-size closure for exactly these two subtrees. This
  is a **lock-coverage gap, not a missing-bytes problem** -- the datasets themselves are fully
  public and independently downloadable; only byte-exact per-file verification of these two
  specific large multi-file payloads is unavailable outside the primary dev machine.
- **The compiled binary bytes** of `llama-server` and `nemo-speech` (sha256es recorded in every
  runtime-identity receipt as "informational" per their own README notes) are toolchain-dependent
  and were never claimed to be reproducible byte-for-byte -- only the source tips they were built
  from are pinned and reproducible (Sections 3-4). If a receipt's binary hash does not match yours
  after following Sections 3-4 exactly, that is expected toolchain variance, not a sign anything
  applied incorrectly.

No pipeline STEP in this repository depends on owner-private data, an internal service, or a
credential you do not have. If you hit a wall this document does not explain, it is a gap in this
document, not a deliberately withheld step -- open an issue or ask directly.
