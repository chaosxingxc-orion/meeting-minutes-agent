#!/usr/bin/env bash
# PRECOMP wave-2 invocation wrapper, revision 2 (invocations 2..N).
#
#   usage: fly2.sh <invocation-number> <runner-budget-seconds>
#
# Identical to fly.sh except for ONE operator-side addition, forced by invocation 1's
# ES2005d outcome: the meeting list is computed here and passed explicitly as --meetings,
# so a meeting whose slice PLAN is structurally refused is attempted exactly once for the
# whole wave instead of once per invocation.
#
# Why: ES2005d's pinned-diar turns produce a transport slice of 120.00000000000011 s
# against the hard cap TRANSPORT_SLICE_MAX_S = 120.0 (slicer.py:248 compares with a
# strict `>` and no epsilon tolerance), so slicer.TransportBoundViolation refuses the
# plan fail-closed -- correctly; nothing was sent. That refusal is deterministic (the
# diar tool is deterministic, so the turns and therefore the plan are too), and
# `already_done` requires ok:true, so a plain --resume would re-run its ~40 s diar
# contact on EVERY later invocation, burn real GPU time, and then overwrite its own
# receipt -- which would also make the receipt-derived ledger UNDER-count the diar time
# actually spent. Excluding it keeps wave accounting exact.
#
# The exclusion is computed from the receipts themselves (never a hand-typed id): any
# meeting whose receipt says ok:false AND whose error names TransportBoundViolation. The
# fail-closed exposure gate still runs unconditionally on the resulting list --
# `assert_wave_roster_admissible` is applied by the runner to an operator-supplied
# --meetings override exactly as it is to the default roster.
#
# Repairing the slicer is deliberately NOT done here: slicer constants/algorithm are a
# registered cache-invalidation axis (prereg SS1), so changing them mid-wave would cold-
# start every slice already built and split the wave across two slicer identities. The
# refused meetings are reported to the coordinator instead.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp2/env.sh

N="${1:?invocation number}"
BUDGET_S="${2:-1900}"
HARD_KILL_S=$((BUDGET_S + 780))

exec > "$LOGS/fly-$N.log" 2>&1
PROGRESS="$LOGS/progress-$N.log"
: > "$PROGRESS"

WRAP_T0=$(date +%s)
echo "=== PRECOMP wave-2 invocation $N start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "repo HEAD:  $(git -C "$REPO" rev-parse HEAD)"
echo "budget_s:   $BUDGET_S (hard runner SIGTERM at ${HARD_KILL_S}s)"
echo "stop-file:  $MY_STOP"
echo "yield-file: $YIELD_FILE"

if [ -e "$YIELD_FILE" ]; then
  echo "COORDINATOR YIELD present at start -- not launching this invocation" | tee -a "$PROGRESS"
  echo "FLY-DONE state=YIELDED-PRESTART" | tee -a "$PROGRESS"
  exit 0
fi

rm -f "$MY_STOP"

# --- the meeting list for THIS invocation --------------------------------------
MEETING_FILE="$LOGS/meetings-$N.txt"
PYTHONPATH="$REPO/src" "$PY" - "$OUT_DIR" "$MEETING_FILE" <<'PYEOF'
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.environ["REPO"] + "/src")
from meeting_minutes_agent.precomp.roster import default_wave_meetings
from meeting_minutes_agent.precomp.receipts import already_done

out = Path(sys.argv[1])
roster = sorted(default_wave_meetings(2))
refused = []
for m in roster:
    p = out / "receipts" / f"{m}-receipt.json"
    if not p.is_file():
        continue
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        continue
    if not d.get("ok") and "TransportBoundViolation" in str(d.get("error")):
        refused.append(m)
todo = [m for m in roster if not already_done(out, m) and m not in refused]
Path(sys.argv[2]).write_text(" ".join(todo) + "\n", encoding="utf-8")
print(json.dumps({"roster_n": len(roster), "already_ok": len([m for m in roster if already_done(out, m)]),
                  "structurally_refused_skipped": refused, "todo_n": len(todo)}, indent=2))
PYEOF
MEETINGS=$(cat "$MEETING_FILE")
echo "meetings for this invocation: $MEETINGS" | tee -a "$PROGRESS"
if [ -z "${MEETINGS// /}" ]; then
  echo "nothing left to run" | tee -a "$PROGRESS"
  echo "FLY-DONE state=WAVE-COMPLETE remaining=0 wall=0s" | tee -a "$PROGRESS"
  exit 0
fi

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

bash "$SP/serve.sh" &
SERVER_PID=$!
echo "llama-server child pid=$SERVER_PID" | tee -a "$PROGRESS"

