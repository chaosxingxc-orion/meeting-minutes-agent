#!/usr/bin/env bash
# Shared environment for the G1 VAD SUPPLEMENT production pass (2026-08-19).
# Same pinned llama.cpp build, same q4km GGUF pair, same WARM per-dataset
# feature cache ami-q4km as the PRECOMP wave-1 pass
# (docs/checks/2026-08-19-precomp-wave1/script-env.sh), with the supplement's
# own out-dir and its own registered ceilings profile (g1-supplement).
# No diar contact: --turn-sources vad never runs the pinned Arm B tool.
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

export SP=/mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1sup
export LOGS="$SP/logs"
export YIELD_FILE="$SP/G1SUP_YIELD"

export OUT_DIR="$REPO/docs/checks/2026-08-19-g1-supplement"
export DERIVED_ROOT="$DATA/derived/meeting-minutes/precomp"
export VAD_SLICE_ROOT="$DERIVED_ROOT/slices/vad"
export VAD_MANIFEST_DIR="$DERIVED_ROOT/slices/vad-manifest"

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

# Roster split: two invocations, each far inside the ~50 min cap and the
# 60 min harness reap window (wave-1 lesson). Pass A is the wave-1 first-pass
# nine, pass B the resume nine -- identical roster, VAD turn source only.
export PASS_A_MEETINGS="ES2011a ES2011b ES2011c ES2011d IB4001 IB4002 IB4003 IB4004 IB4010"
export PASS_B_MEETINGS="IB4011 IS1008a IS1008b IS1008c IS1008d TS3004a TS3004b TS3004c TS3004d"

mkdir -p "$LOGS"
