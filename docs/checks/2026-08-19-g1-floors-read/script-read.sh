#!/usr/bin/env bash
# G1 floors campaign -- the registered ONE-SHOT descriptive read.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
REPO=/mnt/d/chao_workspace/exploring-l4-intelligence/papers/meeting-minutes-agent
export SPEECHRL_DATA_DIR=/mnt/e/chao_workspace/exploring-l4-intelligence/speechrl-data
RUN_DIR="$SPEECHRL_DATA_DIR/derived/meeting-minutes/g1/runs/2026-08-19-g1-floors"
VAD_MANIFEST_DIR="$SPEECHRL_DATA_DIR/derived/meeting-minutes/precomp/slices/vad-manifest"
OUT_DIR="$REPO/docs/checks/2026-08-19-g1-floors-read"

cd "$REPO"
source ~/.venvs/speechrl/bin/activate
export PYTHONPATH="$REPO/src"

# ORC state-space guard: an address-space rlimit so an infeasible ORC term
# raises MemoryError (recorded as an orc_refusal) instead of inviting the
# OOM killer -- the same discipline the P-PROMPT read ran under.
ulimit -v 33554432   # 32 GiB address space

echo "host mem:"; free -g | head -2
echo "repo HEAD: $(git rev-parse HEAD)"
echo "dirty lines: $(git status --porcelain | wc -l)"
echo "run dir: $RUN_DIR"
echo "vad manifests: $(ls "$VAD_MANIFEST_DIR" | wc -l)"
echo "out dir: $OUT_DIR"

MEETINGS=$(python - <<'PY'
from meeting_minutes_agent.probes import g1_campaign
print(" ".join(g1_campaign.meetings_for_mode("floors")))
PY
)
echo "meetings ($(echo $MEETINGS | wc -w)): $MEETINGS"

echo "=== READ START $(date -u +%FT%TZ) ==="
python scripts/g1_read.py \
  --data-dir "$SPEECHRL_DATA_DIR" \
  --responses-dir "$RUN_DIR/responses" \
  --vad-manifest-dir "$VAD_MANIFEST_DIR" \
  --meetings $MEETINGS \
  --out-dir "$OUT_DIR"
echo "=== READ DONE rc=$? $(date -u +%FT%TZ) ==="
echo "run dir untouched check:"
ls -la "$RUN_DIR/responses"
