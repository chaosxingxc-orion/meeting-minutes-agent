#!/usr/bin/env bash
# PRECOMP wave-1 resume, RETRY of the single meeting the reaped server cost.
#
# The resume pass ran 8/9 meetings clean and lost TS3004d to
# "URLError: <urlopen error [Errno 104] Connection reset by peer>": the harness
# reaps a background job at 60 min and the llama-server the pass depended on was
# one, killed mid-encode at 12:54:10Z (started 11:54:10Z). Nothing about the
# pinned identity, the data or the machinery changed; only the server process
# died. --resume re-runs exactly the meetings whose receipt is not ok, i.e.
# TS3004d alone.
#
# This script owns its own server as a CHILD process (started here, torn down
# here) so the whole retry lives inside one fresh harness window, and it repeats
# the full accounting tail so the landed artefacts describe the final state.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp/env.sh
exec > "$LOGS/fly-retry-wrapper.log" 2>&1

PROGRESS="$LOGS/progress-retry.log"
: > "$PROGRESS"

echo "=== PRECOMP wave-1 RETRY (TS3004d) start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "repo HEAD: $(git -C "$REPO" rev-parse HEAD)"

if pgrep -x llama-server >/dev/null 2>&1; then
  echo "REFUSING: an llama-server process is already running"
  pgrep -ax llama-server
  echo "FLY-DONE state=ABORTED-SERVER-ALREADY-RUNNING" | tee -a "$PROGRESS"
  exit 1
fi

# --- server as a child of this script --------------------------------------
( cd "$(dirname "$LLAMA_BIN")" && exec ./llama-server \
    --host 127.0.0.1 --port "$PORT" \
    -m "$MODEL_GGUF" \
    --mmproj "$MMPROJ_GGUF" \
    -c 49152 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0 \
    >> "$LOGS/server.log" 2>&1 ) &
SERVER_PID=$!
echo "$(date -u +%H:%M:%SZ) llama-server child pid=$SERVER_PID" | tee -a "$PROGRESS"

# --- GPU health sampler + progress watcher ---------------------------------
GPUHEALTH="$LOGS/gpu-health-retry.log"
: > "$GPUHEALTH"
(
  while true; do
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $(nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu,power.draw,clocks_throttle_reasons.active --format=csv,noheader,nounits 2>/dev/null)" >> "$GPUHEALTH"
    sleep 30
  done
) &
SAMPLER_PID=$!
(
  while true; do
    echo "$(date -u +%H:%M:%SZ) WATCH cache_entries=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f 2>/dev/null | wc -l) gpu=[$(nvidia-smi --query-gpu=utilization.gpu,clocks.sm,power.draw --format=csv,noheader,nounits 2>/dev/null | tr '\n' ' ')]" >> "$PROGRESS"
    sleep 60
  done
) &
WATCHER_PID=$!

stop_helpers() { kill $SAMPLER_PID $WATCHER_PID 2>/dev/null; wait $SAMPLER_PID $WATCHER_PID 2>/dev/null; }

# --- server readiness ------------------------------------------------------
ready=0
for i in $(seq 1 180); do
  if curl -sf "$BASE_URL/health" >/dev/null 2>&1; then ready=1; break; fi
  if ! kill -0 $SERVER_PID 2>/dev/null; then echo "server child died during load"; break; fi
  sleep 5
done
if [ "$ready" != "1" ]; then
  echo "SERVER NOT READY -- aborting" | tee -a "$PROGRESS"
  stop_helpers
  pkill -TERM -x llama-server 2>/dev/null
  echo "FLY-DONE state=ABORTED-NO-SERVER" | tee -a "$PROGRESS"
  exit 1
fi
echo "server healthy at $(date -u +%H:%M:%SZ)" | tee -a "$PROGRESS"

