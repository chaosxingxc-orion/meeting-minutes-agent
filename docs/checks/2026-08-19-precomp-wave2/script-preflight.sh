#!/usr/bin/env bash
# PRECOMP wave-2 preflight: pytest, hash pins, --summary-only roster (exclusion gate),
# wave-2 pre-charge dry read over any receipts already on disk, per-meeting audio
# presence + crude encode-call estimate, GPU health. No diar contact, no server contact.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp2/env.sh
exec > "$LOGS/preflight.log" 2>&1

echo "=== wave-2 preflight start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "--- repo state ---"
git -C "$REPO" rev-parse HEAD
git -C "$REPO" status --porcelain | head -20
echo "porcelain lines: $(git -C "$REPO" status --porcelain | wc -l)"
git -C "$REPO" log --oneline -3

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
echo "--- feature cache (ami-q4km) BEFORE wave-2 ---"
echo "entries: $(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)"
echo "bytes:   $(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')"
echo "free on /home: $(df -h /home/chao | tail -1)"
echo "free on E:   : $(df -h /mnt/e | tail -1)"

echo
echo "--- wave-2 receipts already on disk ---"
ls "$OUT_DIR/receipts" 2>/dev/null | sort
echo "count: $(ls "$OUT_DIR/receipts" 2>/dev/null | wc -l)"

echo
echo "--- stop files ---"
echo "coordinator YIELD_FILE=$YIELD_FILE exists=$( [ -e "$YIELD_FILE" ] && echo YES || echo no )"
echo "operator MY_STOP=$MY_STOP exists=$( [ -e "$MY_STOP" ] && echo YES || echo no )"

echo
echo "--- pytest (full meeting-repo suite) ---"
cd "$REPO"
source /home/chao/.venvs/speechrl/bin/activate
python -m pytest -q 2>&1 | tail -15

echo
echo "--- runner --summary-only wave 2 (roster + ceilings, exclusion gate) ---"
PYTHONPATH="$REPO/src" "$PY" "$REPO/scripts/run_precomp.py" --wave 2 --data-dir "$DATA" --summary-only

echo
echo "--- roster cross-checks: wave-2 disjoint from dev-18, gate clean, no reserved role ---"
PYTHONPATH="$REPO/src" "$PY" - <<'PYEOF'
import json, os, sys
repo = os.environ["REPO"]
sys.path.insert(0, repo + "/src")
from meeting_minutes_agent.precomp.roster import (
    default_wave_meetings, usable_discovery_exposable_roster, assert_wave_roster_admissible,
)
from meeting_minutes_agent.corpora.roles import FROZEN_DEV_18, load_role_registry, MeetingRole

reg = load_role_registry()
w2 = sorted(default_wave_meetings(2))
w1 = sorted(default_wave_meetings(1))
assert_wave_roster_admissible(w2)
overlap = sorted(set(w1) & set(w2))
allexp = sorted(usable_discovery_exposable_roster())
roles = {}
for m in w2:
    roles.setdefault(reg.role_of(m).value, []).append(m)
print(json.dumps({
    "wave2_n": len(w2),
    "wave1_n": len(w1),
    "overlap_with_dev18": overlap,
    "usable_discovery_exposable_n": len(allexp),
    "wave2_roles": {k: len(v) for k, v in sorted(roles.items())},
    "gate": "assert_wave_roster_admissible PASSED for all %d" % len(w2),
}, indent=2, sort_keys=True))
print("wave2 roster:")
print(" ".join(w2))
PYEOF

echo
echo "--- wave-2 budget pre-charge dry read (from receipts on disk) ---"
PYTHONPATH="$REPO/src" "$PY" - <<'PYEOF'
import json, os, sys
from pathlib import Path
repo = os.environ["REPO"]
sys.path.insert(0, repo + "/src")
sys.path.insert(0, repo + "/scripts")
from meeting_minutes_agent.precomp.roster import default_wave_meetings
from meeting_minutes_agent.precomp.receipts import already_done
from meeting_minutes_agent.precomp.budget import PrecompBudget, PrecompBudgetExceeded, ceilings_for_wave
from run_precomp import load_wave_receipts

