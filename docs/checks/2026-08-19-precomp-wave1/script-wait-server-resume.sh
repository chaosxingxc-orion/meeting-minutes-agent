#!/usr/bin/env bash
# Block until llama-server answers /health, then report identity + cache state.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp/env.sh

for i in $(seq 1 120); do
  if curl -sf "$BASE_URL/health" >/dev/null 2>&1; then
    echo "SERVER-HEALTHY after $((i*5))s at $(date -u +%H:%M:%SZ)"
    curl -s "$BASE_URL/health"
    echo
    pgrep -ax llama-server
    nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,power.draw --format=csv,noheader
    echo "server.log lines: $(wc -l < "$LOGS/server.log")"
    grep -Ei 'error|failed|abort|out of memory' "$LOGS/server.log" | tail -5 || true
    exit 0
  fi
  sleep 5
done
echo "SERVER-NOT-READY after 600s"
tail -30 "$LOGS/server.log"
exit 1
