#!/usr/bin/env bash
# Fly all 14 P-PROMPT arms sequentially against one slot, mirroring
# pattrfly/fly_arm.sh per arm. Aborts on the first structural failure.
# Per-arm CallBudget caps sit below the registered global ceilings:
# 14 arms x 26 calls = 364 <= 380; 14 x 2,500 audio-s = 35,000 <= 35,000.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/ppromptfly/env.sh
SCRATCH=/mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad

WLOG="$RUN_DIR/fly-wrapper.log"
echo "=== fly_all start $(date -u +%FT%TZ) ===" >> "$WLOG"
TOTAL_START=$(date +%s)

cd "$REPO"
for ARM in $PPROMPT_ARMS; do
  RESP="$RUN_DIR/${ARM}-responses.jsonl"
  RECEIPT="$RUN_DIR/${ARM}-receipt.json"
  LOG="$RUN_DIR/${ARM}-launcher.log"

  echo "=== $ARM start $(date -u +%H:%M:%SZ) ===" | tee -a "$LOG" >> /dev/null
  nvidia-smi --query-gpu=clocks.sm,temperature.gpu,power.draw,utilization.gpu,memory.used,pstate \
    --format=csv,noheader >> "$LOG" 2>&1
  CACHE_BEFORE=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)
  START=$(date +%s)

  python scripts/launch_pprompt_sweep.py \
    --data-dir "$SPEECHRL_DATA_DIR" \
    --pattr-manifest "$MANIFEST" \
    --binding "$BINDING" \
    --arm "$ARM" \
    --base-url "$BASE_URL" \
    --model-path "$MODEL_GGUF" \
    --model-sha256 0751c279498785c0b07130ae7748038d1e2cfd04617928e4557063807f98066d \
    --slots 1 \
    --max-calls 26 \
    --max-audio-seconds 2500 \
    --temperature 0 --seed 20260818 --max-tokens 1024 \
    --timeout-seconds 420 \
    --progress-every 8 \
    --responses-out "$RESP" \
    --receipt-out "$RECEIPT" >> "$LOG" 2>&1
  RC=$?

  END=$(date +%s)
  CACHE_AFTER=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)
  {
    echo "=== $ARM done $(date -u +%H:%M:%SZ) rc=$RC ==="
    echo "wall_seconds=$((END - START))"
    python "$SCRATCH/count_records.py" "$RESP" 2>/dev/null || echo "records: responses file unreadable"
    echo "featcache_entries: $CACHE_BEFORE -> $CACHE_AFTER"
    nvidia-smi --query-gpu=clocks.sm,temperature.gpu,power.draw,utilization.gpu,memory.used,pstate \
      --format=csv,noheader
  } >> "$LOG" 2>&1
  echo "$ARM rc=$RC wall=$((END - START))s cache $CACHE_BEFORE->$CACHE_AFTER" >> "$WLOG"

  if [ "$RC" -ne 0 ]; then
    echo "=== ABORT after $ARM rc=$RC $(date -u +%FT%TZ) ===" >> "$WLOG"
    exit "$RC"
  fi
done

TOTAL_END=$(date +%s)
echo "=== fly_all done $(date -u +%FT%TZ) total_wall_seconds=$((TOTAL_END - TOTAL_START)) ===" >> "$WLOG"
