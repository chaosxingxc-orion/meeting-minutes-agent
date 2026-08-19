#!/usr/bin/env bash
# G1 VAD supplement landing: runtime identity, log + operator-script archive,
# per-meeting table, derived-artefact hashes/counts, MANIFEST.sha256.
# Derived bytes (VAD slice WAVs, feature-cache entries) stay on the data root;
# only hashes, counts and manifests land in Git. The VAD SlicePlan manifests
# themselves also stay on the data root (they are the runtime artefact G1's
# Z-nodiar arm loads); Git carries their sha256 list.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1sup/env.sh
exec > "$LOGS/land.log" 2>&1
set -x

mkdir -p "$OUT_DIR"

# --- 1. runtime identity ----------------------------------------------------
"$PY" - "$OUT_DIR/runtime-identity.json" <<'PYEOF'
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
    "pass": "G1 VAD supplement (dev-18, Z-nodiar slice source) -- pass A + pass B",
    "registration": "docs/readiness/2026-08-19-g1-floors-preregistration.md (REGISTERED, owner GO)",
    "ceilings_profile": "g1-supplement (500 encode calls / 1.0 GPU-h encode / 1.0 h CPU cutting)",
    "invocation": (
        "two run_precomp.py --wave 1 --turn-sources vad --ceilings-profile g1-supplement "
        "--meetings <nine> --workers 8 --resume --stop-file <G1SUP_YIELD> invocations"
    ),
    "diar_contact": "none -- --turn-sources vad never contacts the pinned Arm B diar tool",
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
    "feat_cache_dir": str(cache),
    "feat_cache_entries_after": len(entries),
    "feat_cache_bytes_after": sum(p.stat().st_size for p in entries),
    "derived_root": env["DERIVED_ROOT"],
    "vad_slice_root": env["VAD_SLICE_ROOT"],
    "vad_manifest_dir": env["VAD_MANIFEST_DIR"],
}
Path(sys.argv[1]).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({k: doc[k] for k in ("study_repo", "feat_cache_entries_after", "feat_cache_bytes_after")}, indent=2))
PYEOF

# --- 2. per-meeting table + final ledger ------------------------------------
"$PY" "$SP/table.py" "$OUT_DIR" > "$LOGS/table.txt"
cat "$LOGS/table.txt"
"$PY" "$SP/ledger.py" "$OUT_DIR" > "$LOGS/ledger-final.json"
cat "$LOGS/ledger-final.json"

# --- 3. derived-artefact hashes and counts (bytes stay on the data root) ----
( cd "$VAD_MANIFEST_DIR" && find . -type f -name '*.json' | sort | sed 's|^\./||' | xargs -r sha256sum ) > "$LOGS/vad-manifests.sha256"
wc -l "$LOGS/vad-manifests.sha256"
find "$VAD_SLICE_ROOT" -type f -name '*.wav' | wc -l > "$LOGS/vad-slice-wav-count.txt"
cat "$LOGS/vad-slice-wav-count.txt"
find "$DERIVED_ROOT/slices" -type f -name '*.wav' | wc -l > "$LOGS/all-slice-wav-count.txt"
cat "$LOGS/all-slice-wav-count.txt"

# --- 4. wave-1 prior-file integrity (this pass must not touch it) ----------
W1="$REPO/docs/checks/2026-08-19-precomp-wave1"
"$PY" - "$W1/MANIFEST.sha256" "$W1" > "$LOGS/wave1-integrity.txt" <<'PYEOF'
import hashlib, sys
from pathlib import Path
old, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
changed, missing, intact = [], [], 0
for line in old.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    digest, rel = line.split(None, 1)
    p = out_dir / rel.strip()
    if not p.is_file():
        missing.append(rel.strip()); continue
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    if h.hexdigest() == digest:
        intact += 1
    else:
        changed.append(rel.strip())
print(f"wave-1 files checked: {intact + len(changed) + len(missing)}")
print(f"byte-intact:         {intact}")
print(f"CHANGED:             {changed}")
print(f"MISSING:             {missing}")
PYEOF
cat "$LOGS/wave1-integrity.txt"

# --- 5. archive logs (flat: a logs/ subdir is gitignored repo-wide) --------
cp "$LOGS/preflight.log"            "$OUT_DIR/preflight.log"
cp "$LOGS/fly-passA-wrapper.log"    "$OUT_DIR/fly-passA-wrapper.log"
cp "$LOGS/fly-passB-wrapper.log"    "$OUT_DIR/fly-passB-wrapper.log"
cp "$LOGS/progress-passA.log"       "$OUT_DIR/progress-passA.log"
cp "$LOGS/progress-passB.log"       "$OUT_DIR/progress-passB.log"
cp "$LOGS/gpu-health-passA.log"     "$OUT_DIR/gpu-health-passA.log"
cp "$LOGS/gpu-health-passB.log"     "$OUT_DIR/gpu-health-passB.log"
cp "$LOGS/runner-passA.log"         "$OUT_DIR/runner-passA.log"
cp "$LOGS/runner-passB.log"         "$OUT_DIR/runner-passB.log"
cp "$LOGS/table.txt"                "$OUT_DIR/per-meeting-table.txt"
cp "$LOGS/ledger-final.json"        "$OUT_DIR/ledger-final.json"
cp "$LOGS/vad-manifests.sha256"     "$OUT_DIR/vad-manifests.sha256"
cp "$LOGS/vad-slice-wav-count.txt"  "$OUT_DIR/vad-slice-wav-count.txt"
cp "$LOGS/all-slice-wav-count.txt"  "$OUT_DIR/all-slice-wav-count.txt"
cp "$LOGS/wave1-integrity.txt"      "$OUT_DIR/wave1-prior-file-integrity.txt"

# --- 6. archive the operator scripts that drove the pass -------------------
cp "$SP/env.sh"        "$OUT_DIR/script-env.sh"
cp "$SP/preflight.sh"  "$OUT_DIR/script-preflight.sh"
cp "$SP/fly.sh"        "$OUT_DIR/script-fly.sh"
cp "$SP/monitor.sh"    "$OUT_DIR/script-monitor.sh"
cp "$SP/assess.sh"     "$OUT_DIR/script-assess.sh"
cp "$SP/land.sh"       "$OUT_DIR/script-land.sh"
cp "$SP/ledger.py"     "$OUT_DIR/ledger.py"
cp "$SP/aggregate.py"  "$OUT_DIR/aggregate.py"
cp "$SP/table.py"      "$OUT_DIR/table.py"

# --- 7. MANIFEST ------------------------------------------------------------
( cd "$OUT_DIR" && find . -type f ! -name 'MANIFEST.sha256' | sort | sed 's|^\./||' | xargs sha256sum ) > "$OUT_DIR/MANIFEST.sha256"
wc -l "$OUT_DIR/MANIFEST.sha256"
echo "LAND-DONE"
