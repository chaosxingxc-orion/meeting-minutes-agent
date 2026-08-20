#!/usr/bin/env bash
# PRECOMP wave-2 landing: runtime identity, re-aggregated wave summary over ALL
# receipts, per-meeting table, derived-artefact hashes, per-invocation log/script
# archive, MANIFEST.sha256.
#
#   usage: land.sh <n_invocations> "<stopped_reason or empty>"
#
# Derived bytes (RTTM, slice WAVs, feature-cache entries) stay on the data root; only
# hashes/counts/manifests land in Git (prereg SS5). Encode-warm generation text is never
# read: the runner discards it and the receipts carry counts only.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp2/env.sh
exec > "$LOGS/land.log" 2>&1
set -x

NINV="${1:?n invocations}"
STOP_REASON="${2:-}"

# --- 1. runtime identity ------------------------------------------------------
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
    "pass": "PRECOMP wave-2 (remaining usable-discovery meetings) -- night batch",
    "registration": "docs/readiness/2026-08-19-precomp-preregistration.md",
    "adjudication": "docs/readiness/2026-08-19-diar-adjudication-TOOL-LOCKED-B.md",
    "invocation": (
        "%s x [own llama-server child -> run_precomp.py --wave 2 --resume "
        "--stop-file <per-invocation> --workers 8 --slots 1 -> teardown]" % sys.argv[2]
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

# --- 2. re-aggregate the wave artefact over ALL receipts ----------------------
"$PY" "$SP/aggregate2.py" 2 "$OUT_DIR" "$STOP_REASON" "$NINV"

# --- 3. per-meeting table + final ledger --------------------------------------
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
( cd "$DATA/derived/meeting-minutes/precomp" && find . -type f -name '*.rttm' | sort | sed 's|^\./||' | xargs -r sha256sum ) > "$LOGS/rttm-artefacts.sha256"
wc -l "$LOGS/rttm-artefacts.sha256"
cp "$LOGS/rttm-artefacts.sha256" "$OUT_DIR/rttm-artefacts.sha256"
( cd "$DATA/derived/meeting-minutes/precomp" && find . -type f -name '*.wav' | wc -l ) > "$OUT_DIR/slice-wav-count.txt"
cat "$OUT_DIR/slice-wav-count.txt"

# --- 6. archive per-invocation logs (flat: a logs/ subdir is gitignored) ------
cp "$LOGS/preflight.log" "$OUT_DIR/preflight.log"
for f in "$LOGS"/fly-*.log;        do [ -e "$f" ] && cp "$f" "$OUT_DIR/$(basename "$f")"; done
for f in "$LOGS"/progress-*.log;   do [ -e "$f" ] && cp "$f" "$OUT_DIR/$(basename "$f")"; done
for f in "$LOGS"/runner-*.log;     do [ -e "$f" ] && cp "$f" "$OUT_DIR/$(basename "$f")"; done
for f in "$LOGS"/gpu-health-*.log; do [ -e "$f" ] && cp "$f" "$OUT_DIR/$(basename "$f")"; done
# llama-server's own operational log: error lines only (no reply content is logged at this
# verbosity, and the encode-warm outputs are never read).
grep -Ei 'error|failed|abort|assert|out of memory|terminate' "$LOGS/server.log" > "$OUT_DIR/server-errors.log" 2>/dev/null
echo "server.log lines: $(wc -l < "$LOGS/server.log")" >> "$OUT_DIR/server-errors.log"

# --- 7. archive the operator scripts that drove the wave ---------------------
cp "$SP/env.sh"          "$OUT_DIR/script-env.sh"
cp "$SP/serve.sh"        "$OUT_DIR/script-serve.sh"
cp "$SP/setup.sh"        "$OUT_DIR/script-setup.sh"
cp "$SP/preflight.sh"    "$OUT_DIR/script-preflight.sh"
cp "$SP/fly.sh"          "$OUT_DIR/script-fly.sh"
cp "$SP/land.sh"         "$OUT_DIR/script-land.sh"
cp "$SP/aggregate2.py"   "$OUT_DIR/aggregate2.py"
cp "$SP/budget_ledger.py" "$OUT_DIR/budget_ledger.py"
cp "$SP/table.py"        "$OUT_DIR/table.py"

# --- 8. MANIFEST ---------------------------------------------------------------
( cd "$OUT_DIR" && find . -type f ! -name 'MANIFEST.sha256' | sort | sed 's|^\./||' | xargs sha256sum ) > "$OUT_DIR/MANIFEST.sha256"
wc -l "$OUT_DIR/MANIFEST.sha256"
echo "LAND-DONE"
