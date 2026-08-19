#!/usr/bin/env bash
# G1 VAD supplement: ONE pass = ONE run_precomp.py invocation over half the
# dev-18 roster, with its own llama-server started and torn down as a CHILD of
# THIS script -- so server and work share one harness window and the server can
# never outlive (or be killed independently of) the work depending on it
# (docs/checks/2026-08-19-precomp-wave1/README.md resume-pass lesson).
#
# Usage: fly.sh A|B
#
# ALL output goes to files: a write to a dead pty must never be able to kill
# the run.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1sup/env.sh

L="${1:?usage: fly.sh A|B}"
case "$L" in
  A) MEETINGS="$PASS_A_MEETINGS" ;;
  B) MEETINGS="$PASS_B_MEETINGS" ;;
  *) echo "unknown pass $L" >&2; exit 1 ;;
esac

exec > "$LOGS/fly-pass$L-wrapper.log" 2>&1
PROGRESS="$LOGS/progress-pass$L.log"
: > "$PROGRESS"

echo "=== G1 VAD supplement pass $L start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "repo HEAD: $(git -C "$REPO" rev-parse HEAD)"
echo "repo dirty lines: $(git -C "$REPO" status --porcelain | wc -l)"
echo "out-dir:   $OUT_DIR"
echo "cache:     $LLAMA_MTMD_FEAT_CACHE_DIR"
echo "stop-file: $YIELD_FILE"
echo "meetings:  $MEETINGS"

if pgrep -x llama-server >/dev/null 2>&1; then
  echo "REFUSING: an llama-server process is already running"
  pgrep -ax llama-server
  echo "FLY-DONE state=ABORTED-SERVER-ALREADY-RUNNING" | tee -a "$PROGRESS"
  exit 1
fi

mkdir -p "$OUT_DIR/transport-receipts"

# --- server as a CHILD of this script ---------------------------------------
( cd "$(dirname "$LLAMA_BIN")" && exec ./llama-server \
    --host 127.0.0.1 --port "$PORT" \
    -m "$MODEL_GGUF" \
    --mmproj "$MMPROJ_GGUF" \
    -c 49152 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0 \
    >> "$LOGS/server.log" 2>&1 ) &
SERVER_PID=$!
echo "$(date -u +%H:%M:%SZ) llama-server child pid=$SERVER_PID" | tee -a "$PROGRESS"

# --- GPU health sampler (30 s) ----------------------------------------------
GPUHEALTH="$LOGS/gpu-health-pass$L.log"
: > "$GPUHEALTH"
(
  while true; do
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $(nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu,power.draw,clocks_throttle_reasons.active --format=csv,noheader,nounits 2>/dev/null)" >> "$GPUHEALTH"
    sleep 30
  done
) &
SAMPLER_PID=$!

# --- progress watcher (60 s) ------------------------------------------------
# The runner prints nothing per stage; silence must never look like success.
(
  while true; do
    N_RCPT=$(ls "$OUT_DIR/receipts" 2>/dev/null | wc -l)
    N_MAN=$(ls "$VAD_MANIFEST_DIR" 2>/dev/null | wc -l)
    N_WAV=$(find "$VAD_SLICE_ROOT" -type f -name '*.wav' 2>/dev/null | wc -l)
    N_CACHE=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f 2>/dev/null | wc -l)
    GPU=$(nvidia-smi --query-gpu=utilization.gpu,clocks.sm,power.draw --format=csv,noheader,nounits 2>/dev/null | tr '\n' ' ')
    echo "$(date -u +%H:%M:%SZ) WATCH receipts=$N_RCPT manifests=$N_MAN vad_wavs=$N_WAV cache_entries=$N_CACHE gpu=[$GPU]" >> "$PROGRESS"
    sleep 60
  done
) &
WATCHER_PID=$!

stop_helpers() { kill $SAMPLER_PID $WATCHER_PID 2>/dev/null; wait $SAMPLER_PID $WATCHER_PID 2>/dev/null; }

