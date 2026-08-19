#!/usr/bin/env bash
# PRECOMP wave-1 landing: runtime identity, log archive, MANIFEST.sha256.
# Derived bytes (RTTM, slice WAVs, feature-cache entries) stay on the data root;
# only hashes/counts/manifests land in Git (prereg SS5).
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp/env.sh
exec > "$LOGS/land.log" 2>&1
set -x

mkdir -p "$OUT_DIR/logs" "$OUT_DIR/scripts"

# --- runtime identity ------------------------------------------------------
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
    "pass": "PRECOMP wave-1 (dev-18)",
    "registration": "docs/readiness/2026-08-19-precomp-preregistration.md",
    "adjudication": "docs/readiness/2026-08-19-diar-adjudication-TOOL-LOCKED-B.md",
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

# --- archive logs + the operator scripts that drove the pass ----------------
cp "$LOGS/preflight.log"          "$OUT_DIR/logs/preflight.log"
cp "$LOGS/fly-wrapper.log"        "$OUT_DIR/logs/fly-wrapper.log"
cp "$LOGS/progress.log"           "$OUT_DIR/logs/progress.log"
cp "$LOGS/gpu-health.log"         "$OUT_DIR/logs/gpu-health.log"
cp "$LOGS/rttm-artefacts.sha256"  "$OUT_DIR/logs/rttm-artefacts.sha256"
cp "$LOGS/slice-wav-count.txt"    "$OUT_DIR/logs/slice-wav-count.txt"
mkdir -p "$OUT_DIR/logs/meetings"
cp "$LOGS"/meetings/*.log "$OUT_DIR/logs/meetings/" 2>/dev/null || true

cp "$SP/env.sh"            "$OUT_DIR/scripts/script-env.sh"
cp "$SP/serve.sh"          "$OUT_DIR/scripts/script-serve.sh"
cp "$SP/fly.sh"            "$OUT_DIR/scripts/script-fly.sh"
cp "$SP/one.sh"            "$OUT_DIR/scripts/script-one-meeting.sh"
cp "$SP/preflight.sh"      "$OUT_DIR/scripts/script-preflight.sh"
cp "$SP/teardown.sh"       "$OUT_DIR/scripts/script-teardown.sh"
cp "$SP/monitor.sh"        "$OUT_DIR/scripts/script-monitor.sh"
cp "$SP/budget_ledger.py"  "$OUT_DIR/scripts/budget_ledger.py"
cp "$SP/aggregate.py"      "$OUT_DIR/scripts/aggregate.py"
cp "$SP/table.py"          "$OUT_DIR/scripts/table.py"
cp "$SP/land.sh"           "$OUT_DIR/scripts/script-land.sh"
cp "$LOGS/teardown-shutdown.log" "$OUT_DIR/logs/teardown-shutdown.log"

# the single-invocation transport receipt is superseded by transport-receipts/<meeting>.json
rm -f "$OUT_DIR/transport-receipt.json"

# --- MANIFEST -------------------------------------------------------------
( cd "$OUT_DIR" && find . -type f ! -name 'MANIFEST.sha256' | sort | sed 's|^\./||' | xargs sha256sum ) > "$OUT_DIR/MANIFEST.sha256"
wc -l "$OUT_DIR/MANIFEST.sha256"
echo "LAND-DONE"
