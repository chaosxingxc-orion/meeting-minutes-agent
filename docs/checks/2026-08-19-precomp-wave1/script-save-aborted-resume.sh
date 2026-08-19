#!/usr/bin/env bash
# Preserve the aborted TS3004d receipt before --resume overwrites it: the
# retry's success must not erase the record that a first attempt ran diar and
# then lost the server. Landed as evidence, not as a wave outcome.
set -eu
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp/env.sh
cp "$OUT_DIR/receipts/TS3004d-receipt.json" "$LOGS/TS3004d-aborted-attempt-receipt.json"
sha256sum "$LOGS/TS3004d-aborted-attempt-receipt.json"
"$PY" -c "
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
print(json.dumps({k:d.get(k) for k in ('meeting_id','ok','error','diar','cutting','encode_warm','started_utc','finished_utc')}, indent=2, sort_keys=True))
" "$LOGS/TS3004d-aborted-attempt-receipt.json"
