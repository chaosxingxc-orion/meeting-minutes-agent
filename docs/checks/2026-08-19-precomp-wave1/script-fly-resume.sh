#!/usr/bin/env bash
# PRECOMP wave-1 RESUME pass: the nine untouched dev-18 meetings, in ONE
# run_precomp.py invocation. The per-meeting invocation loop the first pass
# needed is retired by commit e4e18c4: --stop-file gives the yield protocol a
# native in-flight hook (checked before every meeting) and PrecompBudget
# precharges wave-cumulative usage from the receipts already on disk, so the
# registered WAVE ceilings hold across both passes without an external ledger.
#
# ALL output goes to files: the Windows console can detach mid-flight on this
# machine, and a write to a dead pty must never be able to kill the run.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp/env.sh
exec > "$LOGS/fly-resume-wrapper.log" 2>&1

REMAINING="IB4011 IS1008a IS1008b IS1008c IS1008d TS3004a TS3004b TS3004c TS3004d"
PROGRESS="$LOGS/progress-resume.log"
: > "$PROGRESS"

echo "=== PRECOMP wave-1 RESUME start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "repo HEAD: $(git -C "$REPO" rev-parse HEAD)"
echo "out-dir:   $OUT_DIR"
echo "cache:     $LLAMA_MTMD_FEAT_CACHE_DIR"
echo "stop-file: $YIELD_FILE"
echo "remaining: $REMAINING"

# --- GPU health sampler (30 s) ---------------------------------------------
GPUHEALTH="$LOGS/gpu-health-resume.log"
: > "$GPUHEALTH"
(
  while true; do
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $(nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu,power.draw,clocks_throttle_reasons.active --format=csv,noheader,nounits 2>/dev/null)" >> "$GPUHEALTH"
    sleep 30
  done
) &
SAMPLER_PID=$!

# --- progress watcher (60 s) ------------------------------------------------
# The runner prints nothing per stage, so an external watcher makes the pass
# observable: receipts landed, feature-cache growth, GPU state. Silence must
# never look like success.
(
  while true; do
    N_RCPT=$(ls "$OUT_DIR/receipts" 2>/dev/null | wc -l)
    N_CACHE=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f 2>/dev/null | wc -l)
    GPU=$(nvidia-smi --query-gpu=utilization.gpu,clocks.sm,power.draw --format=csv,noheader,nounits 2>/dev/null | tr '\n' ' ')
    LATEST=$(ls -t "$OUT_DIR/receipts" 2>/dev/null | head -1)
    echo "$(date -u +%H:%M:%SZ) WATCH receipts=$N_RCPT latest=$LATEST cache_entries=$N_CACHE gpu=[$GPU]" >> "$PROGRESS"
    sleep 60
  done
) &
WATCHER_PID=$!

cleanup() { kill $SAMPLER_PID $WATCHER_PID 2>/dev/null; wait $SAMPLER_PID $WATCHER_PID 2>/dev/null; }

# --- server readiness ------------------------------------------------------
echo "--- waiting for llama-server at $BASE_URL ---"
ready=0
for i in $(seq 1 180); do
  if curl -sf "$BASE_URL/health" >/dev/null 2>&1; then ready=1; break; fi
  sleep 5
done
if [ "$ready" != "1" ]; then
  echo "SERVER NOT READY after 900 s -- aborting" | tee -a "$PROGRESS"
  cleanup
  echo "FLY-DONE state=ABORTED-NO-SERVER" | tee -a "$PROGRESS"
  exit 1
fi
echo "server healthy at $(date -u +%H:%M:%SZ)" | tee -a "$PROGRESS"

