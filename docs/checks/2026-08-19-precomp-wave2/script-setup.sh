#!/usr/bin/env bash
# Install + syntax-verify the PRECOMP wave-2 operator working directory.
set -u
SP=/mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp2
ARC=/mnt/d/chao_workspace/exploring-l4-intelligence/papers/meeting-minutes-agent/docs/checks/2026-08-19-precomp-wave1

cp "$ARC/budget_ledger.py" "$SP/budget_ledger.py"
cp "$ARC/table.py" "$SP/table.py"

# The Windows-side editor may leave CRLF; bash refuses those.
for f in "$SP"/*.sh "$SP"/*.py; do sed -i 's/\r$//' "$f"; done
chmod +x "$SP"/*.sh "$SP"/*.py

echo "--- line endings ---"
file "$SP"/*.sh | sed 's|.*/precomp2/||'

echo "--- bash syntax ---"
for f in "$SP"/*.sh; do bash -n "$f" && echo "OK  $(basename "$f")"; done

echo "--- python syntax ---"
for f in "$SP"/*.py; do /home/chao/.venvs/speechrl/bin/python -m py_compile "$f" && echo "OK  $(basename "$f")"; done
rm -rf "$SP/__pycache__"

echo "--- env sourced ---"
set +u; source "$SP/env.sh"; set -u
echo "REPO=$REPO"
echo "DATA=$DATA"
echo "OUT_DIR=$OUT_DIR"
echo "LOGS=$LOGS"
echo "CACHE=$LLAMA_MTMD_FEAT_CACHE_DIR"
echo "MY_STOP=$MY_STOP exists=$( [ -e "$MY_STOP" ] && echo YES || echo no )"
echo "YIELD_FILE=$YIELD_FILE exists=$( [ -e "$YIELD_FILE" ] && echo YES || echo no )"
echo "PY=$PY"
ls -d "$ARM_CONFIG" "$LLAMA_MTMD_FEAT_CACHE_DIR" "$OUT_DIR" "$OUT_DIR/receipts" "$LLAMA_BIN" "$DIAR_BIN"
echo "SETUP-DONE"
