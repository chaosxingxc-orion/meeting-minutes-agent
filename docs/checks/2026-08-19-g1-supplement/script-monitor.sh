#!/usr/bin/env bash
# G1 VAD supplement monitor. Emits ONE line per newly landed receipt (the only
# real per-meeting progress signal -- the runner prints nothing per stage), plus
# every failure signature and the terminal marker, then exits.
# Coverage: success, per-meeting error, budget stop, yield, traceback, dead
# server, dead wrapper. Silence must never look like success.
# Usage: monitor.sh A|B
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1sup/env.sh

L="${1:?usage: monitor.sh A|B}"
WRAP="$LOGS/fly-pass$L-wrapper.log"
RUNLOG="$LOGS/runner-pass$L.log"
TERM_PAT='FLY-'"DONE"
ERR_PAT='Traceback|BUDGET STOP|stop-file present|NO-RECEIPT|ERR:|SERVER NOT READY|ConnectionError|HTTPError|Timeout|URLError'

SEEN=" "
for f in "$OUT_DIR"/receipts/*-receipt.json; do
  [ -e "$f" ] || continue
  SEEN="$SEEN$(basename "$f" -receipt.json) "
done
ERRLINES=0
echo "monitor armed $(date -u +%H:%M:%SZ) pass=$L; seeded with [$SEEN]"

while true; do
  for f in "$OUT_DIR"/receipts/*-receipt.json; do
    [ -e "$f" ] || continue
    b=$(basename "$f" -receipt.json)
    case "$SEEN" in *" $b "*) continue;; esac
    SEEN="$SEEN$b "
    line=$("$PY" -c "
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
sp=(d.get('slice_plans') or {}).get('vad') or {}
cd=((d.get('metrics') or {}).get('cache') or {}).get('delta') or {}
cut=d.get('cutting') or {}
enc=d.get('encode_warm') or {}
print('%s ok=%s vad_slices=%s manifest=%s cut=%.2fs calls=%s encode=%.1fs cache+=%s' % (
    d.get('meeting_id'), d.get('ok'), sp.get('n_slices'),
    'yes' if sp.get('manifest_path') else 'NO',
    float(cut.get('wall_seconds') or 0.0), enc.get('n_calls'),
    float(enc.get('wall_seconds') or 0.0), cd.get('entries_added')))
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

  if [ -f "$WRAP" ] && grep -q "$TERM_PAT" "$WRAP" 2>/dev/null; then
    echo "$(date -u +%H:%M:%SZ) TERMINAL $(grep "$TERM_PAT" "$WRAP" | tail -1)"
    exit 0
  fi

  if ! pgrep -x llama-server >/dev/null 2>&1; then
    echo "$(date -u +%H:%M:%SZ) FATAL llama-server is gone (and no terminal marker)"
    tail -5 "$LOGS/server.log" 2>/dev/null
    exit 1
  fi

  sleep 20
done
