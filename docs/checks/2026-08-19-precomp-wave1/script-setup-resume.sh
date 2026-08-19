#!/usr/bin/env bash
# Recreate the PRECOMP wave-1 operator working dir for the RESUME pass.
# The predecessor's scratchpad/precomp/ is gone; the archived scripts are the
# authority, so they are restored byte-for-byte from the committed receipt dir.
set -euo pipefail

SP=/mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp
ARC=/mnt/d/chao_workspace/exploring-l4-intelligence/papers/meeting-minutes-agent/docs/checks/2026-08-19-precomp-wave1

mkdir -p "$SP/logs/meetings"

cp "$ARC/script-env.sh"   "$SP/env.sh"
cp "$ARC/script-serve.sh" "$SP/serve.sh"
cp "$ARC/budget_ledger.py" "$SP/budget_ledger.py"
cp "$ARC/table.py"         "$SP/table.py"
cp "$ARC/aggregate.py"     "$SP/aggregate.py"
chmod +x "$SP"/*.sh "$SP"/*.py

echo "--- restored (sha256 vs archive) ---"
sha256sum "$SP/env.sh" "$SP/serve.sh" "$SP/budget_ledger.py" "$SP/table.py" "$SP/aggregate.py"
sha256sum "$ARC/script-env.sh" "$ARC/script-serve.sh" "$ARC/budget_ledger.py" "$ARC/table.py" "$ARC/aggregate.py"

echo "--- line endings ---"
file "$SP/env.sh" "$SP/serve.sh"

echo "--- syntax ---"
bash -n "$SP/env.sh" && echo "env.sh OK"
bash -n "$SP/serve.sh" && echo "serve.sh OK"

echo "--- env sanity (sourced) ---"
set +u
source "$SP/env.sh"
set -u
echo "REPO=$REPO"
echo "DATA=$DATA"
echo "OUT_DIR=$OUT_DIR"
echo "RUN_DIR=$RUN_DIR"
echo "CACHE=$LLAMA_MTMD_FEAT_CACHE_DIR"
echo "YIELD_FILE=$YIELD_FILE  exists=$( [ -e "$YIELD_FILE" ] && echo YES || echo no )"
echo "PY=$PY"
ls -d "$OUT_DIR" "$LLAMA_MTMD_FEAT_CACHE_DIR" "$ARM_CONFIG"
echo "SETUP-DONE"
