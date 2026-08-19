#!/usr/bin/env bash
# Shared preflight (both G1 missions): the full test suite at 8aedcb9.
# Expectation: 1512 passed, 6 skipped (fix commit message). PYTHONDONTWRITEBYTECODE
# keeps bytecode out of the frozen scoring package; .pytest_cache is gitignored.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1path2/env.sh
exec > "$LOGS/pytest-preflight.log" 2>&1
echo "=== pytest preflight start $(date -u +%Y-%m-%dT%H:%M:%SZ) at $(git -C "$REPO" rev-parse HEAD) ==="
cd "$REPO"
PYTHONPATH="$REPO/src" "$PY" -m pytest -q
RC=$?
echo "pytest rc=$RC"
echo "repo porcelain lines after pytest: $(git -C "$REPO" status --porcelain | wc -l)"
git -C "$REPO" status --porcelain | head -10
echo "=== pytest preflight end $(date -u +%Y-%m-%dT%H:%M:%SZ) rc=$RC ==="
echo "PYTEST-DONE rc=$RC"
