#!/usr/bin/env bash
# Shared environment for the G1-PATH RE-RUN (path2) flight (2026-08-19):
# structural re-validation of the 8aedcb9 per-meeting QA routing + real GPU
# accounting fix, at the REGISTERED N=200/seed=20260818 QA cap (no override).
# Same pinned llama.cpp build, same q4km GGUF pair, same WARM per-dataset
# feature cache ami-q4km as PRECOMP wave-1, the G1 VAD supplement, and G1-PATH.
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

export SP=/mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1path2
export LOGS="$SP/logs"
export YIELD_FILE="$SP/G1PATH2_YIELD"

# The runner's --out-dir lives on the DATA root, never in Git: it holds the
# per-contact response sink (responses/chunk*-responses.jsonl), a raw trace
# prohibited from the repository. A FRESH run dir (path2): the first PATH
# flight's receipts must not satisfy --resume for this re-validation.
export RUN_DIR="$DATA/derived/meeting-minutes/g1/runs/2026-08-19-g1-path2"
export ARCHIVE_DIR="$REPO/docs/checks/2026-08-19-g1-path2-flight"
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

# G1-PATH's own registered envelope (floors prereg SS5: "~250 requests,
# <=0.5 GPU-h"), enforced fail-closed as this flight's G1Budget rather than
# the whole campaign's 2,900/6.0/8.0 -- a pathfinder must not be able to
# spend the floors campaign's ceiling. The QA head flies at the REGISTERED
# cap this time: the 8aedcb9 fix routes per meeting (ES2011a's own 7
# questions x 2 QA arms, IS1008a 0), so the registered cap fits the envelope.
export PATH_MAX_CALLS=250
export PATH_MAX_GPU_HOURS=0.5
export PATH_MAX_WALL_HOURS=2.0

mkdir -p "$LOGS" "$RUN_DIR"
