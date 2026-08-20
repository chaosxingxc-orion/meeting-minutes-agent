#!/usr/bin/env bash
# ONE PRECOMP wave-2 invocation: a self-contained <=45 min slice of the night batch.
#
#   usage: fly.sh <invocation-number> <runner-budget-seconds>
#
# The harness reaps a background task at ~60 min, so the wave runs as REPEATED short
# invocations rather than one long one. Each invocation:
#   (a) starts its OWN llama-server as a CHILD (a child dies with the wrapper, so even a
#       reap cannot leave an orphan holding 20 GB of VRAM);
#   (b) runs run_precomp.py --wave 2 --resume --stop-file "$MY_STOP";
#   (c) tears the server down;
#   (d) exits.
# Meeting granularity is preserved by the runner: every receipt is fsynced before the next
# meeting starts, so at worst one in-flight meeting is repeated by the next --resume.
#
# Two independent writers can create $MY_STOP, and the runner's --stop-file hook (checked
# before every meeting) turns either into a clean end-of-wave:
#   * the INVOCATION TIMER at $BUDGET_S -- this invocation's own ~40 min slice; and
#   * the YIELD BRIDGE, which polls the COORDINATOR's $YIELD_FILE every 15 s and mirrors
#     it into $MY_STOP. The coordinator's file is only ever read, never created or
#     deleted here (operator rule); $MY_STOP is this operator's own and is cleared at the
#     start of every invocation.
#
# ALL output goes to files: the Windows console can detach mid-flight on this machine, and
# a write to a dead pty must never be able to kill the run.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp2/env.sh

N="${1:?invocation number}"
BUDGET_S="${2:-1920}"
HARD_KILL_S=$((BUDGET_S + 780))   # runner SIGTERM backstop: the harness reap must never be
                                  # the thing that ends this invocation.

exec > "$LOGS/fly-$N.log" 2>&1
PROGRESS="$LOGS/progress-$N.log"
: > "$PROGRESS"

WRAP_T0=$(date +%s)
echo "=== PRECOMP wave-2 invocation $N start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "repo HEAD:  $(git -C "$REPO" rev-parse HEAD)"
echo "out-dir:    $OUT_DIR"
echo "cache:      $LLAMA_MTMD_FEAT_CACHE_DIR"
echo "budget_s:   $BUDGET_S (hard runner SIGTERM at ${HARD_KILL_S}s)"
echo "stop-file:  $MY_STOP"
echo "yield-file: $YIELD_FILE"

# --- coordinator yield honored BEFORE anything starts --------------------------
if [ -e "$YIELD_FILE" ]; then
  echo "COORDINATOR YIELD present at start -- not launching this invocation" | tee -a "$PROGRESS"
  echo "FLY-DONE state=YIELDED-PRESTART" | tee -a "$PROGRESS"
  exit 0
fi

# --- clear this operator's own stop file ---------------------------------------
rm -f "$MY_STOP"

# --- a reaped predecessor can leave an orphan server; clear it -----------------
if pgrep -x llama-server >/dev/null 2>&1; then
  echo "stale llama-server found (reaped predecessor?) -- terminating before launch"
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

# --- server as a CHILD ---------------------------------------------------------
bash "$SP/serve.sh" &
SERVER_PID=$!
echo "llama-server child pid=$SERVER_PID" | tee -a "$PROGRESS"

# --- GPU health sampler (30 s) --------------------------------------------------
GPUHEALTH="$LOGS/gpu-health-$N.log"
: > "$GPUHEALTH"
(
  while true; do
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $(nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu,power.draw,clocks_throttle_reasons.active --format=csv,noheader,nounits 2>/dev/null)" >> "$GPUHEALTH"
    sleep 30
  done
) &
SAMPLER_PID=$!

# --- progress watcher (60 s) ----------------------------------------------------
# The runner prints nothing per stage; silence must never look like success.
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

# --- yield bridge: coordinator file -> this invocation's stop file ---------------
(
  while true; do
    if [ -e "$YIELD_FILE" ]; then
      echo "$(date -u +%H:%M:%SZ) COORDINATOR YIELD observed -> mirroring into MY_STOP" >> "$PROGRESS"
      : > "$MY_STOP"
      break
    fi
    sleep 15
  done
) &
BRIDGE_PID=$!

cleanup_helpers() {
  kill $SAMPLER_PID $WATCHER_PID $BRIDGE_PID $TIMER_PID $KILLER_PID 2>/dev/null
  wait $SAMPLER_PID $WATCHER_PID $BRIDGE_PID $TIMER_PID $KILLER_PID 2>/dev/null
}

# --- server readiness -----------------------------------------------------------
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
  TIMER_PID=""; KILLER_PID=""
  cleanup_helpers
  kill -TERM $SERVER_PID 2>/dev/null; sleep 5; pkill -KILL -x llama-server 2>/dev/null
  tail -30 "$LOGS/server.log"
  echo "FLY-DONE state=ABORTED-NO-SERVER" | tee -a "$PROGRESS"
  exit 1