GPUHEALTH="$LOGS/gpu-health-$N.log"
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
    N_RCPT=$(ls "$OUT_DIR/receipts" 2>/dev/null | wc -l)
    N_CACHE=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f 2>/dev/null | wc -l)
    GPU=$(nvidia-smi --query-gpu=utilization.gpu,clocks.sm,power.draw --format=csv,noheader,nounits 2>/dev/null | tr '\n' ' ')
    LATEST=$(ls -t "$OUT_DIR/receipts" 2>/dev/null | head -1)
    echo "$(date -u +%H:%M:%SZ) WATCH receipts=$N_RCPT latest=$LATEST cache_entries=$N_CACHE gpu=[$GPU]" >> "$PROGRESS"
    sleep 60
  done
) &
WATCHER_PID=$!

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

TIMER_PID=""; KILLER_PID=""
cleanup_helpers() {
  kill $SAMPLER_PID $WATCHER_PID $BRIDGE_PID $TIMER_PID $KILLER_PID 2>/dev/null
  wait $SAMPLER_PID $WATCHER_PID $BRIDGE_PID $TIMER_PID $KILLER_PID 2>/dev/null
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
  echo "FLY-DONE state=ABORTED-NO-SERVER remaining=? wall=$(( $(date +%s)-WRAP_T0 ))s" | tee -a "$PROGRESS"
  exit 1
fi
echo "server healthy after $((SRV_T1-SRV_T0)) s at $(date -u +%H:%M:%SZ)" | tee -a "$PROGRESS"

( sleep "$BUDGET_S"; echo "$(date -u +%H:%M:%SZ) INVOCATION TIMER fired (${BUDGET_S}s) -> MY_STOP" >> "$PROGRESS"; : > "$MY_STOP" ) &
TIMER_PID=$!

echo "--- run_precomp.py --wave 2 --resume --stop-file --meetings <computed> ---" | tee -a "$PROGRESS"
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

echo "--- meetings attempted by THIS invocation ---" | tee -a "$PROGRESS"
PYTHONPATH="$REPO/src" "$PY" - "$OUT_DIR" "$MEETING_FILE" <<'PYEOF' 2>&1 | tee -a "$PROGRESS"
import json, sys
from pathlib import Path
out = Path(sys.argv[1]) / "receipts"
planned = Path(sys.argv[2]).read_text(encoding="utf-8").split()
for m in planned:
    p = out / f"{m}-receipt.json"
    if not p.is_file():
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    enc = d.get("encode_warm") or {}
    print("  %-10s ok=%s calls=%s enc_wall=%.1fs diar_wall=%.1fs"
          % (m, d.get("ok"), enc.get("n_calls"), float(enc.get("wall_seconds") or 0),
             float((d.get("diar") or {}).get("wall_seconds") or 0)))
    if not d.get("ok"):
        print("     ERROR: " + str(d.get("error"))[:300])
PYEOF

REMAIN=$(PYTHONPATH="$REPO/src" "$PY" - "$OUT_DIR" <<'PYEOF'
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.environ["REPO"] + "/src")
from meeting_minutes_agent.precomp.roster import default_wave_meetings
from meeting_minutes_agent.precomp.receipts import already_done
out = Path(sys.argv[1])
roster = sorted(default_wave_meetings(2))
refused = []
for m in roster:
    p = out / "receipts" / f"{m}-receipt.json"
    if p.is_file():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not d.get("ok") and "TransportBoundViolation" in str(d.get("error")):
            refused.append(m)
todo = [m for m in roster if not already_done(out, m) and m not in refused]
print("%d refused=%d" % (len(todo), len(refused)))
PYEOF
)
echo "wave-2 runnable meetings still to run: $REMAIN" | tee -a "$PROGRESS"

if [ "${REMAIN%% *}" = "0" ]; then STATE=WAVE-COMPLETE
elif [ -e "$YIELD_FILE" ]; then STATE=YIELDED
elif [ "$LEDGER_RC" = "3" ]; then STATE=CEILING-REACHED
elif [ "$RC" != "0" ]; then STATE=RUNNER-RC-$RC
else STATE=SLICE-DONE; fi

WRAP_T1=$(date +%s)
echo "invocation wall: $((WRAP_T1-WRAP_T0))s (server start $((SRV_T1-SRV_T0))s, runner ${RUN_WALL}s)" | tee -a "$PROGRESS"
nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu --format=csv,noheader
echo "=== PRECOMP wave-2 invocation $N end $(date -u +%Y-%m-%dT%H:%M:%SZ) state=$STATE ==="
echo "FLY-DONE state=$STATE remaining=$REMAIN wall=$((WRAP_T1-WRAP_T0))s" | tee -a "$PROGRESS"
