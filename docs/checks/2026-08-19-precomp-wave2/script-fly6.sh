#!/usr/bin/env bash
# PRECOMP wave-2 supplemental invocation 6: the single meeting (ES2005d)
# that invocation-1 structurally refused, now that the slicer's float-
# accumulation epsilon fix (commit ac0c3b9) is in the tree. Modeled on
# fly2.sh but with an explicit, hard-coded single-meeting target instead of
# a computed roster subset.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp2/env.sh

N=6
BUDGET_S=1200
HARD_KILL_S=$((BUDGET_S + 300))
MEETINGS="ES2005d"

exec > "$LOGS/fly-$N.log" 2>&1
PROGRESS="$LOGS/progress-$N.log"
: > "$PROGRESS"

WRAP_T0=$(date +%s)
echo "=== PRECOMP wave-2 invocation $N (supplemental, ES2005d only) start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "repo HEAD:  $(git -C "$REPO" rev-parse HEAD)"
echo "repo dirty: $(git -C "$REPO" status --porcelain | wc -l) paths"
echo "budget_s:   $BUDGET_S (hard runner SIGTERM at ${HARD_KILL_S}s)"
echo "meetings:   $MEETINGS"

rm -f "$MY_STOP"

if pgrep -x llama-server >/dev/null 2>&1; then
  echo "stale llama-server found -- terminating before launch"
  pgrep -ax llama-server
  pkill -TERM -x llama-server 2>/dev/null
  for i in $(seq 1 40); do pgrep -x llama-server >/dev/null 2>&1 || break; sleep 1; done
  pkill -KILL -x llama-server 2>/dev/null
  sleep 3
fi

