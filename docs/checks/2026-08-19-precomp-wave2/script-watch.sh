#!/usr/bin/env bash
# Emit ONE event per wave-2 receipt landing, plus every terminal/failure signal, then
# exit. Silence must never look like success, so the terminal alternation is wide: an
# aborted server, a dead child, a budget stop, a runner traceback, a vanished runner
# process, and the wrapper's own FLY-DONE each produce exactly one line.
#   usage: watch.sh <invocation-number>
set -u
N="${1:?invocation number}"
SP=/mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp2
R=/mnt/d/chao_workspace/exploring-l4-intelligence/papers/meeting-minutes-agent/docs/checks/2026-08-19-precomp-wave2/receipts
PROG="$SP/logs/progress-$N.log"
RUN="$SP/logs/runner-$N.log"

prev=$(ls "$R" 2>/dev/null | wc -l)
echo "inv$N watch armed: receipts=$prev at $(date -u +%H:%M:%SZ)"
gone=0
while true; do
  sleep 45
  cur=$(ls "$R" 2>/dev/null | wc -l)
  if [ "$cur" -gt "$prev" ]; then
    echo "inv$N receipts=$cur latest=$(ls -t "$R" 2>/dev/null | head -1) $(date -u +%H:%M:%SZ)"
    prev=$cur
  fi
  if grep -q 'FLY-DONE' "$PROG" 2>/dev/null; then
    grep -hE 'HARD BACKSTOP|COORDINATOR YIELD|ABORTED|SERVER CHILD DIED|STILL RUNNING' "$PROG" 2>/dev/null
    grep -hE 'Traceback|BUDGET STOP|Error:' "$RUN" 2>/dev/null | tail -3
    grep 'FLY-DONE' "$PROG" | tail -1
    exit 0
  fi
  # stall detector: no run_precomp process and no FLY-DONE == the wrapper was reaped.
  if ! pgrep -f 'run_precomp.py --wave 2' >/dev/null 2>&1; then
    gone=$((gone + 1))
    if [ "$gone" -ge 3 ]; then
      echo "inv$N STALLED: no run_precomp.py process and no FLY-DONE (wrapper reaped?) receipts=$cur"
      tail -3 "$PROG" 2>/dev/null
      exit 1
    fi
  else
    gone=0
  fi
done