CACHE_BEFORE_N=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)
CACHE_BEFORE_B=$(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')
echo "featcache before retry: entries=$CACHE_BEFORE_N bytes=$CACHE_BEFORE_B" | tee -a "$PROGRESS"

echo "--- ledger before the retry ---" | tee -a "$PROGRESS"
"$PY" "$SP/budget_ledger.py" 1 "$OUT_DIR" 2>&1 | tee -a "$PROGRESS"

echo "--- run_precomp.py --wave 1 --resume (only TS3004d is not ok) ---" | tee -a "$PROGRESS"
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
  --resume > "$LOGS/retry-runner.log" 2>&1
RC=$?
T1=$(date +%s)
echo "$(date -u +%H:%M:%SZ) runner rc=$RC wall=$((T1-T0))s" | tee -a "$PROGRESS"

stop_helpers

if [ -f "$OUT_DIR/transport-receipt.json" ]; then
  cp "$OUT_DIR/transport-receipt.json" "$OUT_DIR/transport-receipts/resume-2026-08-19-retry.json"
  rm -f "$OUT_DIR/transport-receipt.json"
fi

# --- outcome over the whole roster -----------------------------------------
STATE=COMPLETE
STOP_REASON=""
BAD=""
for m in ES2011a ES2011b ES2011c ES2011d IB4001 IB4002 IB4003 IB4004 IB4010 IB4011 IS1008a IS1008b IS1008c IS1008d TS3004a TS3004b TS3004c TS3004d; do
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
  [ "$OKFLAG" = "ok" ] || { BAD="$BAD $m"; STATE=INCOMPLETE; }
done
if [ -e "$YIELD_FILE" ]; then
  STATE=YIELDED
  STOP_REASON="operator yield (stop-file present at $YIELD_FILE); not complete:$BAD"
elif [ "$STATE" != "COMPLETE" ]; then
  STOP_REASON="wave-1 ended without a complete receipt for:$BAD (runner rc=$RC)"
fi

CACHE_AFTER_N=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)
CACHE_AFTER_B=$(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')
echo "featcache after retry: entries=$CACHE_AFTER_N bytes=$CACHE_AFTER_B (retry delta entries=$((CACHE_AFTER_N-CACHE_BEFORE_N)) bytes=$((CACHE_AFTER_B-CACHE_BEFORE_B)))" | tee -a "$PROGRESS"

echo "--- aggregate wave summary over ALL receipts ---"
"$PY" "$SP/aggregate_resume.py" 1 "$OUT_DIR" "$STOP_REASON" 2>&1 | tee -a "$PROGRESS"

echo "--- final ledger ---"
"$PY" "$SP/budget_ledger.py" 1 "$OUT_DIR" 2>&1 | tee -a "$PROGRESS"

echo "--- per-meeting table (all 18 receipts) ---"
"$PY" "$SP/table.py" "$OUT_DIR" 2>&1 | tee -a "$LOGS/table-final.txt"
cat "$LOGS/table-final.txt"

echo "--- derived-artefact hashes (E: run root; bytes never committed) ---"
( cd "$DATA/derived/meeting-minutes/precomp" && find . -type f -name '*.rttm' | sort | sed 's|^\./||' | xargs -r sha256sum ) > "$LOGS/rttm-artefacts.sha256"
wc -l "$LOGS/rttm-artefacts.sha256"
( cd "$DATA/derived/meeting-minutes/precomp" && find . -type f -name '*.wav' | wc -l ) > "$LOGS/slice-wav-count.txt"
cat "$LOGS/slice-wav-count.txt"

# --- teardown: this script owns the server ---------------------------------
echo "--- teardown ---"
bash "$SP/teardown-resume.sh"
tail -6 "$LOGS/teardown-resume.log"

echo "--- post-run GPU snapshot ---"
nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu --format=csv,noheader

echo "=== PRECOMP wave-1 RETRY end $(date -u +%Y-%m-%dT%H:%M:%SZ) state=$STATE ==="
echo "FLY-DONE state=$STATE" | tee -a "$PROGRESS"
