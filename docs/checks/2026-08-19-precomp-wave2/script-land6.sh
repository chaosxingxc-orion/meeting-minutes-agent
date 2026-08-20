#!/usr/bin/env bash
# Landing for wave-2 supplemental invocation 6 (ES2005d): re-run land.sh logic
# (runtime identity, re-aggregate over ALL 76 receipts, per-meeting table, final
# ledger, roster state, RTTM hashes, log/script archive) with NINV=6, then archive
# the new invocation-6 artefacts (both the transport-bug-discovery first attempt
# and the successful final attempt) and this script itself, then regenerate
# MANIFEST.sha256 last, over everything.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp2/env.sh
exec > "$LOGS/land6.log" 2>&1
set -x

NINV=6
STOP_REASON=""

# --- 1. runtime identity (re-captured post invocation 6) ----------------------
"$PY" - "$OUT_DIR/runtime-identity.json" "$NINV" <<'PYEOF'
import hashlib, json, os, subprocess, sys
from pathlib import Path

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()

def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True).stdout.strip()

env = os.environ
repo, llama_dir = env["REPO"], env["LLAMA_DIR"]
cache = Path(env["LLAMA_MTMD_FEAT_CACHE_DIR"])
entries = [p for p in cache.rglob("*") if p.is_file()]
doc = {
    "captured_utc": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True).stdout.strip(),
    "pass": "PRECOMP wave-2 (remaining usable-discovery meetings) -- night batch plus ES2005d supplement",
    "registration": "docs/readiness/2026-08-19-precomp-preregistration.md",
    "adjudication": "docs/readiness/2026-08-19-diar-adjudication-TOOL-LOCKED-B.md",
    "invocation": (
        "%s x [own llama-server child -> run_precomp.py --wave 2 --resume "
        "--stop-file <per-invocation> --workers 8 --slots 1 -> teardown]; "
        "invocation 6 is the supplemental ES2005d-only run, after the slicer plus transport "
        "float-epsilon fix (commit baaf41c), preceded by an aborted first attempt that "
        "surfaced the transport-layer gate (archived under invocation-6-attempt1-transport-bound-discovery)"
        % sys.argv[2]
    ),
    "study_repo": {"path": repo, "commit": git(repo, "rev-parse", "HEAD"),
                   "dirty_paths": len([l for l in git(repo, "status", "--porcelain").splitlines() if l])},
    "llama_cpp": {"checkout": llama_dir, "build_commit": git(llama_dir, "rev-parse", "HEAD"),
                  "tree_dirty": len([l for l in git(llama_dir, "status", "--porcelain").splitlines() if l]),
                  "binary_path": env["LLAMA_BIN"], "binary_bytes": os.path.getsize(env["LLAMA_BIN"]),
                  "binary_sha256": sha256(env["LLAMA_BIN"])},
    "server_argv": ["--host", "127.0.0.1", "--port", env["PORT"], "-m", env["MODEL_GGUF"],
                    "--mmproj", env["MMPROJ_GGUF"], "-c", "49152", "-np", "1", "-fa", "on",
                    "-ngl", "999", "-ctk", "q8_0", "-ctv", "q8_0"],
    "model_files": [
        {"path": env["MODEL_GGUF"], "bytes": os.path.getsize(env["MODEL_GGUF"]), "sha256": sha256(env["MODEL_GGUF"])},
        {"path": env["MMPROJ_GGUF"], "bytes": os.path.getsize(env["MMPROJ_GGUF"]), "sha256": sha256(env["MMPROJ_GGUF"])},
    ],
    "diarization_pin": {
        "arm": "B (TOOL-LOCKED(B))",
        "arm_config_path": env["ARM_CONFIG"], "arm_config_sha256": sha256(env["ARM_CONFIG"]),
        "binary_path": env["DIAR_BIN"], "binary_sha256": sha256(env["DIAR_BIN"]),
        "checkpoint_path": env["DIAR_GGUF"], "checkpoint_sha256": sha256(env["DIAR_GGUF"]),
    },
    "feat_cache_dir": str(cache),
    "feat_cache_entries_after": len(entries),
    "feat_cache_bytes_after": sum(p.stat().st_size for p in entries),
    "derived_root": env["DATA"] + "/derived/meeting-minutes/precomp",
}
Path(sys.argv[1]).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({k: doc[k] for k in ("study_repo", "feat_cache_entries_after", "feat_cache_bytes_after")}, indent=2))
PYEOF

# --- 2. re-aggregate the wave artefact over ALL 76 receipts --------------------
"$PY" "$SP/aggregate2.py" 2 "$OUT_DIR" "$STOP_REASON" "$NINV"

