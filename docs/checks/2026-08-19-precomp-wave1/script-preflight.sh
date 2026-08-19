#!/usr/bin/env bash
# PRECOMP wave-1 preflight: pytest, roster (--summary-only), hash pins, asset presence,
# GPU health. No diar contact, no server contact.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp/env.sh
exec > "$LOGS/preflight.log" 2>&1

echo "=== preflight start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "--- repo state ---"
git -C "$REPO" rev-parse HEAD
git -C "$REPO" status --porcelain | head -20
echo "porcelain lines: $(git -C "$REPO" status --porcelain | wc -l)"

echo
echo "--- hash pins ---"
fail=0
check() { # name path expected
  local n="$1" p="$2" e="$3"
  if [ ! -e "$p" ]; then echo "MISSING $n: $p"; fail=1; return; fi
  local got; got=$(sha256sum "$p" | awk '{print $1}')
  if [ "$got" = "$e" ]; then echo "OK   $n  $got  $p"; else echo "MISMATCH $n expected=$e got=$got  $p"; fail=1; fi
}
check llama-server        "$LLAMA_BIN"    "$LLAMA_BIN_SHA256"
check qwen3-omni-q4km     "$MODEL_GGUF"   "$MODEL_SHA256"
check qwen3-omni-mmproj   "$MMPROJ_GGUF"  "$MMPROJ_SHA256"
check nemo-speech-binary  "$DIAR_BIN"     "$DIAR_BIN_SHA256"
check diar-sortformer-q8  "$DIAR_GGUF"    "$DIAR_GGUF_SHA256"
echo "hash-pin fail flag: $fail"

echo
echo "--- llama.cpp build commit ---"
git -C "$LLAMA_DIR" rev-parse HEAD
echo "dirty: $(git -C "$LLAMA_DIR" status --porcelain | wc -l)"
cd "$(dirname "$LLAMA_BIN")" && ./llama-server --version 2>&1 | head -3

echo
echo "--- arm-config (pinned Arm B source) ---"
ls -l "$ARM_CONFIG"
sha256sum "$ARM_CONFIG"
"$PY" -c "import json,sys; d=json.load(open(sys.argv[1])); print('arms:', sorted(d)); b=d['B']; print('tool_name:', b['tool_name']); print('checkpoint_sha256:', b['checkpoint_sha256']); print('argv0:', b['command_template'][0])" "$ARM_CONFIG"

echo
echo "--- feature cache (ami-q4km) BEFORE ---"
echo "entries: $(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)"
echo "bytes:   $(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')"

echo
echo "--- NXT annotations root ---"
ls -d "$DATA/datasets/ami/annotations/manual_1.6.2" && ls "$DATA/datasets/ami/annotations/manual_1.6.2" | head -12

echo
echo "--- pytest (full meeting-repo suite) ---"
cd "$REPO"
source /home/chao/.venvs/speechrl/bin/activate
python -m pytest -q 2>&1 | tail -25

echo
echo "--- runner --summary-only (roster + ceilings, exclusion gate) ---"
PYTHONPATH="$REPO/src" "$PY" "$REPO/scripts/run_precomp.py" --wave 1 --data-dir "$DATA" --summary-only

echo
echo "--- dev-18 audio presence + durations ---"
PYTHONPATH="$REPO/src" "$PY" - <<'PYEOF'
import os, sys, wave, contextlib
from pathlib import Path
sys.path.insert(0, os.environ["REPO"] + "/src")
from meeting_minutes_agent.precomp.roster import default_wave_meetings
from meeting_minutes_agent.precomp.pipeline import require_meeting_audio_path, DEFAULT_AMI_AUDIO_ROOT_RELATIVE
data = Path(os.environ["DATA"])
total = 0.0
for m in sorted(default_wave_meetings(1)):
    try:
        p = require_meeting_audio_path(m, data_dir=data, ami_audio_root_relative=DEFAULT_AMI_AUDIO_ROOT_RELATIVE)
    except Exception as e:
        print(f"{m}: MISSING ({type(e).__name__}: {e})")
        continue
    try:
        with contextlib.closing(wave.open(str(p))) as w:
            dur = w.getnframes() / float(w.getframerate())
    except Exception as e:
        dur = float("nan")
        print(f"{m}: {p} (duration read failed: {e})")
        continue
    total += dur
    est_slices = max(1, round(dur / 90.0))
    print(f"{m}: {dur:8.1f}s  est_slices/source~{est_slices:3d}  est_calls(2 sources)~{est_slices*2:3d}  {p}")
print(f"TOTAL audio: {total:.1f}s = {total/3600:.2f} h; crude est encode calls = {round(total/90.0)*2}")
PYEOF

echo
echo "--- GPU health ---"
nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,clocks.sm,clocks.max.sm,pstate,temperature.gpu,power.draw,clocks_throttle_reasons.active --format=csv
echo "=== preflight end $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