out_dir = Path(os.environ["OUT_DIR"])
roster = sorted(default_wave_meetings(2))
skip = [m for m in roster if already_done(out_dir, m)]
todo = [m for m in roster if not already_done(out_dir, m)]
receipts = load_wave_receipts(out_dir)
budget = PrecompBudget(ceilings_for_wave(2))
budget.precharge(receipts)
try:
    budget.check_all(); verdict = "ADMISSIBLE"
except PrecompBudgetExceeded as exc:
    verdict = "REFUSED: " + str(exc)
print(json.dumps({"roster_n": len(roster), "resume_skips_n": len(skip), "resume_runs_n": len(todo),
                  "resume_skips": skip}, indent=2))
print("precharge from %d receipts -> %s" % (len(receipts), verdict))
print(json.dumps(budget.to_dict(), indent=2, sort_keys=True))
PYEOF

echo
echo "--- wave-2 audio presence + crude encode-call / wall estimate ---"
PYTHONPATH="$REPO/src" "$PY" - <<'PYEOF'
import os, sys, wave, contextlib
from pathlib import Path
repo = os.environ["REPO"]
sys.path.insert(0, repo + "/src")
from meeting_minutes_agent.precomp.roster import default_wave_meetings
from meeting_minutes_agent.precomp.receipts import already_done
from meeting_minutes_agent.precomp.pipeline import require_meeting_audio_path, DEFAULT_AMI_AUDIO_ROOT_RELATIVE
data = Path(os.environ["DATA"]); out_dir = Path(os.environ["OUT_DIR"])
total = 0.0; missing = []; n = 0
for m in sorted(default_wave_meetings(2)):
    if already_done(out_dir, m):
        continue
    try:
        p = require_meeting_audio_path(m, data_dir=data, ami_audio_root_relative=DEFAULT_AMI_AUDIO_ROOT_RELATIVE)
    except Exception as e:
        print(f"{m}: MISSING ({type(e).__name__}: {e})"); missing.append(m); continue
    try:
        with contextlib.closing(wave.open(str(p))) as w:
            dur = w.getnframes() / float(w.getframerate())
    except Exception as e:
        print(f"{m}: {p} (duration read failed: {e})"); continue
    total += dur; n += 1
    est = max(1, round(dur / 90.0))
    print(f"{m}: {dur:8.1f}s  est_slices/source~{est:3d}  est_calls(2 src)~{est*2:3d}")
calls = round(total / 90.0) * 2
print(f"REMAINING meetings: {n}; audio {total:.1f}s = {total/3600:.2f} h; crude est encode calls = {calls}")
# wave-1 observed rates (docs/checks/2026-08-19-precomp-wave1/per-meeting-table-final.txt):
# 738 calls / 4955.1 s encode wall / 3633.2 s encode GPU / 1186.0 s diar wall / 270.8 s diar GPU
# over 18 meetings.
print(f"projected encode wall  ~ {calls * 4955.1/738/3600:.2f} h")
print(f"projected encode GPU-h ~ {calls * 3633.2/738/3600:.2f} h  (ceiling 8.0)")
print(f"projected diar  GPU-h  ~ {n * 270.8/18/3600:.2f} h  (ceiling 2.0)")
print(f"projected total wall   ~ {(calls*4955.1/738 + n*1186.0/18 + n*369.7/18)/3600:.2f} h")
print(f"MISSING AUDIO: {missing}")
PYEOF

echo
echo "--- NXT annotations root ---"
ls -d "$DATA/datasets/ami/annotations/manual_1.6.2" && ls "$DATA/datasets/ami/annotations/manual_1.6.2" | head -12

echo
echo "--- GPU health ---"
nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,clocks.sm,clocks.max.sm,pstate,temperature.gpu,power.draw,clocks_throttle_reasons.active --format=csv
pgrep -ax llama-server || echo "(no llama-server running)"
echo "=== wave-2 preflight end $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "PREFLIGHT-DONE"