# --- 3. per-meeting table plus final ledger --------------------------------------
"$PY" "$SP/table.py" "$OUT_DIR" > "$LOGS/table-final.txt"
cat "$LOGS/table-final.txt"
cp "$LOGS/table-final.txt" "$OUT_DIR/per-meeting-table.txt"

"$PY" "$SP/budget_ledger.py" 2 "$OUT_DIR" > "$LOGS/ledger-final.json"
cat "$LOGS/ledger-final.json"
cp "$LOGS/ledger-final.json" "$OUT_DIR/budget-ledger-final.json"

# --- 4. roster completion state ------------------------------------------------
PYTHONPATH="$REPO/src" "$PY" - "$OUT_DIR" > "$LOGS/roster-state.json" <<'PYEOF'
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.environ["REPO"] + "/src")
from meeting_minutes_agent.precomp.roster import default_wave_meetings
from meeting_minutes_agent.precomp.receipts import already_done
out = Path(sys.argv[1])
roster = sorted(default_wave_meetings(2))
done = [m for m in roster if already_done(out, m)]
todo = [m for m in roster if not already_done(out, m)]
print(json.dumps({"roster_n": len(roster), "complete_n": len(done), "remaining_n": len(todo),
                  "remaining": todo, "state": "COMPLETE" if not todo else "PARTIAL"},
                 indent=2, sort_keys=True))
PYEOF
cat "$LOGS/roster-state.json"
cp "$LOGS/roster-state.json" "$OUT_DIR/roster-state.json"

# --- 5. derived-artefact hashes (E: run root; bytes never committed) ----------
( cd "$DATA/derived/meeting-minutes/precomp" && find . -type f -name "*.rttm" | sort | sed "s|^\./||" | xargs -r sha256sum ) > "$LOGS/rttm-artefacts.sha256"
wc -l "$LOGS/rttm-artefacts.sha256"
cp "$LOGS/rttm-artefacts.sha256" "$OUT_DIR/rttm-artefacts.sha256"
( cd "$DATA/derived/meeting-minutes/precomp" && find . -type f -name "*.wav" | wc -l ) > "$OUT_DIR/slice-wav-count.txt"
cat "$OUT_DIR/slice-wav-count.txt"

# --- 6. archive per-invocation logs (flat: a logs subdir is gitignored) ------
cp "$LOGS/preflight.log" "$OUT_DIR/preflight.log"
for f in "$LOGS"/fly-*.log;        do [ -e "$f" ] && cp "$f" "$OUT_DIR/$(basename "$f")"; done
for f in "$LOGS"/progress-*.log;   do [ -e "$f" ] && cp "$f" "$OUT_DIR/$(basename "$f")"; done
for f in "$LOGS"/runner-*.log;     do [ -e "$f" ] && cp "$f" "$OUT_DIR/$(basename "$f")"; done
for f in "$LOGS"/gpu-health-*.log; do [ -e "$f" ] && cp "$f" "$OUT_DIR/$(basename "$f")"; done

# --- 6b. the aborted first attempt at invocation 6 (transport-layer discovery) --
mkdir -p "$OUT_DIR/invocation-6-attempt1-transport-bound-discovery"
cp "$LOGS"/attempt1-transport-bound-discovery/*.log "$OUT_DIR/invocation-6-attempt1-transport-bound-discovery/" 2>/dev/null
cp "$LOGS"/attempt1-transport-bound-discovery/*.json "$OUT_DIR/invocation-6-attempt1-transport-bound-discovery/" 2>/dev/null
ls "$OUT_DIR/invocation-6-attempt1-transport-bound-discovery/"

echo "server.log lines: invocation-6 only, prior server.log rotated per invocation, not archived by land.sh either" >> "$OUT_DIR/server-errors.log"
grep -Ei "error|failed|abort|assert|out of memory|terminate" "$LOGS/server.log" >> "$OUT_DIR/server-errors.log" 2>/dev/null || true

# --- 7. archive the operator scripts that drove invocation 6 -------------------
cp "$SP/fly6.sh"          "$OUT_DIR/script-fly6.sh"
cp "$SP/land6.sh"         "$OUT_DIR/script-land6.sh"

# --- 8. per-invocation transport ledger ----------------------------------------
if [ -f "$OUT_DIR/transport-receipts/inv-6.json" ]; then
  echo "inv-6 transport receipt present"
else
  echo "WARNING inv-6 transport receipt missing"
fi

# --- 9. MANIFEST -----------------------------------------------------------------
( cd "$OUT_DIR" && find . -type f ! -name "MANIFEST.sha256" | sort | sed "s|^\./||" | xargs sha256sum ) > "$OUT_DIR/MANIFEST.sha256"
wc -l "$OUT_DIR/MANIFEST.sha256"
echo "LAND6-DONE"