RCPT_BEFORE=$(ls "$OUT_DIR/receipts" 2>/dev/null | wc -l)
CACHE_BEFORE_N=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)
CACHE_BEFORE_B=$(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')
echo "receipts before: $RCPT_BEFORE; featcache before: entries=$CACHE_BEFORE_N bytes=$CACHE_BEFORE_B" | tee -a "$PROGRESS"

bash "$SP/serve.sh" &
SERVER_PID=$!
echo "llama-server child pid=$SERVER_PID" | tee -a "$PROGRESS"

GPUHEALTH="$LOGS/gpu-health-$N.log"
: > "$GPUHEALTH"
(
  while true; do
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $(nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu,power.draw,clocks_throttle_reasons.active --format=csv,noheader,nounits 2>/dev/null)" >> "$GPUHEALTH"
    sleep 15
  done
) &
SAMPLER_PID=$!

TIMER_PID=""; KILLER_PID=""
cleanup_helpers() {
  kill $SAMPLER_PID $TIMER_PID $KILLER_PID 2>/dev/null
  wait $SAMPLER_PID $TIMER_PID $KILLER_PID 2>/dev/null
}

echo "--- waiting for llama-server at $BASE_URL ---"
SRV_T0=$(date +%s)
ready=0
for i in $(seq 1 120); do
  if curl -sf "$BASE_URL/health" >/dev/null 2>&1; then ready=1; break; fi
  if ! kill -0 $SERVER_PID 2>/dev/null; then echo "SERVER CHILD DIED during startup"; break; fi
  sleep 5
done
SRV_T1=$(date +%s)
if [ "$ready" != "1" ]; then
  echo "SERVER NOT READY after $((SRV_T1-SRV_T0)) s -- aborting invocation $N" | tee -a "$PROGRESS"
  cleanup_helpers
  kill -TERM $SERVER_PID 2>/dev/null; sleep 5; pkill -KILL -x llama-server 2>/dev/null
  tail -30 "$LOGS/server.log"
  echo "FLY-DONE state=ABORTED-NO-SERVER wall=$(( $(date +%s)-WRAP_T0 ))s" | tee -a "$PROGRESS"
  exit 1
fi
echo "server healthy after $((SRV_T1-SRV_T0)) s at $(date -u +%H:%M:%SZ)" | tee -a "$PROGRESS"

( sleep "$BUDGET_S"; echo "$(date -u +%H:%M:%SZ) INVOCATION TIMER fired (${BUDGET_S}s) -> MY_STOP" >> "$PROGRESS"; : > "$MY_STOP" ) &
TIMER_PID=$!

echo "--- run_precomp.py --wave 2 --resume --stop-file --meetings $MEETINGS ---" | tee -a "$PROGRESS"
T0=$(date +%s)
PYTHONPATH="$REPO/src" "$PY" "$REPO/scripts/run_precomp.py" \
  --wave 2 \
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
  --stop-file "$MY_STOP" \
  --meetings $MEETINGS \
  --resume > "$LOGS/runner-$N.log" 2>&1 &
RUNNER_PID=$!

( sleep "$HARD_KILL_S"
  if kill -0 $RUNNER_PID 2>/dev/null; then
    echo "$(date -u +%H:%M:%SZ) HARD BACKSTOP at ${HARD_KILL_S}s -> SIGTERM runner $RUNNER_PID" >> "$PROGRESS"
    kill -TERM $RUNNER_PID 2>/dev/null
  fi ) &
KILLER_PID=$!

wait $RUNNER_PID
RC=$?
T1=$(date +%s)
RUN_WALL=$((T1-T0))
echo "$(date -u +%H:%M:%SZ) runner rc=$RC wall=${RUN_WALL}s" | tee -a "$PROGRESS"

cleanup_helpers

if [ -f "$OUT_DIR/transport-receipt.json" ]; then
  mv "$OUT_DIR/transport-receipt.json" "$OUT_DIR/transport-receipts/inv-$N.json"
fi
if [ -f "$OUT_DIR/wave-summary.json" ]; then
  cp "$OUT_DIR/wave-summary.json" "$LOGS/wave-summary-inv-$N.json"
fi

echo "--- teardown ---"
kill -TERM $SERVER_PID 2>/dev/null
pkill -TERM -x llama-server 2>/dev/null
for i in $(seq 1 60); do pgrep -x llama-server >/dev/null 2>&1 || break; sleep 1; done
if pgrep -x llama-server >/dev/null 2>&1; then
  echo "SIGTERM did not stop llama-server after 60 s; escalating to SIGKILL"
  pkill -KILL -x llama-server 2>/dev/null
  sleep 3
fi
pgrep -ax llama-server && echo "STILL RUNNING" || echo "llama-server stopped"
wait $SERVER_PID 2>/dev/null

RCPT_AFTER=$(ls "$OUT_DIR/receipts" 2>/dev/null | wc -l)
CACHE_AFTER_N=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)
CACHE_AFTER_B=$(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')
echo "receipts: $RCPT_BEFORE -> $RCPT_AFTER (+$((RCPT_AFTER-RCPT_BEFORE)))" | tee -a "$PROGRESS"
echo "featcache: entries +$((CACHE_AFTER_N-CACHE_BEFORE_N)) bytes +$((CACHE_AFTER_B-CACHE_BEFORE_B))" | tee -a "$PROGRESS"

echo "--- wave-cumulative ledger vs registered wave-2 ceilings ---" | tee -a "$PROGRESS"
"$PY" "$SP/budget_ledger.py" 2 "$OUT_DIR" 2>&1 | tee -a "$PROGRESS"
LEDGER_RC=${PIPESTATUS[0]}

echo "--- ES2005d receipt outcome ---" | tee -a "$PROGRESS"
PYTHONPATH="$REPO/src" "$PY" - "$OUT_DIR" <<'PYEOF' 2>&1 | tee -a "$PROGRESS"
import json, sys
from pathlib import Path
p = Path(sys.argv[1]) / "receipts" / "ES2005d-receipt.json"
d = json.loads(p.read_text(encoding="utf-8"))
enc = d.get("encode_warm") or {}
print("  ES2005d ok=%s calls=%s enc_wall=%.1fs diar_wall=%.1fs" % (
    d.get("ok"), enc.get("n_calls"), float(enc.get("wall_seconds") or 0),
    float((d.get("diar") or {}).get("wall_seconds") or 0)))
if not d.get("ok"):
    print("  ERROR: " + str(d.get("error"))[:400])
else:
    tool = (d.get("slice_plans") or {}).get("tool") or {}
    print("  tool slice_plan: n_slices=%s content_hash=%s" % (tool.get("n_slices"), tool.get("content_hash")))
PYEOF

REMAIN=$(PYTHONPATH="$REPO/src" "$PY" - "$OUT_DIR" <<'PYEOF'
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.environ["REPO"] + "/src")
from meeting_minutes_agent.precomp.roster import default_wave_meetings
from meeting_minutes_agent.precomp.receipts import already_done
out = Path(sys.argv[1])
roster = sorted(default_wave_meetings(2))
todo = [m for m in roster if not already_done(out, m)]
print("%d todo=%s" % (len(todo), todo))
PYEOF
)
echo "wave-2 remaining after invocation $N: $REMAIN" | tee -a "$PROGRESS"

if [ "${REMAIN%% *}" = "0" ]; then STATE=WAVE-COMPLETE
elif [ "$LEDGER_RC" = "3" ]; then STATE=CEILING-REACHED
elif [ "$RC" != "0" ]; then STATE=RUNNER-RC-$RC
else STATE=SLICE-DONE; fi

WRAP_T1=$(date +%s)
echo "invocation wall: $((WRAP_T1-WRAP_T0))s (server start $((SRV_T1-SRV_T0))s, runner ${RUN_WALL}s)" | tee -a "$PROGRESS"
nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu --format=csv,noheader
echo "=== PRECOMP wave-2 invocation $N end $(date -u +%Y-%m-%dT%H:%M:%SZ) state=$STATE ==="
echo "FLY-DONE state=$STATE remaining=$REMAIN wall=$((WRAP_T1-WRAP_T0))s" | tee -a "$PROGRESS"
