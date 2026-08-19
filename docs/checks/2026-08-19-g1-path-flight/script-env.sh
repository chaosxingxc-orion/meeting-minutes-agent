#!/usr/bin/env bash
# Shared environment for the G1-PATH pathfinder flight (2026-08-19).
# Same pinned llama.cpp build, same q4km GGUF pair, same WARM per-dataset
# feature cache ami-q4km as PRECOMP wave-1 and the G1 VAD supplement.
export PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export REPO=/mnt/d/chao_workspace/exploring-l4-intelligence/papers/meeting-minutes-agent
export PYTHONPATH="$REPO/src"
export SPEECHRL_DATA_DIR=/mnt/e/chao_workspace/exploring-l4-intelligence/speechrl-data
export DATA="$SPEECHRL_DATA_DIR"

# NEVER q4km / slurp-q4km / audio2tool-q4km.
export FEATCACHE_DATASET=ami
export FEATCACHE_ENCODER=q4km
export LLAMA_MTMD_FEAT_CACHE_DIR=/home/chao/feat-cache/ami-q4km
export SAEA_FEAT_CACHE_DIR=/home/chao/feat-cache/ami-q4km

export SP=/mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1path
export LOGS="$SP/logs"
export YIELD_FILE="$SP/G1PATH_YIELD"

# The runner's --out-dir lives on the DATA root, never in Git: it holds the
# per-contact response sink (responses/chunk*-responses.jsonl), which is a raw
# trace and is prohibited from the repository. That is also exactly where
# scripts/g1_read.py expects to be pointed
# ("--responses-dir $SPEECHRL_DATA_DIR/derived/meeting-minutes/g1/runs/<run-id>").
# Only the text-free per-item/per-chunk receipts, logs, hashes and counts are
# copied into ARCHIVE_DIR at landing.
export RUN_DIR="$DATA/derived/meeting-minutes/g1/runs/2026-08-19-g1-path"
export ARCHIVE_DIR="$REPO/docs/checks/2026-08-19-g1-path-flight"
export DERIVED_ROOT="$DATA/derived/meeting-minutes/precomp"
export VAD_MANIFEST_DIR="$DERIVED_ROOT/slices/vad-manifest"
export MEETINGQA_ROOT="$DATA/datasets/meetingqa"
export AMI_ROOT="$DATA/datasets/ami"

export LLAMA_DIR=/home/chao/llama.cpp-featcache
export LLAMA_BIN="$LLAMA_DIR/build/bin/llama-server"
export MODEL_DIR=/home/chao/models/qwen3-omni-30b-a3b-instruct-gguf-q4km
export MODEL_GGUF="$MODEL_DIR/Qwen3-Omni-30B-A3B-Instruct-Q4_K_M.gguf"
export MMPROJ_GGUF="$MODEL_DIR/mmproj-Qwen3-Omni-30B-A3B-Instruct-bf16.gguf"
export MODEL_SHA256=0751c279498785c0b07130ae7748038d1e2cfd04617928e4557063807f98066d
export MMPROJ_SHA256=f0dfe825fb692d426362b1ac79678fc08daa4758f7151526cad110515f122883
export LLAMA_BIN_SHA256=097c96ec5a3f576f378d4d5e103928bf070647fdcc1f015eacb839503e121c68
export LLAMA_BUILD_COMMIT=5d9dfcb58ea860295da8fc93c7b5bed9e2c71151

export PORT=8080
export BASE_URL="http://127.0.0.1:${PORT}"
export PY=/home/chao/.venvs/speechrl/bin/python

# G1-PATH's own registered envelope (floors prereg SS5: "~250 requests,
# <=0.5 GPU-h"), enforced fail-closed as this flight's G1Budget rather than
# the whole campaign's 2,900/6.0/8.0 -- a pathfinder must not be able to
# spend the floors campaign's ceiling.
export PATH_MAX_CALLS=250
export PATH_MAX_GPU_HOURS=0.5
export PATH_MAX_WALL_HOURS=2.0

# QA-head structural probe size. The registered N=200 cap is a CAMPAIGN-wide
# question set; scripts/run_g1.py dispatches the WHOLE capped set to EVERY
# (meeting, arm), which for PATH would be 2 x 2 x 200 = 800 QA calls against a
# registered ~250-request pathfinder. PATH therefore exercises the QA head's
# dispatch chain at machinery-testing scale only (the runner prints its own
# "only for machinery testing, never for a registered flight" warning, which
# is exactly this invocation's status: structural, never scored).
export PATH_QA_CAP=3

mkdir -p "$LOGS" "$RUN_DIR"
