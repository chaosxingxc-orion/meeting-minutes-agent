#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
REPO=/mnt/d/chao_workspace/exploring-l4-intelligence/papers/meeting-minutes-agent
export SPEECHRL_DATA_DIR=/mnt/e/chao_workspace/exploring-l4-intelligence/speechrl-data
RUN_DIR="$SPEECHRL_DATA_DIR/derived/meeting-minutes/g1/runs/2026-08-19-g1-floors"
OUT_DIR="$REPO/docs/checks/2026-08-19-g1-floors-read"
cd "$REPO"
source ~/.venvs/speechrl/bin/activate
export PYTHONPATH="$REPO/src"
python /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/supplement.py \
  --data-dir "$SPEECHRL_DATA_DIR" \
  --responses-dir "$RUN_DIR/responses" \
  --read-verdict "$OUT_DIR/verdict.json" \
  --out-dir "$OUT_DIR"
