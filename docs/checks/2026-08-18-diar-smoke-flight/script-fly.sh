#!/bin/bash
# DIAR-SMOKE flight: the real pinned-tool run over six dev-18 meetings,
# arms A (NeMo fp32) + B (NeMo-Speech.cpp CUDA q8_0), budget-guarded by the
# launcher itself. Structural counts only afterwards -- no DER, no reference
# comparison, no RTTM content interpretation.
#
# ALL output goes to files (fly-wrapper.log / launcher.log / gpu-health.log):
# the Windows console can detach mid-flight on this machine, and a write to a
# dead pty must never be able to kill the launcher (pprompt flight's own
# fly-wrapper.log pattern).
set -u
SP=/mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/diar
LOGS=$SP/logs
mkdir -p "$LOGS"
exec > "$LOGS/fly-wrapper.log" 2>&1

export PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

REPO=/mnt/d/chao_workspace/exploring-l4-intelligence/papers/meeting-minutes-agent
DATA=/mnt/e/chao_workspace/exploring-l4-intelligence/speechrl-data
RUNROOT=$DATA/derived/meeting-minutes/diar-smoke
TOOLING=$RUNROOT/tooling
OUT=$RUNROOT/runs/2026-08-18-diar-smoke
PY=/home/chao/.venvs/speechrl/bin/python

mkdir -p "$OUT"

echo "=== flight start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

# GPU health sampler, every 30 s, mirrors the pattr flight's gpu-health.log.
GPUHEALTH=$LOGS/gpu-health.log
: > "$GPUHEALTH"
(
  while true; do
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $(nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu,power.draw,clocks_throttle_reasons.active --format=csv,noheader,nounits 2>/dev/null)" >> "$GPUHEALTH"
    sleep 30
  done
) &
SAMPLER_PID=$!

echo "--- pre-run GPU snapshot ---"
nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu --format=csv,noheader 2>/dev/null

PYTHONPATH=$REPO/src "$PY" "$REPO/scripts/launch_diar_smoke.py" \
  --data-dir "$DATA" \
  --arm-config "$TOOLING/arm-config.json" \
  --arms A B \
  --out-dir "$OUT" \
  --resume > "$LOGS/launcher.log" 2>&1
LAUNCH_RC=$?

kill $SAMPLER_PID 2>/dev/null
wait $SAMPLER_PID 2>/dev/null

echo "=== launcher rc=$LAUNCH_RC ==="

echo "=== structural stats (line counts + speaker-label counts only) ==="
{
  for arm in A B; do
    for m in ES2011a ES2011b IS1008b IS1008d TS3004b TS3004d; do
      f=$OUT/rttm/$arm/$m.rttm
      if [ -f "$f" ]; then
        lines=$(wc -l < "$f")
        speakers=$(awk '$1=="SPEAKER"{print $8}' "$f" | sort -u | wc -l)
        labels=$(awk '$1=="SPEAKER"{print $8}' "$f" | sort -u | paste -sd, -)
        echo "$arm/$m: $lines lines, $speakers speaker labels [$labels]"
      else
        echo "$arm/$m: NO RTTM"
      fi
    done
  done
} > "$LOGS/structural-stats.log"
cat "$LOGS/structural-stats.log"

echo "=== run-dir artefact hashes ==="
( cd "$OUT" && find . -type f \( -name '*.rttm' -o -name '*.json' \) | sort | sed 's|^\./||' | xargs sha256sum ) > "$LOGS/run-dir-artefacts.sha256"
wc -l "$LOGS/run-dir-artefacts.sha256"

echo "=== post-run GPU snapshot ==="
nvidia-smi --query-gpu=utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu --format=csv,noheader 2>/dev/null

echo "=== tree state after flight ==="
git -C "$REPO" rev-parse HEAD
git -C "$REPO" status --porcelain
echo "=== flight end $(date -u +%Y-%m-%dT%H:%M:%SZ) rc=$LAUNCH_RC ==="
exit $LAUNCH_RC
