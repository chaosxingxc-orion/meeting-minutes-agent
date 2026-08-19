#!/usr/bin/env bash
# PRECOMP wave-1 production pass: the dev-18 meetings, one run_precomp.py
# invocation per meeting so the YIELD protocol can stop cleanly at a meeting
# boundary (the runner exposes no in-flight stop hook). --resume makes a
# re-entry skip every meeting whose receipt is complete+verified.
#
# ALL output goes to files: the Windows console can detach mid-flight on this
# machine, and a write to a dead pty must never be able to kill the loop
# (the pprompt/diar flights' own fly-wrapper.log pattern).
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp/env.sh
exec > "$LOGS/fly-wrapper.log" 2>&1

MEETINGS="ES2011a ES2011b ES2011c ES2011d IB4001 IB4002 IB4003 IB4004 IB4010 IB4011 IS1008a IS1008b IS1008c IS1008d TS3004a TS3004b TS3004c TS3004d"
PROGRESS="$LOGS/progress.log"
: > "$PROGRESS"

echo "=== PRECOMP wave-1 start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "repo HEAD: $(git -C "$REPO" rev-parse HEAD)"
echo "out-dir:   $OUT_DIR"
echo "cache:     $LLAMA_MTMD_FEAT_CACHE_DIR"

# --- GPU health sampler (30 s), mirrors the pattr/pprompt flights ----------
GPUHEALTH="$LOGS/gpu-health.log"
: > "$GPUHEALTH"
(
  while true; do
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $(nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu,power.draw,clocks_throttle_reasons.active --format=csv,noheader,nounits 2>/dev/null)" >> "$GPUHEALTH"
    sleep 30
  done
) &
SAMPLER_PID=$!

# --- server readiness ------------------------------------------------------
echo "--- waiting for llama-server at $BASE_URL ---"
ready=0
for i in $(seq 1 180); do
  if curl -sf "$BASE_URL/health" >/dev/null 2>&1; then ready=1; break; fi
  sleep 5
done
if [ "$ready" != "1" ]; then
  echo "SERVER NOT READY after 900 s -- aborting" | tee -a "$PROGRESS"
  kill $SAMPLER_PID 2>/dev/null
  echo "FLY-DONE state=ABORTED-NO-SERVER" | tee -a "$PROGRESS"
  exit 1
fi
echo "server healthy at $(date -u +%H:%M:%SZ)"

CACHE_BEFORE_N=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)
CACHE_BEFORE_B=$(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')
echo "featcache before: entries=$CACHE_BEFORE_N bytes=$CACHE_BEFORE_B" | tee -a "$PROGRESS"

mkdir -p "$OUT_DIR/transport-receipts" "$LOGS/meetings"

STATE=COMPLETE
STOP_REASON=""
DONE_LIST=""

for m in $MEETINGS; do
  # -- YIELD protocol: check BEFORE each meeting ---------------------------
  if [ -e "$YIELD_FILE" ]; then
    echo "$(date -u +%H:%M:%SZ) YIELD file present before $m -- stopping cleanly" | tee -a "$PROGRESS"
    STATE=YIELDED
    STOP_REASON="operator yield (PRECOMP_YIELD stop-file present before $m)"
    break
  fi

  # -- wave-cumulative budget guard (see budget_ledger.py) -----------------
  LEDGER=$("$PY" "$SP/budget_ledger.py" 1 "$OUT_DIR")
  LEDGER_RC=$?
  echo "$(date -u +%H:%M:%SZ) ledger before $m: $LEDGER" >> "$PROGRESS"
  if [ "$LEDGER_RC" = "3" ]; then
    echo "$(date -u +%H:%M:%SZ) BUDGET STOP before $m: $LEDGER" | tee -a "$PROGRESS"
    STATE=BUDGET-STOPPED
    STOP_REASON="wave-cumulative ceiling reached before $m: $LEDGER"
    break
  fi

  echo "--- $m start $(date -u +%Y-%m-%dT%H:%M:%SZ) ---" | tee -a "$PROGRESS"
  T0=$(date +%s)
  PYTHONPATH="$REPO/src" "$PY" "$REPO/scripts/run_precomp.py" \
    --wave 1 \
    --data-dir "$DATA" \
    --meetings "$m" \
    --arm-config "$ARM_CONFIG" \
    --server-url "$BASE_URL" \
    --model-path "$MODEL_GGUF" \
    --model-sha256 "$MODEL_SHA256" \
    --slots 1 \
    --out-dir "$OUT_DIR" \
    --workers 8 \
    --featcache-dataset "$FEATCACHE_DATASET" \
    --encoder "$FEATCACHE_ENCODER" \
    --timeout-seconds 600 \
    --resume > "$LOGS/meetings/$m.log" 2>&1
  RC=$?
  T1=$(date +%s)

  # preserve this meeting's transport ledger before the next invocation
  # overwrites the single transport-receipt.json path
  if [ -f "$OUT_DIR/transport-receipt.json" ]; then
    cp "$OUT_DIR/transport-receipt.json" "$OUT_DIR/transport-receipts/$m.json"
  fi

  OKFLAG=$("$PY" -c "
import json,sys
from pathlib import Path
p=Path(sys.argv[1])/'receipts'/(sys.argv[2]+'-receipt.json')
try:
    d=json.loads(p.read_text(encoding='utf-8'))
except Exception as e:
    print('NO-RECEIPT'); raise SystemExit(0)
print('ok' if d.get('ok') else 'ERR:'+str(d.get('error'))[:200])
" "$OUT_DIR" "$m")

  echo "$(date -u +%H:%M:%SZ) $m rc=$RC wall=$((T1-T0))s receipt=$OKFLAG" | tee -a "$PROGRESS"
  if [ "$OKFLAG" = "ok" ]; then
    DONE_LIST="$DONE_LIST $m"
  fi
done

kill $SAMPLER_PID 2>/dev/null
wait $SAMPLER_PID 2>/dev/null

CACHE_AFTER_N=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)
CACHE_AFTER_B=$(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')
echo "featcache after: entries=$CACHE_AFTER_N bytes=$CACHE_AFTER_B (delta entries=$((CACHE_AFTER_N-CACHE_BEFORE_N)) bytes=$((CACHE_AFTER_B-CACHE_BEFORE_B)))" | tee -a "$PROGRESS"

echo "--- aggregate wave summary ---"
"$PY" "$SP/aggregate.py" 1 "$OUT_DIR" "$STOP_REASON" 2>&1 | tee -a "$PROGRESS"

echo "--- final ledger ---"
"$PY" "$SP/budget_ledger.py" 1 "$OUT_DIR" 2>&1 | tee -a "$PROGRESS"

echo "--- derived-artefact hashes (E: run root; bytes never committed) ---"
( cd "$DATA/derived/meeting-minutes/precomp" && find . -type f -name '*.rttm' | sort | sed 's|^\./||' | xargs -r sha256sum ) > "$LOGS/rttm-artefacts.sha256"
wc -l "$LOGS/rttm-artefacts.sha256"
( cd "$DATA/derived/meeting-minutes/precomp" && find . -type f -name '*.wav' | wc -l ) > "$LOGS/slice-wav-count.txt"
cat "$LOGS/slice-wav-count.txt"

echo "--- post-run GPU snapshot ---"
nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu --format=csv,noheader

echo "completed meetings:$DONE_LIST" | tee -a "$PROGRESS"
echo "=== PRECOMP wave-1 end $(date -u +%Y-%m-%dT%H:%M:%SZ) state=$STATE ==="
echo "FLY-DONE state=$STATE" | tee -a "$PROGRESS"