# --- server readiness -------------------------------------------------------
echo "--- waiting for llama-server at $BASE_URL ---"
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
RCPT_BEFORE=$(ls "$OUT_DIR/receipts" 2>/dev/null | wc -l)
echo "featcache before: entries=$CACHE_BEFORE_N bytes=$CACHE_BEFORE_B; supplement receipts before: $RCPT_BEFORE" | tee -a "$PROGRESS"

echo "--- ledger before pass $L (operator cross-check of the native precharge) ---" | tee -a "$PROGRESS"
"$PY" "$SP/ledger.py" "$OUT_DIR" 2>&1 | tee -a "$PROGRESS"

echo "--- invocation: run_precomp.py --turn-sources vad --ceilings-profile g1-supplement --resume ---" | tee -a "$PROGRESS"
T0=$(date +%s)
PYTHONPATH="$REPO/src" "$PY" "$REPO/scripts/run_precomp.py" \
  --wave 1 \
  --data-dir "$DATA" \
  --meetings $MEETINGS \
  --turn-sources vad \
  --ceilings-profile g1-supplement \
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
  --resume > "$LOGS/runner-pass$L.log" 2>&1
RC=$?
T1=$(date +%s)
echo "$(date -u +%H:%M:%SZ) runner rc=$RC wall=$((T1-T0))s" | tee -a "$PROGRESS"

stop_helpers

# preserve this invocation's transport ledger under its own per-pass name
if [ -f "$OUT_DIR/transport-receipt.json" ]; then
  cp "$OUT_DIR/transport-receipt.json" "$OUT_DIR/transport-receipts/pass$L-2026-08-19.json"
  rm -f "$OUT_DIR/transport-receipt.json"
fi

# --- per-meeting outcome ----------------------------------------------------
STATE=COMPLETE
DONE_LIST=""
MISSING_LIST=""
for m in $MEETINGS; do
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
if [ -e "$YIELD_FILE" ]; then STATE=YIELDED; fi

CACHE_AFTER_N=$(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)
CACHE_AFTER_B=$(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')
echo "featcache after: entries=$CACHE_AFTER_N bytes=$CACHE_AFTER_B (pass delta entries=$((CACHE_AFTER_N-CACHE_BEFORE_N)) bytes=$((CACHE_AFTER_B-CACHE_BEFORE_B)))" | tee -a "$PROGRESS"
echo "vad manifests now: $(ls "$VAD_MANIFEST_DIR" 2>/dev/null | wc -l)" | tee -a "$PROGRESS"
echo "vad slice wavs now: $(find "$VAD_SLICE_ROOT" -type f -name '*.wav' 2>/dev/null | wc -l)" | tee -a "$PROGRESS"

echo "--- ledger after pass $L ---" | tee -a "$PROGRESS"
"$PY" "$SP/ledger.py" "$OUT_DIR" 2>&1 | tee -a "$PROGRESS"

# --- teardown: the server is OUR child; it dies with this pass --------------
echo "--- teardown $(date -u +%H:%M:%SZ) ---"
kill -TERM $SERVER_PID 2>/dev/null
for i in $(seq 1 60); do
  kill -0 $SERVER_PID 2>/dev/null || break
  sleep 1
done
if kill -0 $SERVER_PID 2>/dev/null; then
  echo "SIGTERM did not stop the server child after 60 s; escalating to SIGKILL"
  kill -KILL $SERVER_PID 2>/dev/null
  sleep 3
fi
pkill -TERM -x llama-server 2>/dev/null
sleep 2
pgrep -ax llama-server && echo "WARNING: llama-server STILL RUNNING" || echo "llama-server stopped"
nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu --format=csv,noheader
echo "server.log lines: $(wc -l < "$LOGS/server.log")"
grep -Ei 'error|failed|abort|assert|out of memory|terminate' "$LOGS/server.log" | tail -10 || echo "(no error lines)"

echo "completed this pass:$DONE_LIST"
echo "not completed:$MISSING_LIST"
echo "=== G1 VAD supplement pass $L end $(date -u +%Y-%m-%dT%H:%M:%SZ) state=$STATE ==="
echo "FLY-DONE state=$STATE pass=$L" | tee -a "$PROGRESS"
