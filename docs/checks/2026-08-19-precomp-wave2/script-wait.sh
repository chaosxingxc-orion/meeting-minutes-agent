#!/usr/bin/env bash
# Block until invocation <N>'s wrapper reaches a terminal state, then print its outcome.
# Wide terminal detection: FLY-DONE covers the clean paths, and the wrapper-process
# check catches a reap (silence must never look like success).
#   usage: wait.sh <invocation-number> [max-polls]
set -u
N="${1:?invocation number}"
MAX="${2:-240}"   # 240 * 20 s = 80 min
SP=/mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp2
PROG="$SP/logs/progress-$N.log"

for i in $(seq 1 "$MAX"); do
  if grep -q 'FLY-DONE' "$PROG" 2>/dev/null; then
    echo "--- invocation $N terminal ---"
    grep -E 'server healthy|runner rc=|receipts:|featcache:|HARD BACKSTOP|COORDINATOR YIELD|ABORTED|STILL RUNNING|wave-2 meetings still to run|invocation wall|FLY-DONE' "$PROG"
    echo "--- meetings this invocation ---"
    grep -E '^\s{2}\S+\s+ok=|^\s{5}ERROR:' "$PROG" || true
    echo "--- ledger ---"
    grep -o '{"breaches".*' "$PROG" | tail -1
    exit 0
  fi
  if ! pgrep -f "precomp2/fly.*\.sh $N " >/dev/null 2>&1 && [ "$i" -gt 3 ]; then
    echo "--- invocation $N WRAPPER GONE without FLY-DONE (reaped?) ---"
    tail -20 "$PROG" 2>/dev/null
    pgrep -ax llama-server || echo "(no llama-server)"
    exit 2
  fi
  sleep 20
done
echo "--- invocation $N still running after $((MAX * 20)) s ---"
tail -10 "$PROG" 2>/dev/null
exit 3
