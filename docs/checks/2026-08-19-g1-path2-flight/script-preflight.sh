#!/usr/bin/env bash
# G1-PATH2 preflight: repo state at 8aedcb9, hash pins, llama.cpp build
# commit, roster, VAD-supplement presence, the flight chunk plan at the
# REGISTERED N=200 QA cap (the fix's planning-time verification: ES2011a's
# own 7 questions x 2 QA arms, IS1008a 0), and the arm/plan cross-check.
# CPU-only: --list-chunks rebuilds slice plans from PRECOMP's on-disk cache
# with zero model contact.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1path2/env.sh
exec > "$LOGS/preflight.log" 2>&1

echo "=== G1-PATH2 preflight start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
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
echo "--- run-dir BEFORE (must be FRESH: path2, not the first PATH run) ---"
echo "run-dir: $RUN_DIR"
echo "exists: $( [ -d "$RUN_DIR" ] && echo YES || echo no )"
echo "receipts already present: $(ls "$RUN_DIR/receipts" 2>/dev/null | wc -l)"
echo "stop-file: $YIELD_FILE  present: $( [ -e "$YIELD_FILE" ] && echo YES || echo no )"

echo
echo "--- run_g1 --summary-only (roster, arms, registered QA cap) ---"
PYTHONPATH="$REPO/src" "$PY" "$REPO/scripts/run_g1.py" --mode path --data-dir "$DATA" \
  --meetingqa-root "$MEETINGQA_ROOT" --ami-root "$AMI_ROOT" --summary-only

echo
echo "--- per-meeting QA routing at the REGISTERED cap (the 8aedcb9 fix) ---"
PYTHONPATH="$REPO/src" "$PY" - <<'PYEOF'
import os, sys
repo = os.environ["REPO"]
sys.path.insert(0, repo + "/src")
from meeting_minutes_agent.corpora.roles import load_role_registry
from meeting_minutes_agent.probes import g1, g1_campaign
qs = g1_campaign.load_dev18_usable_discovery_questions(
    meetingqa_root=os.environ["MEETINGQA_ROOT"], ami_root=os.environ["AMI_ROOT"],
    registry=load_role_registry())
capped = g1.select_capped_qa_questions(qs, cap=g1.QA_CAP_N, seed=g1.QA_CAP_SEED)
print("dev-18 usable-discovery questions:", len(qs), " capped:", len(capped))
for m in g1_campaign.PATH_MEETINGS:
    print("  %-9s routed questions: %d" % (m, len(g1.questions_for_meeting(capped, m))))
per = {}
for q in capped:
    per[q.meeting_id] = per.get(q.meeting_id, 0) + 1
print("capped-set per-meeting counts (dev-18):", dict(sorted(per.items())))
print("total planned QA calls at floors scale (x2 arms):", 2 * len(capped))
PYEOF

echo
echo "=========================================================================="
echo "--- THE FLIGHT PLAN: registered N=200 cap, per-meeting routed (8aedcb9) ---"
echo "=========================================================================="
PYTHONPATH="$REPO/src" "$PY" "$REPO/scripts/run_g1.py" --mode path --data-dir "$DATA" \
  --vad-manifest-dir "$VAD_MANIFEST_DIR" \
  --meetingqa-root "$MEETINGQA_ROOT" --ami-root "$AMI_ROOT" \
  --max-calls "$PATH_MAX_CALLS" --max-gpu-hours "$PATH_MAX_GPU_HOURS" --max-wall-hours "$PATH_MAX_WALL_HOURS" \
  --list-chunks > "$LOGS/chunkplan-flight.json" 2>"$LOGS/chunkplan-flight.err"
echo "rc=$?"
cat "$LOGS/chunkplan-flight.err"
"$PY" - "$LOGS/chunkplan-flight.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print("n_work_items:", d["n_work_items"], " n_chunks:", d["n_chunks"])
tot = qa = 0
for c in d["chunks"]:
    print("  chunk %d: est_wall=%.1fs items=%d" % (c["index"], c["estimated_wall_seconds"], len(c["items"])))
    for it in c["items"]:
        print("    %-9s %-9s transcribe=%3d minutes=%d qa=%3d -> calls=%3d"
              % (it["meeting_id"], it["arm"], it["n_transcribe"], it["n_minutes"], it["n_qa"], it["n_calls"]))
        tot += it["n_calls"]; qa += it["n_qa"]
print("FLIGHT TOTAL CALLS:", tot, " QA CALLS:", qa, "(registered cap, per-meeting routed)")
print("flight fail-closed ceilings: <=250 calls / <=0.5 GPU-h / <=2 h wall")
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
echo "=== G1-PATH2 preflight end $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
