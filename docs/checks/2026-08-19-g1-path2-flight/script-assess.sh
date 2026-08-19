#!/usr/bin/env bash
# Point-in-time state of the G1-PATH2 flight. Usage: assess.sh <chunk-index>
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1path2/env.sh
N="${1:-0}"
echo "=== assess $(date -u +%H:%M:%SZ) chunk=$N ==="
echo "--- procs ---"
pgrep -ax llama-server || echo "llama-server: GONE"
pgrep -af run_g1.py || echo "run_g1: GONE"
echo "--- item receipts ---"
ls "$RUN_DIR/receipts" 2>/dev/null | sort
echo "count: $(ls "$RUN_DIR/receipts" 2>/dev/null | wc -l)"
echo "--- chunk receipts ---"
ls "$RUN_DIR/chunks" 2>/dev/null | sort
echo "--- response sink line counts (lines only; reply text never read) ---"
for f in "$RUN_DIR"/responses/*.jsonl; do [ -e "$f" ] && echo "$(basename "$f"): $(wc -l < "$f") lines"; done
echo "--- runner log tail ---"
tail -30 "$LOGS/runner-chunk$N.log" 2>/dev/null
echo "--- wrapper log tail ---"
tail -25 "$LOGS/fly-chunk$N-wrapper.log" 2>/dev/null
echo "--- progress tail ---"
tail -8 "$LOGS/progress-chunk$N.log" 2>/dev/null
echo "--- cache ---"
echo "entries=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l) bytes=$(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')"
echo "--- gpu ---"
nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,power.draw --format=csv,noheader
echo "--- repo dirty ---"
git -C "$REPO" status --porcelain | head -30
