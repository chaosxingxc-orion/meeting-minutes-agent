#!/usr/bin/env bash
# G1-PATH preflight: repo state, hash pins, llama.cpp build commit, roster,
# VAD-supplement presence for the Z-nodiar arm, and the two chunk plans --
# the REGISTERED-cap plan (the structural finding) and the machinery-probe
# plan this flight actually runs. CPU-only: --list-chunks rebuilds slice plans
# from PRECOMP's on-disk cache with zero model contact.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1path/env.sh
exec > "$LOGS/preflight.log" 2>&1

echo "=== G1-PATH preflight start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "--- repo state ---"
git -C "$REPO" rev-parse HEAD
git -C "$REPO" status --porcelain | head -20
echo "porcelain lines: $(git -C "$REPO" status --porcelain | wc -l)"
git -C "$REPO" log --oneline -3

echo
echo "--- hash pins ---"
fail=0
check() { local n="$1" p="$2" e="$3"
  if [ ! -e "$p" ]; then echo "MISSING $n: $p"; fail=1; return; fi
  local got; got=$(sha256sum "$p" | awk '{print $1}')
  if [ "$got" = "$e" ]; then echo "OK   $n  $got  $p"; else echo "MISMATCH $n expected=$e got=$got  $p"; fail=1; fi
}
check llama-server      "$LLAMA_BIN"   "$LLAMA_BIN_SHA256"
check qwen3-omni-q4km   "$MODEL_GGUF"  "$MODEL_SHA256"
check qwen3-omni-mmproj "$MMPROJ_GGUF" "$MMPROJ_SHA256"
echo "hash-pin fail flag: $fail"
got_commit=$(git -C "$LLAMA_DIR" rev-parse HEAD)
echo "llama.cpp HEAD: $got_commit"
[ "$got_commit" = "$LLAMA_BUILD_COMMIT" ] && echo "build-commit: OK vs pin" || echo "build-commit: MISMATCH vs pin"
echo "dirty: $(git -C "$LLAMA_DIR" status --porcelain | wc -l)"

echo
echo "--- PRECOMP inputs the four arms rebuild from ---"
echo "rttm files:    $(ls "$DERIVED_ROOT/rttm" 2>/dev/null | wc -l)"
echo "tool slice dirs:   $(ls "$DERIVED_ROOT/slices/tool" 2>/dev/null | wc -l)"
echo "oracle slice dirs: $(ls "$DERIVED_ROOT/slices/oracle" 2>/dev/null | wc -l)"
echo "vad slice dirs:    $(ls "$DERIVED_ROOT/slices/vad" 2>/dev/null | wc -l)"
echo "vad manifests:     $(ls "$VAD_MANIFEST_DIR" 2>/dev/null | wc -l)"
for m in ES2011a IS1008a; do
  echo "  $m: rttm=$( [ -f "$DERIVED_ROOT/rttm/$m.rttm" ] && echo yes || echo NO )" \
       "vad_manifest=$( [ -f "$VAD_MANIFEST_DIR/$m.json" ] && echo yes || echo NO )" \
       "tool_wavs=$(ls "$DERIVED_ROOT/slices/tool/$m" 2>/dev/null | wc -l)" \
       "oracle_wavs=$(ls "$DERIVED_ROOT/slices/oracle/$m" 2>/dev/null | wc -l)" \
       "vad_wavs=$(ls "$DERIVED_ROOT/slices/vad/$m" 2>/dev/null | wc -l)"
done

echo
echo "--- feature cache (ami-q4km) BEFORE the flight ---"
echo "entries: $(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)"
echo "bytes:   $(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')"

echo
echo "--- run-dir BEFORE ---"
echo "exists: $( [ -d "$RUN_DIR" ] && echo YES || echo no )"
ls "$RUN_DIR/receipts" 2>/dev/null | wc -l

echo
echo "--- run_g1 --summary-only (roster, arms, registered ceilings) ---"
PYTHONPATH="$REPO/src" "$PY" "$REPO/scripts/run_g1.py" --mode path --data-dir "$DATA" \
  --meetingqa-root "$MEETINGQA_ROOT" --ami-root "$AMI_ROOT" --summary-only

echo
echo "=========================================================================="
echo "--- STRUCTURAL FINDING: the plan at the REGISTERED N=200 QA cap ---"
echo "run_g1.run_item dispatches the WHOLE capped question set to EVERY"
echo "(meeting, arm), instead of the questions attached to THAT meeting."
echo "=========================================================================="
PYTHONPATH="$REPO/src" "$PY" "$REPO/scripts/run_g1.py" --mode path --data-dir "$DATA" \
  --vad-manifest-dir "$VAD_MANIFEST_DIR" \
  --meetingqa-root "$MEETINGQA_ROOT" --ami-root "$AMI_ROOT" \
  --list-chunks > "$LOGS/chunkplan-registered-cap.json" 2>"$LOGS/chunkplan-registered-cap.err"
