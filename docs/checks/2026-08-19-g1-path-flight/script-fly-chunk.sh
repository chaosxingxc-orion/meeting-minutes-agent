#!/usr/bin/env bash
# G1-PATH: ONE chunk = ONE scripts/run_g1.py --run-chunk invocation, which
# starts and tears down the pinned llama-server as its OWN direct child
# (g1_campaign.ManagedLlamaServer). Server and work therefore share one
# harness window and the server can never outlive, or be killed independently
# of, the work depending on it (the wave-1 resume-pass lesson).
#
# Usage: fly-chunk.sh <chunk-index>
#
# ALL output goes to files: a write to a dead pty must never kill the run.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1path/env.sh

N="${1:?usage: fly-chunk.sh <chunk-index>}"
exec > "$LOGS/fly-chunk$N-wrapper.log" 2>&1
PROGRESS="$LOGS/progress-chunk$N.log"
: > "$PROGRESS"

echo "=== G1-PATH chunk $N start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "repo HEAD: $(git -C "$REPO" rev-parse HEAD)"
echo "repo dirty lines: $(git -C "$REPO" status --porcelain | wc -l)"
echo "out-dir:  $RUN_DIR"
echo "vad-manifest-dir: $VAD_MANIFEST_DIR ($(ls "$VAD_MANIFEST_DIR" 2>/dev/null | wc -l) manifests)"
echo "flight ceilings: calls<=$PATH_MAX_CALLS gpu<=${PATH_MAX_GPU_HOURS}h wall<=${PATH_MAX_WALL_HOURS}h"
echo "qa cap (machinery probe): $PATH_QA_CAP"

if pgrep -x llama-server >/dev/null 2>&1; then
  echo "REFUSING: an llama-server process is already running"
  pgrep -ax llama-server
  echo "FLY-DONE state=ABORTED-SERVER-ALREADY-RUNNING" | tee -a "$PROGRESS"
  exit 1
fi

mkdir -p "$RUN_DIR"

# --- GPU health sampler (30 s) ----------------------------------------------
GPUHEALTH="$LOGS/gpu-health-chunk$N.log"
: > "$GPUHEALTH"
(
  while true; do
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $(nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu,power.draw,clocks_throttle_reasons.active --format=csv,noheader,nounits 2>/dev/null)" >> "$GPUHEALTH"
    sleep 30
  done
) &
SAMPLER_PID=$!

# --- progress watcher (60 s) ------------------------------------------------
# Receipts land per (meeting, arm); the JSONL sink grows per contact. Counting
# sink LINES is the only per-contact progress signal read here -- the reply
# text itself is never read (PATH renders no metric verdict).
(
  while true; do
    N_RCPT=$(ls "$RUN_DIR/receipts" 2>/dev/null | wc -l)
    N_SINK=$(wc -l < "$RUN_DIR/responses/chunk$(printf '%04d' "$N")-responses.jsonl" 2>/dev/null || echo 0)
    GPU=$(nvidia-smi --query-gpu=utilization.gpu,clocks.sm,power.draw --format=csv,noheader,nounits 2>/dev/null | tr '\n' ' ')
    echo "$(date -u +%H:%M:%SZ) WATCH item_receipts=$N_RCPT sink_lines=$N_SINK gpu=[$GPU]" >> "$PROGRESS"
    sleep 60
  done
) &
WATCHER_PID=$!
stop_helpers() { kill $SAMPLER_PID $WATCHER_PID 2>/dev/null; wait $SAMPLER_PID $WATCHER_PID 2>/dev/null; }

echo "--- invocation: run_g1.py --mode path --run-chunk $N ---" | tee -a "$PROGRESS"
T0=$(date +%s)
PYTHONPATH="$REPO/src" "$PY" "$REPO/scripts/run_g1.py" \
  --mode path \
  --data-dir "$DATA" \
  --out-dir "$RUN_DIR" \
  --vad-manifest-dir "$VAD_MANIFEST_DIR" \
  --meetingqa-root "$MEETINGQA_ROOT" \
  --ami-root "$AMI_ROOT" \
  --qa-cap "$PATH_QA_CAP" \
  --max-calls "$PATH_MAX_CALLS" \
  --max-gpu-hours "$PATH_MAX_GPU_HOURS" \
  --max-wall-hours "$PATH_MAX_WALL_HOURS" \
  --run-chunk "$N" \
  --resume \
  --stop-file "$YIELD_FILE" \
  --server-cmd "$SP/serve-child.sh" \
  --base-url "$BASE_URL" \
  --model-path "$MODEL_GGUF" \
  --model-sha256 "$MODEL_SHA256" \
  --slots 1 \
  --timeout-seconds 600 \
  --health-timeout-seconds 900 > "$LOGS/runner-chunk$N.log" 2>&1
RC=$?
T1=$(date +%s)
echo "$(date -u +%H:%M:%SZ) runner rc=$RC wall=$((T1-T0))s" | tee -a "$PROGRESS"

stop_helpers

# --- structural outcome per (meeting, arm) ----------------------------------
"$PY" "$SP/structural.py" "$RUN_DIR" "$N" 2>&1 | tee -a "$PROGRESS"

# --- no orphan server may survive this chunk --------------------------------
if pgrep -x llama-server >/dev/null 2>&1; then
  echo "WARNING: llama-server survived the chunk invocation; terminating"
  pgrep -ax llama-server
  pkill -TERM -x llama-server 2>/dev/null
  for i in $(seq 1 60); do pgrep -x llama-server >/dev/null 2>&1 || break; sleep 1; done
  pkill -KILL -x llama-server 2>/dev/null
  sleep 2
fi
pgrep -ax llama-server && echo "STILL RUNNING" || echo "llama-server stopped (no orphan)"
nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu --format=csv,noheader
echo "server.log lines: $(wc -l < "$LOGS/server.log" 2>/dev/null || echo 0)"
grep -Ei 'error|failed|abort|assert|out of memory|terminate' "$LOGS/server.log" 2>/dev/null | tail -10 || echo "(no error lines)"

STATE=DONE
[ "$RC" != "0" ] && STATE=RUNNER-RC-$RC
[ -e "$YIELD_FILE" ] && STATE=YIELDED
echo "=== G1-PATH chunk $N end $(date -u +%Y-%m-%dT%H:%M:%SZ) state=$STATE ==="
echo "FLY-DONE state=$STATE chunk=$N" | tee -a "$PROGRESS"
