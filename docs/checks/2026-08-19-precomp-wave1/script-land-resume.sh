#!/usr/bin/env bash
# PRECOMP wave-1 RESUME landing: runtime identity, log/script archive delta,
# prior-file integrity proof, regenerated MANIFEST.sha256.
#
# This EXTENDS the existing receipt directory: every file the first pass landed
# stays byte-intact except the single registered wave artefact
# (wave-summary.json, which by construction must describe the whole wave) and
# MANIFEST.sha256/README.md. Resume outputs get their own -resume names.
# Derived bytes (RTTM, slice WAVs, feature-cache entries) stay on the data root;
# only hashes/counts/manifests land in Git (prereg SS5).
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp/env.sh
exec > "$LOGS/land-resume.log" 2>&1
set -x

SPROOT=/mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad

# --- 0. snapshot the OLD manifest so prior-file integrity is provable --------
cp "$OUT_DIR/MANIFEST.sha256" "$LOGS/MANIFEST.old.sha256"

# --- 1. runtime identity for the resume pass --------------------------------
"$PY" - "$OUT_DIR/runtime-identity-resume.json" <<'PYEOF'
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
    "pass": "PRECOMP wave-1 (dev-18) -- RESUME pass, meetings 10-18",
    "registration": "docs/readiness/2026-08-19-precomp-preregistration.md",
    "adjudication": "docs/readiness/2026-08-19-diar-adjudication-TOOL-LOCKED-B.md",
    "invocation": "single run_precomp.py --wave 1 --resume --stop-file <PRECOMP_YIELD> --workers 8",
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

# --- 2. archive the resume + retry logs (flat: a logs/ subdir is gitignored) -
cp "$LOGS/preflight-resume.log"        "$OUT_DIR/preflight-resume.log"
cp "$LOGS/fly-resume-wrapper.log"      "$OUT_DIR/fly-resume-wrapper.log"
cp "$LOGS/progress-resume.log"         "$OUT_DIR/progress-resume.log"
cp "$LOGS/gpu-health-resume.log"       "$OUT_DIR/gpu-health-resume.log"
cp "$LOGS/resume-runner.log"           "$OUT_DIR/resume-runner.log"
cp "$LOGS/fly-retry-wrapper.log"       "$OUT_DIR/fly-retry-wrapper.log"
cp "$LOGS/progress-retry.log"          "$OUT_DIR/progress-retry.log"
cp "$LOGS/gpu-health-retry.log"        "$OUT_DIR/gpu-health-retry.log"
cp "$LOGS/retry-runner.log"            "$OUT_DIR/retry-runner.log"
cp "$LOGS/teardown-resume.log"         "$OUT_DIR/teardown-resume-retry.log"
cp "$LOGS/table-final.txt"             "$OUT_DIR/per-meeting-table-final.txt"
cp "$LOGS/rttm-artefacts.sha256"       "$OUT_DIR/rttm-artefacts-final.sha256"
cp "$LOGS/slice-wav-count.txt"         "$OUT_DIR/slice-wav-count-final.txt"
# the superseded first attempt at TS3004d: real diar + cutting spend, lost to a
# reaped server, and overwritten on disk by the retry's receipt. Kept as
# evidence, NOT as a wave outcome.
cp "$LOGS/TS3004d-aborted-attempt-receipt.json" "$OUT_DIR/TS3004d-aborted-attempt-receipt.json"

# --- 3. archive the operator scripts that drove the resume ------------------
cp "$SPROOT/precomp-setup.sh"    "$OUT_DIR/script-setup-resume.sh"
cp "$SP/preflight-resume.sh"     "$OUT_DIR/script-preflight-resume.sh"
cp "$SP/wait-server.sh"          "$OUT_DIR/script-wait-server-resume.sh"
cp "$SP/fly-resume.sh"           "$OUT_DIR/script-fly-resume.sh"
cp "$SP/monitor-resume.sh"       "$OUT_DIR/script-monitor-resume.sh"
cp "$SP/wait-fly.sh"             "$OUT_DIR/script-wait-fly-resume.sh"
cp "$SP/assess.sh"               "$OUT_DIR/script-assess-resume.sh"
cp "$SP/save-aborted.sh"         "$OUT_DIR/script-save-aborted-resume.sh"
cp "$SP/fly-retry.sh"            "$OUT_DIR/script-fly-retry.sh"
cp "$SP/wait-retry.sh"           "$OUT_DIR/script-wait-retry.sh"
cp "$SP/teardown-resume.sh"      "$OUT_DIR/script-teardown-resume.sh"
cp "$SP/land-resume.sh"          "$OUT_DIR/script-land-resume.sh"
cp "$SP/aggregate_resume.py"     "$OUT_DIR/aggregate_resume.py"

# --- 4. prior-file integrity: every path in the OLD manifest, rehashed ------
"$PY" - "$LOGS/MANIFEST.old.sha256" "$OUT_DIR" > "$LOGS/prior-file-integrity.txt" <<'PYEOF'
import hashlib, sys
from pathlib import Path
old, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
changed, missing, intact = [], [], 0
for line in old.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    digest, rel = line.split(None, 1)
    rel = rel.strip()
    p = out_dir / rel
    if not p.is_file():
        missing.append(rel)
        continue
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    if h.hexdigest() == digest:
        intact += 1
    else:
        changed.append(rel)
print(f"prior files checked: {intact + len(changed) + len(missing)}")
print(f"byte-intact:        {intact}")
print(f"CHANGED:            {changed}")
print(f"MISSING:            {missing}")
PYEOF
cat "$LOGS/prior-file-integrity.txt"
cp "$LOGS/prior-file-integrity.txt" "$OUT_DIR/prior-file-integrity-resume.txt"

# --- 5. MANIFEST ------------------------------------------------------------
( cd "$OUT_DIR" && find . -type f ! -name 'MANIFEST.sha256' | sort | sed 's|^\./||' | xargs sha256sum ) > "$OUT_DIR/MANIFEST.sha256"
wc -l "$OUT_DIR/MANIFEST.sha256"
echo "LAND-DONE"
