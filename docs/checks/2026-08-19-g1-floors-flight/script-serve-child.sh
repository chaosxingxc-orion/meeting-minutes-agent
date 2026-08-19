#!/usr/bin/env bash
# The llama-server argv, as ONE executable, so scripts/run_g1.py's
# --server-cmd (argparse nargs="+", which would swallow the server's own
# "--host"/"-m" flags as its own options) can name it in a single token and
# still start the pinned server as a DIRECT CHILD of the chunk invocation
# (g1_campaign.ManagedLlamaServer -> subprocess.Popen -> this script -> exec,
# so the PID ManagedLlamaServer.terminate() signals IS llama-server).
#
# Same pinned binary and flags as the flown P-ATTR / P-PROMPT / PRECOMP /
# G1-PATH / G1-PATH2 passes: -c 49152 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0.
set -eu
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1floors/env.sh

# cwd matters: the 17,920-byte stub resolves its .so siblings from here.
cd "$(dirname "$LLAMA_BIN")"
exec ./llama-server \
  --host 127.0.0.1 --port "$PORT" \
  -m "$MODEL_GGUF" \
  --mmproj "$MMPROJ_GGUF" \
  -c 49152 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0 \
  >> "$LOGS/server.log" 2>&1