fi
echo "server healthy after $((SRV_T1-SRV_T0)) s at $(date -u +%H:%M:%SZ)" | tee -a "$PROGRESS"

# --- invocation timer + hard SIGTERM backstop -----------------------------------
( sleep "$BUDGET_S"; echo "$(date -u +%H:%M:%SZ) INVOCATION TIMER fired (${BUDGET_S}s) -> MY_STOP" >> "$PROGRESS"; : > "$MY_STOP" ) &
TIMER_PID=$!

echo "--- run_precomp.py --wave 2 --resume --stop-file ---" | tee -a "$PROGRESS"
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

# --- preserve this invocation's transport ledger --------------------------------
if [ -f "$OUT_DIR/transport-receipt.json" ]; then
  mv "$OUT_DIR/transport-receipt.json" "$OUT_DIR/transport-receipts/inv-$N.json"
fi
# The runner rewrites wave-summary.json per process (only THIS process's outcomes); keep
# the per-invocation copy and let the landing pass re-aggregate over all receipts.
if [ -f "$OUT_DIR/wave-summary.json" ]; then
  cp "$OUT_DIR/wave-summary.json" "$LOGS/wave-summary-inv-$N.json"
fi

# --- teardown: the child server ---------------------------------------------------
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

# --- accounting -------------------------------------------------------------------
RCPT_AFTER=$(ls "$OUT_DIR/receipts" 2>/dev/null | wc -l)
CACHE_AFTER_N=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)
CACHE_AFTER_B=$(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')
echo "receipts: $RCPT_BEFORE -> $RCPT_AFTER (+$((RCPT_AFTER-RCPT_BEFORE)))" | tee -a "$PROGRESS"
echo "featcache: entries +$((CACHE_AFTER_N-CACHE_BEFORE_N)) bytes +$((CACHE_AFTER_B-CACHE_BEFORE_B))" | tee -a "$PROGRESS"

echo "--- wave-cumulative ledger vs registered wave-2 ceilings ---" | tee -a "$PROGRESS"
"$PY" "$SP/budget_ledger.py" 2 "$OUT_DIR" 2>&1 | tee -a "$PROGRESS"
LEDGER_RC=${PIPESTATUS[0]}

echo "--- meetings completed by THIS invocation ---" | tee -a "$PROGRESS"
PYTHONPATH="$REPO/src" "$PY" - "$OUT_DIR" "$RCPT_BEFORE" <<'PYEOF' 2>&1 | tee -a "$PROGRESS"
import json, sys, os
from pathlib import Path
out = Path(sys.argv[1]) / "receipts"
rows = []
for p in sorted(out.glob("*-receipt.json"), key=lambda q: q.stat().st_mtime):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        continue
    rows.append((p.stat().st_mtime, d))
n_before = int(sys.argv[2])
for _, d in rows[n_before:]:
    enc = d.get("encode_warm") or {}
    print("  %-10s ok=%s calls=%s enc_wall=%.1fs diar_wall=%.1fs"
          % (d.get("meeting_id"), d.get("ok"), enc.get("n_calls"),
             float(enc.get("wall_seconds") or 0), float((d.get("diar") or {}).get("wall_seconds") or 0)))
    if not d.get("ok"):
        print("     ERROR: " + str(d.get("error"))[:400])
PYEOF

# --- state ------------------------------------------------------------------------
REMAIN=$(PYTHONPATH="$REPO/src" "$PY" - "$OUT_DIR" <<'PYEOF'
import os, sys
from pathlib import Path
sys.path.insert(0, os.environ["REPO"] + "/src")
from meeting_minutes_agent.precomp.roster import default_wave_meetings
from meeting_minutes_agent.precomp.receipts import already_done
out = Path(sys.argv[1])
todo = [m for m in sorted(default_wave_meetings(2)) if not already_done(out, m)]
print(len(todo))
PYEOF
)
echo "wave-2 meetings still to run: $REMAIN" | tee -a "$PROGRESS"

if [ "$REMAIN" = "0" ]; then STATE=WAVE-COMPLETE
elif [ -e "$YIELD_FILE" ]; then STATE=YIELDED
elif [ "$LEDGER_RC" = "3" ]; then STATE=CEILING-REACHED
elif [ "$RC" != "0" ]; then STATE=RUNNER-RC-$RC
else STATE=SLICE-DONE; fi

WRAP_T1=$(date +%s)
echo "invocation wall: $((WRAP_T1-WRAP_T0))s (server start $((SRV_T1-SRV_T0))s, runner ${RUN_WALL}s)" | tee -a "$PROGRESS"
nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu --format=csv,noheader
echo "=== PRECOMP wave-2 invocation $N end $(date -u +%Y-%m-%dT%H:%M:%SZ) state=$STATE ==="
echo "FLY-DONE state=$STATE remaining=$REMAIN wall=$((WRAP_T1-WRAP_T0))s" | tee -a "$PROGRESS"
