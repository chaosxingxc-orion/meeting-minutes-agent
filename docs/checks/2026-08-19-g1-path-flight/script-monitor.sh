#!/usr/bin/env bash
# G1-PATH monitor. Emits ONE line per newly landed (meeting, arm) item receipt,
# every failure signature, and the terminal marker, then exits.
# Coverage: success, per-item error, budget stop, yield, traceback, server
# startup failure, dead wrapper. Silence must never look like success.
# Usage: monitor.sh <chunk-index>
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1path/env.sh

N="${1:?usage: monitor.sh <chunk-index>}"
WRAP="$LOGS/fly-chunk$N-wrapper.log"
RUNLOG="$LOGS/runner-chunk$N.log"
TERM_PAT='FLY-'"DONE"
ERR_PAT='Traceback|G1BudgetExceeded|ServerStartupError|G1VadSupplementMissingError|G1Error|stop-file present|SERVER NOT READY|ConnectionError|HTTPError|Timeout|URLError|REFUSING'

SEEN=" "
for f in "$RUN_DIR"/receipts/*-receipt.json; do
  [ -e "$f" ] || continue
  SEEN="$SEEN$(basename "$f" -receipt.json) "
done
ERRLINES=0
echo "monitor armed $(date -u +%H:%M:%SZ) chunk=$N; seeded with [$SEEN]"

while true; do
  for f in "$RUN_DIR"/receipts/*-receipt.json; do
    [ -e "$f" ] || continue
    b=$(basename "$f" -receipt.json)
    case "$SEEN" in *" $b "*) continue;; esac
    SEEN="$SEEN$b "
    line=$("$PY" -c "
import collections,json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
k=collections.Counter(c.get('kind') for c in (d.get('contacts') or []))
print('%s %s ok=%s calls=%s transcribe=%d minutes=%d qa=%d wall=%.1fs' % (
    d.get('meeting_id'), d.get('arm'), d.get('ok'), d.get('n_calls'),
    k.get('transcribe',0), k.get('minutes',0), k.get('qa',0),
    float(d.get('wall_seconds') or 0.0)))
if not d.get('ok'):
    print('   ITEM-ERROR: ' + str(d.get('error'))[:300])
" "$f" 2>&1)
    echo "$(date -u +%H:%M:%SZ) ITEM $line"
  done

  if [ -f "$RUNLOG" ]; then
    n=$(grep -Ec "$ERR_PAT" "$RUNLOG" 2>/dev/null || echo 0)
    if [ "$n" -gt "$ERRLINES" ]; then
      grep -E "$ERR_PAT" "$RUNLOG" 2>/dev/null | tail -n $((n - ERRLINES)) | while IFS= read -r l; do
        echo "$(date -u +%H:%M:%SZ) RUNLOG $l"
      done
      ERRLINES=$n
    fi
  fi

  if [ -f "$WRAP" ] && grep -q "$TERM_PAT" "$WRAP" 2>/dev/null; then
    echo "$(date -u +%H:%M:%SZ) TERMINAL $(grep "$TERM_PAT" "$WRAP" | tail -1)"
    exit 0
  fi

  # Dead-runner detection, armed only once the runner has actually been seen:
  # a runner that vanishes without writing the terminal marker is a hard fail
  # (harness reap, SIGKILL), and must never read as "still running".
  if pgrep -af "run_g1.py" >/dev/null 2>&1; then
    RUNNER_SEEN=1
  elif [ "${RUNNER_SEEN:-0}" = "1" ]; then
    echo "$(date -u +%H:%M:%SZ) FATAL run_g1.py vanished without a terminal marker"
    tail -15 "$RUNLOG" 2>/dev/null
    exit 1
  fi

  sleep 20
done
