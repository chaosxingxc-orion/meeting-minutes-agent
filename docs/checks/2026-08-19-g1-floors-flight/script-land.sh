#!/usr/bin/env bash
# G1-FLOORS landing: runtime identity, the text-free per-item/per-chunk
# receipts, the structural report, the chunk plan, the logs, and the operator
# scripts. NO MANIFEST here -- the README is written after this, then
# finalize-manifest.sh seals the directory.
#
# The per-contact response sink (RUN_DIR/responses/chunk*-responses.jsonl) is a
# RAW TRACE and stays on the data root -- Git carries only its sha256 and line
# count. That is also the directory scripts/g1_read.py's --responses-dir is
# meant to be pointed at, for the separately-gated read mission.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1floors/env.sh
exec > "$LOGS/land.log" 2>&1
set -x

mkdir -p "$ARCHIVE_DIR"

# --- 1. runtime identity ----------------------------------------------------
"$PY" - "$ARCHIVE_DIR/runtime-identity.json" <<'PYEOF'
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
run_dir = Path(env["RUN_DIR"])
sinks = sorted((run_dir / "responses").glob("chunk*-responses.jsonl"))
doc = {
    "captured_utc": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], capture_output=True, text=True).stdout.strip(),
    "flight": "G1 floors campaign (dev-18, four arms, transcribe + minutes + qa heads, registered N=200 QA cap routed per meeting)",
    "registration": "docs/readiness/2026-08-19-g1-floors-preregistration.md (REGISTERED, owner GO)",
    "scope": "flight only -- structural counts, no metric scoring, no result interpretation; the read is a separately gated mission",
    "campaign_ceilings": {
        "max_calls": int(env["FLOORS_MAX_CALLS"]),
        "max_gpu_hours": float(env["FLOORS_MAX_GPU_HOURS"]),
        "max_wall_hours": float(env["FLOORS_MAX_WALL_HOURS"]),
        "max_chunk_wall_seconds_estimated": float(env["FLOORS_MAX_CHUNK_WALL_SECONDS"]),
        "qa_cap": 200,
        "qa_seed": 20260818,
    },
    "stop_file": env["YIELD_FILE"],
    "study_repo": {"path": repo, "commit": git(repo, "rev-parse", "HEAD"),
                   "dirty_paths": len([l for l in git(repo, "status", "--porcelain").splitlines() if l])},
    "llama_cpp": {"checkout": llama_dir, "build_commit": git(llama_dir, "rev-parse", "HEAD"),
                  "tree_dirty": len([l for l in git(llama_dir, "status", "--porcelain").splitlines() if l]),
                  "binary_path": env["LLAMA_BIN"], "binary_bytes": os.path.getsize(env["LLAMA_BIN"]),
                  "binary_sha256": sha256(env["LLAMA_BIN"])},
    "server_argv": ["--host", "127.0.0.1", "--port", env["PORT"], "-m", env["MODEL_GGUF"],
                    "--mmproj", env["MMPROJ_GGUF"], "-c", "49152", "-np", "1", "-fa", "on",
                    "-ngl", "999", "-ctk", "q8_0", "-ctv", "q8_0"],
    "server_ownership": "child of each run_g1.py chunk invocation (g1_campaign.ManagedLlamaServer), one server per chunk",
    "model_files": [
        {"path": env["MODEL_GGUF"], "bytes": os.path.getsize(env["MODEL_GGUF"]), "sha256": sha256(env["MODEL_GGUF"])},
        {"path": env["MMPROJ_GGUF"], "bytes": os.path.getsize(env["MMPROJ_GGUF"]), "sha256": sha256(env["MMPROJ_GGUF"])},
    ],
    "feat_cache_dir": str(cache),
    "feat_cache_entries_after": len(entries),
    "feat_cache_bytes_after": sum(p.stat().st_size for p in entries),
    "run_dir": str(run_dir),
    "vad_manifest_dir": env["VAD_MANIFEST_DIR"],
    "response_sinks": [
        {"path": str(p), "bytes": p.stat().st_size,
         "lines": sum(1 for _ in p.open(encoding="utf-8")), "sha256": sha256(p)}
        for p in sinks
    ],
}
Path(sys.argv[1]).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({k: doc[k] for k in ("study_repo", "response_sinks", "feat_cache_entries_after")}, indent=2))
PYEOF

