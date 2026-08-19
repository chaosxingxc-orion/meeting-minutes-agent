#!/usr/bin/env bash
# Point-in-time state of the G1 VAD supplement. Usage: assess.sh A|B
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1sup/env.sh
L="${1:-A}"
echo "=== assess $(date -u +%H:%M:%SZ) pass=$L ==="
echo "--- procs ---"
pgrep -ax llama-server || echo "llama-server: GONE"
pgrep -af run_precomp.py || echo "run_precomp: GONE"
pgrep -af "fly.sh" || echo "fly wrapper: GONE"
echo "--- receipts ---"
ls "$OUT_DIR/receipts" 2>/dev/null | sort
echo "count: $(ls "$OUT_DIR/receipts" 2>/dev/null | wc -l)"
echo "--- vad artefacts ---"
echo "manifests: $(ls "$VAD_MANIFEST_DIR" 2>/dev/null | wc -l)"
echo "slice wavs: $(find "$VAD_SLICE_ROOT" -type f -name '*.wav' 2>/dev/null | wc -l)"
echo "--- runner log tail ---"
tail -30 "$LOGS/runner-pass$L.log" 2>/dev/null
echo "--- wrapper log tail ---"
tail -25 "$LOGS/fly-pass$L-wrapper.log" 2>/dev/null
echo "--- progress tail ---"
tail -8 "$LOGS/progress-pass$L.log" 2>/dev/null
echo "--- cache ---"
echo "entries=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l) bytes=$(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')"
echo "--- gpu ---"
nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,power.draw --format=csv,noheader
echo "--- ledger ---"
"$PY" "$SP/ledger.py" "$OUT_DIR"
echo "--- repo dirty ---"
git -C "$REPO" status --porcelain | head -30
