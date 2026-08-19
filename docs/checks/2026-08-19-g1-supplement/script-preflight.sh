#!/usr/bin/env bash
# G1 VAD supplement preflight: repo state, hash pins, llama.cpp build commit,
# full pytest, roster + ceilings (--summary-only under the g1-supplement
# profile), per-meeting audio presence and crude VAD slice projection, GPU
# health. No server contact, no diar contact, no model contact.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1sup/env.sh
exec > "$LOGS/preflight.log" 2>&1

echo "=== G1 VAD supplement preflight start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
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
check llama-server      "$LLAMA_BIN"   "$LLAMA_BIN_SHA256"
check qwen3-omni-q4km   "$MODEL_GGUF"  "$MODEL_SHA256"
check qwen3-omni-mmproj "$MMPROJ_GGUF" "$MMPROJ_SHA256"
echo "hash-pin fail flag: $fail"

echo
echo "--- llama.cpp build commit (pinned $LLAMA_BUILD_COMMIT) ---"
got_commit=$(git -C "$LLAMA_DIR" rev-parse HEAD)
echo "HEAD: $got_commit"
[ "$got_commit" = "$LLAMA_BUILD_COMMIT" ] && echo "build-commit: OK vs pin" || echo "build-commit: MISMATCH vs pin"
echo "dirty: $(git -C "$LLAMA_DIR" status --porcelain | wc -l)"
cd "$(dirname "$LLAMA_BIN")" && ./llama-server --version 2>&1 | head -3

echo
echo "--- feature cache (ami-q4km) BEFORE the supplement ---"
echo "entries: $(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)"
echo "bytes:   $(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')"

echo
echo "--- supplement out-dir / derived VAD dirs BEFORE ---"
echo "out-dir exists: $( [ -d "$OUT_DIR" ] && echo YES || echo no )"
ls "$OUT_DIR/receipts" 2>/dev/null | wc -l
echo "vad slice meeting dirs: $(ls "$VAD_SLICE_ROOT" 2>/dev/null | wc -l)"
echo "vad manifests:          $(ls "$VAD_MANIFEST_DIR" 2>/dev/null | wc -l)"
echo "wave-1 receipts (must stay untouched): $(ls "$REPO/docs/checks/2026-08-19-precomp-wave1/receipts" | wc -l)"

echo
echo "--- pytest (full meeting-repo suite) ---"
cd "$REPO"
source /home/chao/.venvs/speechrl/bin/activate
python -m pytest -q 2>&1 | tail -20

echo
echo "--- runner --summary-only : vad turn source + g1-supplement ceilings ---"
PYTHONPATH="$REPO/src" "$PY" "$REPO/scripts/run_precomp.py" --wave 1 --data-dir "$DATA" \
  --turn-sources vad --ceilings-profile g1-supplement --summary-only

echo
echo "--- default out-dir resolution for the g1-supplement profile ---"
PYTHONPATH="$REPO/src" "$PY" - <<'PYEOF'
import os, sys
repo = os.environ["REPO"]
sys.path.insert(0, repo + "/scripts")
sys.path.insert(0, repo + "/src")
from run_precomp import default_out_dir, vad_manifest_dir, vad_slice_dir, missing_required_args
from pathlib import Path
print("default_out_dir(1, 'g1-supplement') =", default_out_dir(1, "g1-supplement"))
derived = Path(os.environ["DERIVED_ROOT"])
print("vad_manifest_dir =", vad_manifest_dir(derived))
print("vad_slice_dir(ES2011a) =", vad_slice_dir(derived, "ES2011a"))
print("missing args for a vad-only real run (no --arm-config):",
      missing_required_args(turn_sources=("vad",), arm_config=None,
                            server_url="x", model_path="y", model_sha256="z"))
PYEOF

echo
echo "--- per-meeting audio presence + crude VAD slice projection ---"
PYTHONPATH="$REPO/src" "$PY" - <<'PYEOF'
import contextlib, os, sys, wave
from pathlib import Path
repo = os.environ["REPO"]
sys.path.insert(0, repo + "/src")
from meeting_minutes_agent.precomp.roster import default_wave_meetings, assert_wave_roster_admissible
from meeting_minutes_agent.precomp.pipeline import require_meeting_audio_path, DEFAULT_AMI_AUDIO_ROOT_RELATIVE
data = Path(os.environ["DATA"])
roster = sorted(default_wave_meetings(1))
assert_wave_roster_admissible(roster)
pass_a = set(os.environ["PASS_A_MEETINGS"].split())
pass_b = set(os.environ["PASS_B_MEETINGS"].split())
assert pass_a | pass_b == set(roster), "pass split does not cover the roster"
assert not (pass_a & pass_b), "pass split overlaps"
tot = {"A": 0.0, "B": 0.0}
est = {"A": 0, "B": 0}
for m in roster:
    grp = "A" if m in pass_a else "B"
    p = require_meeting_audio_path(m, data_dir=data, ami_audio_root_relative=DEFAULT_AMI_AUDIO_ROOT_RELATIVE)
    with contextlib.closing(wave.open(str(p))) as w:
        dur = w.getnframes() / float(w.getframerate())
    n = max(1, round(dur / 90.0))
    tot[grp] += dur
    est[grp] += n
    print(f"{m}  pass{grp}  {dur:8.1f}s  est_vad_slices~{n:3d}")
for g in ("A", "B"):
    print(f"pass {g}: audio {tot[g]:.1f}s ({tot[g]/3600:.2f} h)  est calls~{est[g]}  "
          f"est encode wall~{est[g]*6.8/60:.1f} min (6.8 s/contact, wave-1 measured)")
print(f"TOTAL est calls~{est['A']+est['B']} against the 500-call g1-supplement ceiling")
PYEOF

echo
echo "--- GPU health ---"
nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,clocks.sm,clocks.max.sm,pstate,temperature.gpu,power.draw,clocks_throttle_reasons.active --format=csv
echo "--- orphan processes ---"
pgrep -ax llama-server || echo "llama-server: none"
pgrep -af run_precomp.py || echo "run_precomp: none"
echo "=== G1 VAD supplement preflight end $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
