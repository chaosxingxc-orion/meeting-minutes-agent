#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
REPO=/mnt/d/chao_workspace/exploring-l4-intelligence/papers/meeting-minutes-agent
S=/mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad
cd "$REPO"
source ~/.venvs/speechrl/bin/activate
export PYTHONPATH="$REPO/src"
python "$S/ablations.py" \
  --read-verdict "$REPO/docs/checks/2026-08-19-g1-floors-read/verdict.json" \
  --out-dir "$REPO/docs/checks/2026-08-19-g1-floors-read"
cp "$S/ablations.py" "$REPO/docs/checks/2026-08-19-g1-floors-read/ablations.py"
