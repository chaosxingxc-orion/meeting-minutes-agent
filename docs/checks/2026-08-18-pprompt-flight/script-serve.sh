#!/usr/bin/env bash
# Foreground llama-server (the live-wrapper background Bash job holds it;
# setsid/nohup do not survive on this machine). Same binary/flags as the
# flown P-ATTR smoke: -c 49152 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0.
set -euo pipefail
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/ppromptfly/env.sh

if pgrep -x llama-server >/dev/null 2>&1; then
  echo "REFUSING: an llama-server process is already running" >&2
  pgrep -ax llama-server >&2
  exit 1
fi

# cwd matters: the 17,920-byte stub resolves its .so siblings from here.
cd "$(dirname "$LLAMA_BIN")"
echo "starting llama-server at $(date -u +%H:%M:%SZ), cache=$LLAMA_MTMD_FEAT_CACHE_DIR"
exec ./llama-server \
  --host 127.0.0.1 --port "$PORT" \
  -m "$MODEL_GGUF" \
  --mmproj "$MMPROJ_GGUF" \
  -c 49152 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0 \
  >> "$RUN_DIR/server.log" 2>&1
