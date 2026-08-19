#!/usr/bin/env bash
# Shared environment for the G1 FLOORS campaign flight (2026-08-19):
# dev-18, four arms, minutes+qa on Z-turn/Z-oracle, REGISTERED N=200 QA cap
# routed per meeting (8aedcb9), registered campaign ceilings 2,900 calls /
# 6.0 GPU-h / 8 h wall, resumable chunks. Same pinned llama.cpp build, same
# q4km GGUF pair, same WARM feature cache ami-q4km as every prior G1 flight.
export PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export REPO=/mnt/d/chao_workspace/exploring-l4-intelligence/papers/meeting-minutes-agent
export PYTHONPATH="$REPO/src"
export SPEECHRL_DATA_DIR=/mnt/e/chao_workspace/exploring-l4-intelligence/speechrl-data
export DATA="$SPEECHRL_DATA_DIR"

# NEVER q4km / slurp-q4km / audio2tool-q4km.
export FEATCACHE_DATASET=ami
export FEATCACHE_ENCODER=q4km
export LLAMA_MTMD_FEAT_CACHE_DIR=/home/chao/feat-cache/ami-q4km
export SAEA_FEAT_CACHE_DIR=/home/chao/feat-cache/ami-q4km

export SCRATCH=/mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad
export SP="$SCRATCH/g1floors"
export LOGS="$SP/logs"
# The coordinator-owned stop-file (mission brief): checked by run_g1.py before
# every work item, and by the operator between chunks.
export YIELD_FILE="$SCRATCH/G1_YIELD"

# The runner's --out-dir lives on the DATA root, never in Git: it holds the
# per-contact response sink (responses/chunk*-responses.jsonl), a raw trace
# prohibited from the repository. Receipts accumulate here across ALL chunk
# invocations (--resume + budget precharge read them back).
export RUN_DIR="$DATA/derived/meeting-minutes/g1/runs/2026-08-19-g1-floors"
export ARCHIVE_DIR="$REPO/docs/checks/2026-08-19-g1-floors-flight"
export DERIVED_ROOT="$DATA/derived/meeting-minutes/precomp"
export VAD_MANIFEST_DIR="$DERIVED_ROOT/slices/vad-manifest"
export MEETINGQA_ROOT="$DATA/datasets/meetingqa"
export AMI_ROOT="$DATA/datasets/ami"

export LLAMA_DIR=/home/chao/llama.cpp-featcache
export LLAMA_BIN="$LLAMA_DIR/build/bin/llama-server"
export MODEL_DIR=/home/chao/models/qwen3-omni-30b-a3b-instruct-gguf-q4km
export MODEL_GGUF="$MODEL_DIR/Qwen3-Omni-30B-A3B-Instruct-Q4_K_M.gguf"
export MMPROJ_GGUF="$MODEL_DIR/mmproj-Qwen3-Omni-30B-A3B-Instruct-bf16.gguf"
export MODEL_SHA256=0751c279498785c0b07130ae7748038d1e2cfd04617928e4557063807f98066d
export MMPROJ_SHA256=f0dfe825fb692d426362b1ac79678fc08daa4758f7151526cad110515f122883
export LLAMA_BIN_SHA256=097c96ec5a3f576f378d4d5e103928bf070647fdcc1f015eacb839503e121c68
export LLAMA_BUILD_COMMIT=5d9dfcb58ea860295da8fc93c7b5bed9e2c71151

export PORT=8080
export BASE_URL="http://127.0.0.1:${PORT}"
export PY=/home/chao/.venvs/speechrl/bin/python

# REGISTERED campaign ceilings (floors prereg SS6), enforced fail-closed by
# G1Budget with the now-real GPU accounting (8aedcb9).
export FLOORS_MAX_CALLS=2900
export FLOORS_MAX_GPU_HOURS=6.0
export FLOORS_MAX_WALL_HOURS=8.0

# Chunk sizing: the registered cap is <=50 min per chunk. P-PROMPT's planning
# basis is 3.7 s/request but G1-PATH measured ~3.9 s/contact, each chunk
# invocation additionally pays server startup, and G1-PATH2 observed one
# degenerate unbounded generation (max_tokens=None) burn a full transport
# timeout before its bounded retry succeeded (IS1008a Z-oracle transcribe
# slice 8: ~600 s attempt 1, ok on -r1). 1,800 s (30 min) estimated keeps a
# chunk's ACTUAL wall inside ~40-50 min even with a couple of such stalls --
# margin under both the 50-min chunk rule and the 60-min harness-reap window.
export FLOORS_MAX_CHUNK_WALL_SECONDS=1800

# Per-attempt transport timeout: 300 s (the TransportConfig default; G1-PATH
# ran an operator-chosen 600 s). Normal contacts run ~4 s and the largest
# minutes call tens of seconds, so 300 s keeps 3-4x headroom over the worst
# normal call while halving the GPU/wall cost of a degenerate-generation
# timeout before its retry.
export FLOORS_TIMEOUT_SECONDS=300

mkdir -p "$LOGS" "$RUN_DIR"