echo "rc=$?"
tail -5 "$LOGS/chunkplan-registered-cap.err"
"$PY" - "$LOGS/chunkplan-registered-cap.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print("n_work_items:", d["n_work_items"], " n_chunks:", d["n_chunks"])
tot = 0
for c in d["chunks"]:
    print("  chunk %d: est_wall=%.1fs items=%d" % (c["index"], c["estimated_wall_seconds"], len(c["items"])))
    for it in c["items"]:
        print("    %-9s %-9s transcribe=%3d minutes=%d qa=%3d -> calls=%3d"
              % (it["meeting_id"], it["arm"], it["n_transcribe"], it["n_minutes"], it["n_qa"], it["n_calls"]))
        tot += it["n_calls"]
print("PLANNED TOTAL CALLS AT THE REGISTERED CAP:", tot)
print("floors prereg SS5 registered PATH size: ~250 requests, <=0.5 GPU-h")
PYEOF

echo
echo "=========================================================================="
echo "--- THE PLAN THIS FLIGHT RUNS: QA head at machinery-probe cap $PATH_QA_CAP ---"
echo "=========================================================================="
PYTHONPATH="$REPO/src" "$PY" "$REPO/scripts/run_g1.py" --mode path --data-dir "$DATA" \
  --vad-manifest-dir "$VAD_MANIFEST_DIR" \
  --meetingqa-root "$MEETINGQA_ROOT" --ami-root "$AMI_ROOT" \
  --qa-cap "$PATH_QA_CAP" \
  --max-calls "$PATH_MAX_CALLS" --max-gpu-hours "$PATH_MAX_GPU_HOURS" --max-wall-hours "$PATH_MAX_WALL_HOURS" \
  --list-chunks > "$LOGS/chunkplan-flight.json" 2>"$LOGS/chunkplan-flight.err"
echo "rc=$?"
cat "$LOGS/chunkplan-flight.err"
"$PY" - "$LOGS/chunkplan-flight.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print("n_work_items:", d["n_work_items"], " n_chunks:", d["n_chunks"])
tot = 0
for c in d["chunks"]:
    print("  chunk %d: est_wall=%.1fs items=%d" % (c["index"], c["estimated_wall_seconds"], len(c["items"])))
    for it in c["items"]:
        print("    %-9s %-9s transcribe=%3d minutes=%d qa=%3d -> calls=%3d"
              % (it["meeting_id"], it["arm"], it["n_transcribe"], it["n_minutes"], it["n_qa"], it["n_calls"]))
        tot += it["n_calls"]
print("FLIGHT TOTAL CALLS:", tot, "against this flight's own fail-closed max-calls ceiling")
PYEOF

echo
echo "--- arm/plan provenance cross-check (CPU-only, zero model contact) ---"
PYTHONPATH="$REPO/src" "$PY" - <<'PYEOF'
import os, sys
from pathlib import Path
repo = os.environ["REPO"]
sys.path.insert(0, repo + "/src"); sys.path.insert(0, repo + "/scripts")
from meeting_minutes_agent.corpora.nxt.corpus import NxtCorpus
from meeting_minutes_agent.probes import g1, g1_campaign
from run_g1 import resolve_slice_plan
data = Path(os.environ["DATA"]); derived = Path(os.environ["DERIVED_ROOT"])
nxt = NxtCorpus(data / "datasets/ami/annotations/manual_1.6.2")
vadman = Path(os.environ["VAD_MANIFEST_DIR"])
for m in g1_campaign.PATH_MEETINGS:
    for arm in g1.ARMS:
        plan, sdir = resolve_slice_plan(arm, m, data_dir=data, derived_root=derived,
                                        nxt_corpus=nxt, vad_manifest_dir=vadman)
        missing = [s.index for s in plan.slices
                   if not (data / sdir / m / g1.slice_filename(m, s.index)).is_file()]
        print("%-9s %-9s mode=%-5s prov=%-12s slices=%3d slice_dir=%s missing_wavs=%s"
              % (m, arm, plan.mode.value, str(plan.turn_provenance and plan.turn_provenance.value),
                 len(plan.slices), sdir, missing if missing else "none"))
PYEOF

echo
echo "--- GPU health / orphans ---"
nvidia-smi --query-gpu=name,utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu,power.draw --format=csv
pgrep -ax llama-server || echo "llama-server: none"
pgrep -af run_g1.py || echo "run_g1: none"
echo "=== G1-PATH preflight end $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
