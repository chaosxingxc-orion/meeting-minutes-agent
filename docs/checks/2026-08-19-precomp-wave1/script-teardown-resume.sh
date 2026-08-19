#!/usr/bin/env bash
# Clean llama-server shutdown after the PRECOMP wave-1 resume pass.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp/env.sh
exec > "$LOGS/teardown-resume.log" 2>&1

echo "=== teardown $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "cache before shutdown: entries=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l) bytes=$(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')"
pgrep -ax llama-server || echo "(no llama-server running)"

pkill -TERM -x llama-server 2>/dev/null
for i in $(seq 1 60); do
  pgrep -x llama-server >/dev/null 2>&1 || break
  sleep 1
done
if pgrep -x llama-server >/dev/null 2>&1; then
  echo "SIGTERM did not stop it after 60 s; escalating to SIGKILL"
  pkill -KILL -x llama-server 2>/dev/null
  sleep 3
fi
pgrep -ax llama-server && echo "STILL RUNNING" || echo "llama-server stopped"

echo "cache after shutdown: entries=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l) bytes=$(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')"
echo "--- server.log tail (operational lines only; no reply content is logged by llama-server at this verbosity) ---"
grep -Ei 'error|failed|abort|assert|out of memory|terminate' "$LOGS/server.log" | tail -20 || echo "(no error lines)"
echo "server.log lines: $(wc -l < "$LOGS/server.log")"
nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu --format=csv,noheader
echo "--- releasing the SM clock floor is the operator's call; leaving -lgc as set ---"
echo "=== teardown end $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
