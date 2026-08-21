#!/usr/bin/env bash
set -euo pipefail

export LLAMA_MTMD_FEAT_CACHE_DIR=/home/yansuqing/.cache/meeting-minutes/e4-disjoint-dir-q4km
mkdir -p "$LLAMA_MTMD_FEAT_CACHE_DIR"
cd /home/yansuqing/llama.cpp-featcache/build/bin

exec ./llama-server \
  --host 127.0.0.1 \
  --port 8080 \
  -m /home/yansuqing/models/qwen3-omni-30b-a3b-instruct/Qwen3-Omni-30B-A3B-Instruct-Q4_K_M.gguf \
  --mmproj /home/yansuqing/models/qwen3-omni-30b-a3b-instruct/mmproj-Qwen3-Omni-30B-A3B-Instruct-Q8_0.gguf \
  -c 16384 \
  -np 1 \
  -fa on \
  -ngl 999 \
  -ctk q8_0 \
  -ctv q8_0
