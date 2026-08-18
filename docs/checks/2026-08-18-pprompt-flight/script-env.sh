#!/usr/bin/env bash
# Shared environment for the P-PROMPT template-and-arrangement sweep flight (2026-08-18).
# Mirrors pattrfly/env.sh (the flown P-ATTR precedent) with the P-PROMPT run dir + binding.
export PYTHONDONTWRITEBYTECODE=1
export REPO=/mnt/d/chao_workspace/exploring-l4-intelligence/papers/meeting-minutes-agent
export PYTHONPATH="$REPO/src"
export SPEECHRL_DATA_DIR=/mnt/e/chao_workspace/exploring-l4-intelligence/speechrl-data

# Same WARM per-dataset cache dir the P-ATTR smoke created (879 entries).
# NEVER q4km / slurp-q4km / audio2tool-q4km.
export LLAMA_MTMD_FEAT_CACHE_DIR=/home/chao/feat-cache/ami-q4km
export SAEA_FEAT_CACHE_DIR=/home/chao/feat-cache/ami-q4km

export RUN_DIR="$SPEECHRL_DATA_DIR/derived/meeting-minutes/pprompt-sweep/runs/2026-08-18-pprompt-sweep"
export LLAMA_DIR=/home/chao/llama.cpp-featcache
export LLAMA_BIN="$LLAMA_DIR/build/bin/llama-server"
export MODEL_DIR=/home/chao/models/qwen3-omni-30b-a3b-instruct-gguf-q4km
export MODEL_GGUF="$MODEL_DIR/Qwen3-Omni-30B-A3B-Instruct-Q4_K_M.gguf"
export MMPROJ_GGUF="$MODEL_DIR/mmproj-Qwen3-Omni-30B-A3B-Instruct-bf16.gguf"
export PORT=8080
export BASE_URL="http://127.0.0.1:${PORT}"
export MANIFEST="$REPO/configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json"
export BINDING="$REPO/configs/probes/pprompt/2026-08-18-pprompt-binding.json"
export PPROMPT_ARMS="T1-A1 T1-A2 T1-A3 T2-A1 T2-A2 T2-A3 T3-A1 T3-A2 T3-A3 T4-A1 T4-A2 T4-A3 X1 X2"

source ~/.venvs/speechrl/bin/activate
mkdir -p "$RUN_DIR"
