#!/usr/bin/env bash
# G1-FLOORS preflight: repo state at 8aedcb9, hash pins, llama.cpp build
# commit, PRECOMP inputs for ALL dev-18 meetings, featcache-before, the full
# floors chunk plan at the REGISTERED N=200 QA cap (per-meeting routed,
# 8aedcb9), and the 72-item arm/plan cross-check. CPU-only: --list-chunks
# rebuilds slice plans from PRECOMP's on-disk cache with zero model contact.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1floors/env.sh
exec > "$LOGS/preflight.log" 2>&1

echo "=== G1-FLOORS preflight start $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
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
echo "--- PRECOMP inputs (all dev-18) ---"
echo "rttm files:        $(ls "$DERIVED_ROOT/rttm" 2>/dev/null | wc -l)"
echo "tool slice dirs:   $(ls "$DERIVED_ROOT/slices/tool" 2>/dev/null | wc -l)"
echo "oracle slice dirs: $(ls "$DERIVED_ROOT/slices/oracle" 2>/dev/null | wc -l)"
echo "vad slice dirs:    $(ls "$DERIVED_ROOT/slices/vad" 2>/dev/null | wc -l)"
echo "vad manifests:     $(ls "$VAD_MANIFEST_DIR" 2>/dev/null | wc -l)"

echo
echo "--- feature cache (ami-q4km) BEFORE the campaign ---"
echo "entries: $(find "$LLAMA_MTMD_FEAT_CACHE_DIR" -type f | wc -l)"
echo "bytes:   $(du -sb "$LLAMA_MTMD_FEAT_CACHE_DIR" | awk '{print $1}')"

echo
echo "--- run-dir BEFORE ---"
echo "run-dir: $RUN_DIR"
echo "receipts already present: $(ls "$RUN_DIR/receipts" 2>/dev/null | wc -l)"
echo "stop-file: $YIELD_FILE  present: $( [ -e "$YIELD_FILE" ] && echo YES || echo no )"

echo
echo "=========================================================================="
echo "--- THE CAMPAIGN PLAN: floors, registered cap, per-meeting routed ---"
echo "=========================================================================="
PYTHONPATH="$REPO/src" "$PY" "$REPO/scripts/run_g1.py" --mode floors --data-dir "$DATA" \
  --vad-manifest-dir "$VAD_MANIFEST_DIR" \
  --meetingqa-root "$MEETINGQA_ROOT" --ami-root "$AMI_ROOT" \
  --max-calls "$FLOORS_MAX_CALLS" --max-gpu-hours "$FLOORS_MAX_GPU_HOURS" --max-wall-hours "$FLOORS_MAX_WALL_HOURS" \
  --max-chunk-wall-seconds "$FLOORS_MAX_CHUNK_WALL_SECONDS" \
  --list-chunks > "$LOGS/chunkplan-flight.json" 2>"$LOGS/chunkplan-flight.err"
echo "rc=$?"
cat "$LOGS/chunkplan-flight.err"
"$PY" - "$LOGS/chunkplan-flight.json" <<'PYEOF'
import collections, json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print("n_work_items:", d["n_work_items"], " n_chunks:", d["n_chunks"])
tot = qa = tr = mi = 0
qa_by_meeting = collections.Counter()
for c in d["chunks"]:
    calls = sum(it["n_calls"] for it in c["items"])
    print("  chunk %d: est_wall=%.1fs (%.1f min) items=%d calls=%d"
          % (c["index"], c["estimated_wall_seconds"], c["estimated_wall_seconds"] / 60.0, len(c["items"]), calls))
    for it in c["items"]:
        tot += it["n_calls"]; qa += it["n_qa"]; tr += it["n_transcribe"]; mi += it["n_minutes"]
        qa_by_meeting[it["meeting_id"]] += it["n_qa"]
print("CAMPAIGN TOTAL CALLS:", tot, " transcribe:", tr, " minutes:", mi, " qa:", qa)
print("per-meeting planned QA calls (both arms):", dict(sorted(qa_by_meeting.items())))
print("registered ceilings: <=2,900 calls / <=6.0 GPU-h / <=8 h wall; est total wall %.1f min" % (tot * 3.7 / 60.0))
PYEOF

echo
echo "--- per-item detail (all chunks) ---"
"$PY" - "$LOGS/chunkplan-flight.json" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
for c in d["chunks"]:
    print("chunk %d:" % c["index"])
    for it in c["items"]:
        print("    %-9s %-9s transcribe=%3d minutes=%d qa=%3d -> calls=%3d"
              % (it["meeting_id"], it["arm"], it["n_transcribe"], it["n_minutes"], it["n_qa"], it["n_calls"]))
PYEOF

echo
echo "--- arm/plan provenance cross-check, all 18 x 4 (CPU-only, zero model contact) ---"
PYTHONPATH="$REPO/src" "$PY" - <<'PYEOF'
import os, sys
from pathlib import Path
repo = os.environ["REPO"]
sys.path.insert(0, repo + "/src"); sys.path.insert(0, repo + "/scripts")
from meeting_minutes_agent.corpora.nxt.corpus import NxtCorpus
from meeting_minutes_agent.corpora.roles import FROZEN_DEV_18
from meeting_minutes_agent.probes import g1
from run_g1 import resolve_slice_plan
data = Path(os.environ["DATA"]); derived = Path(os.environ["DERIVED_ROOT"])
nxt = NxtCorpus(data / "datasets/ami/annotations/manual_1.6.2")
vadman = Path(os.environ["VAD_MANIFEST_DIR"])
bad = 0
for m in FROZEN_DEV_18:
    for arm in g1.ARMS:
        plan, sdir = resolve_slice_plan(arm, m, data_dir=data, derived_root=derived,
                                        nxt_corpus=nxt, vad_manifest_dir=vadman)
        missing = [s.index for s in plan.slices
                   if not (data / sdir / m / g1.slice_filename(m, s.index)).is_file()]
        if missing:
            bad += 1
        print("%-9s %-9s mode=%-10s prov=%-12s slices=%3d missing_wavs=%s"
              % (m, arm, plan.mode.value, str(plan.turn_provenance and plan.turn_provenance.value),
                 len(plan.slices), missing if missing else "none"))
print("items with missing WAVs:", bad)
PYEOF

echo
echo "--- GPU health / orphans ---"
nvidia-smi --query-gpu=name,utilization.gpu,memory.used,clocks.sm,pstate,temperature.gpu,power.draw --format=csv
pgrep -ax llama-server || echo "llama-server: none"
pgrep -af run_g1.py || echo "run_g1: none"
echo "=== G1-FLOORS preflight end $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
