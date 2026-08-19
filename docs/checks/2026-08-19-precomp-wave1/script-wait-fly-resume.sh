#!/usr/bin/env bash
# Block up to ~9.5 min for the resume pass to reach its terminal marker.
# rc=0 terminal reached, rc=2 still running (call again), rc=1 fatal.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp/env.sh
WRAP="$LOGS/fly-resume-wrapper.log"
TERM_PAT='FLY-'"DONE"

for i in $(seq 1 114); do
  if [ -f "$WRAP" ] && grep -q "$TERM_PAT" "$WRAP" 2>/dev/null; then
    echo "TERMINAL: $(grep "$TERM_PAT" "$WRAP" | tail -1)"
    exit 0
  fi
  if ! pgrep -x llama-server >/dev/null 2>&1; then
    echo "FATAL: llama-server is gone"
    tail -20 "$LOGS/server.log"
    exit 1
  fi
  sleep 5
done
echo "STILL-RUNNING at $(date -u +%H:%M:%SZ)"
tail -3 "$LOGS/progress-resume.log"
echo "receipts: $(ls "$OUT_DIR/receipts" | wc -l)/18"
exit 2
