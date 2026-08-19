#!/usr/bin/env bash
# PRECOMP wave-1 resume monitor. Emits ONE line per newly landed receipt (the
# only real per-meeting progress signal -- the runner prints nothing per stage),
# plus every failure signature and the terminal marker, then exits.
# Coverage: success, per-meeting error, budget stop, yield, traceback, dead
# server, dead wrapper. Silence must never look like success.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp/env.sh

WRAP="$LOGS/fly-resume-wrapper.log"
RUNLOG="$LOGS/resume-runner.log"
TERM_PAT='FLY-'"DONE"
ERR_PAT='Traceback|BUDGET STOP|stop-file present|NO-RECEIPT|ERR:|SERVER NOT READY|ConnectionError|HTTPError|Timeout'

# Seed: the nine meetings the first pass already landed (commit b969add).
SEEN=" ES2011a ES2011b ES2011c ES2011d IB4001 IB4002 IB4003 IB4004 IB4010 "
ERRLINES=0

echo "monitor armed $(date -u +%H:%M:%SZ); watching $OUT_DIR/receipts and $RUNLOG"

while true; do
  for f in "$OUT_DIR"/receipts/*-receipt.json; do
    [ -e "$f" ] || continue
    b=$(basename "$f" -receipt.json)
    case "$SEEN" in *" $b "*) continue;; esac
    SEEN="$SEEN$b "
    line=$("$PY" -c "
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
m=d.get('metrics') or {}
sc=m.get('slice_counts') or {}
cd=(m.get('cache') or {}).get('delta') or {}
print('%s ok=%s diar=%.1fs slices=%s/%s calls=%s encode=%.1fs cache+=%s' % (
    d.get('meeting_id'), d.get('ok'),
    (d.get('diar') or {}).get('wall_seconds') or 0.0,
    sc.get('tool_slices'), sc.get('oracle_slices'),
    (d.get('encode_warm') or {}).get('n_calls'),
    (d.get('encode_warm') or {}).get('wall_seconds') or 0.0,
    cd.get('entries_added')))
if not d.get('ok'):
    print('   MEETING-ERROR: ' + str(d.get('error'))[:300])
" "$f" 2>&1)
    echo "$(date -u +%H:%M:%SZ) RECEIPT $line"
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

  if ! pgrep -x llama-server >/dev/null 2>&1; then
    echo "$(date -u +%H:%M:%SZ) FATAL llama-server is gone"
    exit 1
  fi

  if [ -f "$WRAP" ] && grep -q "$TERM_PAT" "$WRAP" 2>/dev/null; then
    echo "$(date -u +%H:%M:%SZ) TERMINAL $(grep "$TERM_PAT" "$WRAP" | tail -1)"
    exit 0
  fi

  sleep 20
done
