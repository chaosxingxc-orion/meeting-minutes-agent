#!/usr/bin/env bash
# Shared environment for the PRECOMP wave-1 production pass (2026-08-19).
# Mirrors the flown P-PROMPT flight env (docs/checks/2026-08-18-pprompt-flight/script-env.sh)
# with the PRECOMP run dir. Same pinned llama.cpp build, same q4km GGUF pair,
# same WARM per-dataset feature cache ami-q4km (the cache later G1 experiments read).
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

export SP=/mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp
export LOGS="$SP/logs"
export YIELD_FILE=/mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/PRECOMP_YIELD

export RUN_DIR="$DATA/derived/meeting-minutes/precomp/runs/2026-08-19-precomp-wave1"
export OUT_DIR="$REPO/docs/checks/2026-08-19-precomp-wave1"
export ARM_CONFIG="$DATA/derived/meeting-minutes/diar-smoke/tooling/arm-config.json"

export LLAMA_DIR=/home/chao/llama.cpp-featcache
export LLAMA_BIN="$LLAMA_DIR/build/bin/llama-server"
export MODEL_DIR=/home/chao/models/qwen3-omni-30b-a3b-instruct-gguf-q4km
export MODEL_GGUF="$MODEL_DIR/Qwen3-Omni-30B-A3B-Instruct-Q4_K_M.gguf"
export MMPROJ_GGUF="$MODEL_DIR/mmproj-Qwen3-Omni-30B-A3B-Instruct-bf16.gguf"
export MODEL_SHA256=0751c279498785c0b07130ae7748038d1e2cfd04617928e4557063807f98066d
export MMPROJ_SHA256=f0dfe825fb692d426362b1ac79678fc08daa4758f7151526cad110515f122883
export LLAMA_BIN_SHA256=097c96ec5a3f576f378d4d5e103928bf070647fdcc1f015eacb839503e121c68
export DIAR_BIN=/home/chao/nemo-speech.cpp/build/cuda-diar/bin/nemo-speech
export DIAR_BIN_SHA256=1a3e3f4fe7db4c48e5d6e44a76d5adf2bbfef80024c023b0eab2766eb61aca78
export DIAR_GGUF="$DATA/models/diar-sortformer-4spk-v2/diar_streaming_sortformer_4spk-v2.q8_0.gguf"
export DIAR_GGUF_SHA256=0679cfeb1ce356d0dea9470b31274f4bfc7eb927497d82005483770666da998a

export PORT=8080
export BASE_URL="http://127.0.0.1:${PORT}"
export PY=/home/chao/.venvs/speechrl/bin/python

mkdir -p "$LOGS" "$RUN_DIR"
