#!/usr/bin/env bash
# Block up to ~9.5 min for the retry to reach its terminal marker.
# rc=0 terminal reached, rc=2 still running (call again).
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp/env.sh
WRAP="$LOGS/fly-retry-wrapper.log"
TERM_PAT='FLY-'"DONE"

for i in $(seq 1 114); do
  if [ -f "$WRAP" ] && grep -q "$TERM_PAT" "$WRAP" 2>/dev/null; then
    echo "TERMINAL: $(grep "$TERM_PAT" "$WRAP" | tail -1)"
    exit 0
  fi
  sleep 5
done
echo "STILL-RUNNING at $(date -u +%H:%M:%SZ)"
tail -3 "$LOGS/progress-retry.log"
"$PY" -c "
import json,sys
from pathlib import Path
p=Path(sys.argv[1])/'receipts'/'TS3004d-receipt.json'
d=json.loads(p.read_text(encoding='utf-8'))
print('TS3004d ok=%s error=%s' % (d.get('ok'), str(d.get('error'))[:120]))
" "$OUT_DIR"
exit 2