# --- 2. text-free receipts (per item, per chunk) ----------------------------
rm -rf "$ARCHIVE_DIR/receipts" "$ARCHIVE_DIR/chunks"
cp -r "$RUN_DIR/receipts" "$ARCHIVE_DIR/receipts"
cp -r "$RUN_DIR/chunks"   "$ARCHIVE_DIR/chunks"
ls "$ARCHIVE_DIR/receipts" | wc -l
ls "$ARCHIVE_DIR/chunks"   | wc -l
# defence in depth: no archived receipt may carry reply text
grep -l '"text"' "$ARCHIVE_DIR"/receipts/*.json "$ARCHIVE_DIR"/chunks/*.json && echo "REFUSE: reply text in an archived receipt" || echo "no reply text in archived receipts"

# --- 3. structural report ---------------------------------------------------
"$PY" "$SP/structural.py" "$RUN_DIR" "$LOGS/chunkplan-flight.json" > "$LOGS/structural-report.txt" 2>&1
cat "$LOGS/structural-report.txt"

# --- 4. response-sink hashes and counts (bytes stay on the data root) -------
( cd "$RUN_DIR/responses" && find . -type f -name '*.jsonl' | sort | sed 's|^\./||' | xargs -r sha256sum ) > "$LOGS/response-sinks.sha256"
for f in "$RUN_DIR"/responses/*.jsonl; do
  [ -e "$f" ] && echo "$(basename "$f") lines=$(wc -l < "$f") bytes=$(stat -c%s "$f")"
done > "$LOGS/response-sink-counts.txt"
cat "$LOGS/response-sinks.sha256" "$LOGS/response-sink-counts.txt"

# --- 5. archive logs + chunk plan -------------------------------------------
cp "$LOGS/preflight.log"                   "$ARCHIVE_DIR/preflight.log"
cp "$LOGS/chunkplan-flight.json"           "$ARCHIVE_DIR/chunkplan-flight.json"
cp "$LOGS/structural-report.txt"           "$ARCHIVE_DIR/structural-report.txt"
cp "$LOGS/response-sinks.sha256"           "$ARCHIVE_DIR/response-sinks.sha256"
cp "$LOGS/response-sink-counts.txt"        "$ARCHIVE_DIR/response-sink-counts.txt"
for f in "$LOGS"/fly-chunk*-wrapper.log "$LOGS"/progress-chunk*.log "$LOGS"/gpu-health-chunk*.log "$LOGS"/runner-chunk*.log; do
  [ -e "$f" ] && cp "$f" "$ARCHIVE_DIR/$(basename "$f")"
done

# --- 6. archive the operator scripts ----------------------------------------
cp "$SP/env.sh"         "$ARCHIVE_DIR/script-env.sh"
cp "$SP/serve-child.sh" "$ARCHIVE_DIR/script-serve-child.sh"
cp "$SP/preflight.sh"   "$ARCHIVE_DIR/script-preflight.sh"
cp "$SP/fly-chunk.sh"   "$ARCHIVE_DIR/script-fly-chunk.sh"
cp "$SP/assess.sh"      "$ARCHIVE_DIR/script-assess.sh"
cp "$SP/land.sh"        "$ARCHIVE_DIR/script-land.sh"
cp "$SP/finalize-manifest.sh" "$ARCHIVE_DIR/script-finalize-manifest.sh"
cp "$SP/structural.py"  "$ARCHIVE_DIR/structural.py"

echo "LAND-DONE (manifest pending README)"
