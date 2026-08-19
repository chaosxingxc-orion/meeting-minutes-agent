#!/usr/bin/env bash
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp/env.sh
echo "=== assess $(date -u +%H:%M:%SZ) ==="
echo "--- procs ---"
pgrep -ax llama-server || echo "llama-server: GONE"
pgrep -af run_precomp.py || echo "run_precomp: GONE"
pgrep -af fly-resume || echo "fly-resume wrapper: GONE"
echo "--- receipts ---"
ls "$OUT_DIR/receipts" | sort
echo "count: $(ls "$OUT_DIR/receipts" | wc -l)"
echo "--- runner log tail ---"
tail -40 "$LOGS/resume-runner.log"
echo "--- wrapper log tail ---"
tail -30 "$LOGS/fly-resume-wrapper.log"
echo "--- progress tail ---"
tail -8 "$LOGS/progress-resume.log"
echo "--- cache ---"
echo "entries=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l) bytes=$(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')"
echo "--- yield file ---"
ls -la "$YIELD_FILE" 2>&1
echo "--- repo dirty ---"
git -C "$REPO" status --porcelain | head -30