CACHE_BEFORE_N=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)
CACHE_BEFORE_B=$(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')
RCPT_BEFORE=$(ls "$OUT_DIR/receipts" | wc -l)
echo "featcache before: entries=$CACHE_BEFORE_N bytes=$CACHE_BEFORE_B; receipts before: $RCPT_BEFORE" | tee -a "$PROGRESS"

mkdir -p "$OUT_DIR/transport-receipts"

echo "--- ledger before the resume (operator cross-check of the native precharge) ---" | tee -a "$PROGRESS"
"$PY" "$SP/budget_ledger.py" 1 "$OUT_DIR" 2>&1 | tee -a "$PROGRESS"

echo "--- single invocation: run_precomp.py --wave 1 --resume --stop-file ... ---" | tee -a "$PROGRESS"
T0=$(date +%s)
PYTHONPATH="$REPO/src" "$PY" "$REPO/scripts/run_precomp.py" \
  --wave 1 \
  --data-dir "$DATA" \
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
  --stop-file "$YIELD_FILE" \
  --resume > "$LOGS/resume-runner.log" 2>&1
RC=$?
T1=$(date +%s)
echo "$(date -u +%H:%M:%SZ) runner rc=$RC wall=$((T1-T0))s" | tee -a "$PROGRESS"

cleanup

# preserve this invocation's transport ledger under the per-pass name; the
# first pass's per-meeting ledgers stay byte-intact.
if [ -f "$OUT_DIR/transport-receipt.json" ]; then
  cp "$OUT_DIR/transport-receipt.json" "$OUT_DIR/transport-receipts/resume-2026-08-19.json"
  rm -f "$OUT_DIR/transport-receipt.json"
fi

# --- per-meeting outcome of the nine ---------------------------------------
STATE=COMPLETE
STOP_REASON=""
DONE_LIST=""
MISSING_LIST=""
for m in $REMAINING; do
  OKFLAG=$("$PY" -c "
import json,sys
from pathlib import Path
p=Path(sys.argv[1])/'receipts'/(sys.argv[2]+'-receipt.json')
try:
    d=json.loads(p.read_text(encoding='utf-8'))
except Exception:
    print('NO-RECEIPT'); raise SystemExit(0)
print('ok' if d.get('ok') else 'ERR:'+str(d.get('error'))[:300])
" "$OUT_DIR" "$m")
  echo "$(date -u +%H:%M:%SZ) $m receipt=$OKFLAG" | tee -a "$PROGRESS"
  if [ "$OKFLAG" = "ok" ]; then DONE_LIST="$DONE_LIST $m"; else MISSING_LIST="$MISSING_LIST $m"; STATE=INCOMPLETE; fi
done

if [ -e "$YIELD_FILE" ]; then
  STATE=YIELDED
  STOP_REASON="operator yield (stop-file present at $YIELD_FILE); not run:$MISSING_LIST"
elif [ "$STATE" != "COMPLETE" ]; then
  STOP_REASON="resume pass ended without a complete receipt for:$MISSING_LIST (runner rc=$RC)"
fi

CACHE_AFTER_N=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)
CACHE_AFTER_B=$(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')
echo "featcache after: entries=$CACHE_AFTER_N bytes=$CACHE_AFTER_B (resume delta entries=$((CACHE_AFTER_N-CACHE_BEFORE_N)) bytes=$((CACHE_AFTER_B-CACHE_BEFORE_B)))" | tee -a "$PROGRESS"

echo "--- aggregate wave summary over ALL receipts ---"
"$PY" "$SP/aggregate_resume.py" 1 "$OUT_DIR" "$STOP_REASON" 2>&1 | tee -a "$PROGRESS"

echo "--- final ledger ---"
"$PY" "$SP/budget_ledger.py" 1 "$OUT_DIR" 2>&1 | tee -a "$PROGRESS"

echo "--- per-meeting table (all receipts) ---"
"$PY" "$SP/table.py" "$OUT_DIR" 2>&1 | tee -a "$PROGRESS"

echo "--- derived-artefact hashes (E: run root; bytes never committed) ---"
( cd "$DATA/derived/meeting-minutes/precomp" && find . -type f -name '*.rttm' | sort | sed 's|^\./||' | xargs -r sha256sum ) > "$LOGS/rttm-artefacts.sha256"
wc -l "$LOGS/rttm-artefacts.sha256"
( cd "$DATA/derived/meeting-minutes/precomp" && find . -type f -name '*.wav' | wc -l ) > "$LOGS/slice-wav-count.txt"
cat "$LOGS/slice-wav-count.txt"

echo "--- post-run GPU snapshot ---"
nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu --format=csv,noheader

echo "completed this pass:$DONE_LIST" | tee -a "$PROGRESS"
echo "=== PRECOMP wave-1 RESUME end $(date -u +%Y-%m-%dT%H:%M:%SZ) state=$STATE ==="
echo "FLY-DONE state=$STATE" | tee -a "$PROGRESS"
