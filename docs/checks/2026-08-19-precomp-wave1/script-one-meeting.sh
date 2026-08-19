#!/usr/bin/env bash
# Single-meeting PRECOMP invocation (pipeline validation before the full loop;
# also the exact command the loop runs per meeting).
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp/env.sh
M="${1:?meeting id required}"
mkdir -p "$OUT_DIR/transport-receipts" "$LOGS/meetings"
echo "=== $M start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
T0=$(date +%s)
PYTHONPATH="$REPO/src" "$PY" "$REPO/scripts/run_precomp.py" \
  --wave 1 \
  --data-dir "$DATA" \
  --meetings "$M" \
  --arm-config "$ARM_CONFIG" \
  --server-url "$BASE_URL" \
  --model-path "$MODEL_GGUF" \
  --model-sha256 "$MODEL_SHA256" \
  --slots 1 \
  --out-dir "$OUT_DIR" \
  --workers 8 \
  --featcache-dataset "$FEATCACHE_DATASET" \
  --encoder "$FEATCACHE_ENCODER" \
  --timeout-seconds 600 \
  --resume 2>&1 | tee "$LOGS/meetings/$M.log"
RC=${PIPESTATUS[0]}
T1=$(date +%s)
[ -f "$OUT_DIR/transport-receipt.json" ] && cp "$OUT_DIR/transport-receipt.json" "$OUT_DIR/transport-receipts/$M.json"
echo "=== $M rc=$RC wall=$((T1-T0))s ==="
"$PY" -c "
import json,sys
from pathlib import Path
p=Path(sys.argv[1])/'receipts'/(sys.argv[2]+'-receipt.json')
d=json.loads(p.read_text(encoding='utf-8'))
print('ok:', d['ok'], '| error:', d['error'])
print('diar:', {k:v for k,v in d['diar'].items() if k!='contact'})
print('diar contact rc:', (d['diar'].get('contact') or {}).get('return_code'))
print('slice_plans:', d['slice_plans'])
print('cutting:', {k:v for k,v in d['cutting'].items()})
print('encode n_calls:', d['encode_warm']['n_calls'], 'wall:', d['encode_warm']['wall_seconds'])
m=d['metrics']
print('metrics turn_counts:', m.get('turn_counts'))
print('metrics slice_counts:', m.get('slice_counts'))
print('metrics cache:', m.get('cache'))
print('metrics walls:', m.get('walls'))
bd=m.get('boundary_displacement') or {}
print('boundary_displacement:', {k:v for k,v in bd.items() if k!='displacements_s'})
" "$OUT_DIR" "$M"
exit $RC
