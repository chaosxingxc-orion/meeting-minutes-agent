#!/usr/bin/env bash
# Stream PRECOMP wave-1 progress events. Covers success, failure, yield,
# budget stop and the terminal marker -- silence must never look like success.
P=/mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp/logs/progress.log
until [ -f "$P" ]; do sleep 2; done
tail -n +1 -f "$P" | grep -E --line-buffered 'rc=|YIELD|BUDGET|FLY-DONE|ABORT|NO-RECEIPT|ERR:|featcache'
