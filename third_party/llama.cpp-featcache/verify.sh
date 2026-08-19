#!/usr/bin/env bash
# Applies this directory's patch series to a fresh clone of upstream llama.cpp
# at the pinned base commit, and reports whether the result matches the
# recorded tip. Does not build anything (no cmake/CUDA needed) and never
# touches this repository's own working tree -- it clones into a scratch
# directory and cleans up after itself.
#
# Usage: bash verify.sh [scratch-dir]
#   scratch-dir defaults to a mktemp -d directory, removed on exit unless
#   KEEP=1 is set in the environment.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH_DIR="$HERE/patches"

BASE_HASH="fdbd6abee20e408de21e90ca77a24cd50a6ea073"
EXPECT_TIP="5d9dfcb58ea860295da8fc93c7b5bed9e2c71151"
UPSTREAM_URL="https://github.com/ggml-org/llama.cpp"

SCRATCH="${1:-$(mktemp -d)}"
mkdir -p "$SCRATCH"

cleanup() {
  if [ -z "${KEEP:-}" ]; then
    rm -rf "$SCRATCH/llama.cpp"
  else
    echo "KEEP=1 set; leaving checkout at $SCRATCH/llama.cpp"
  fi
}
trap cleanup EXIT

echo "== cloning $UPSTREAM_URL into $SCRATCH/llama.cpp =="
git clone --quiet "$UPSTREAM_URL" "$SCRATCH/llama.cpp"

echo "== checking out base commit $BASE_HASH =="
git -C "$SCRATCH/llama.cpp" checkout --quiet "$BASE_HASH"

echo "== applying patch series from $PATCH_DIR =="
git -C "$SCRATCH/llama.cpp" am --quiet "$PATCH_DIR"/*.patch

ACTUAL_TIP="$(git -C "$SCRATCH/llama.cpp" rev-parse HEAD)"

echo
echo "== diff --stat base..HEAD =="
git -C "$SCRATCH/llama.cpp" diff --stat "$BASE_HASH"..HEAD

echo
echo "expected tip: $EXPECT_TIP"
echo "actual tip:   $ACTUAL_TIP"

if [ "$ACTUAL_TIP" = "$EXPECT_TIP" ]; then
  echo "OK: tip hash matches."
  exit 0
else
  echo "MISMATCH: applied tip hash differs from the recorded tip." >&2
  echo "(A source-tree-identical-but-different-hash result can happen if" >&2
  echo "'git am' is run with different author/committer identity/date" >&2
  echo "handling than the original; compare 'git diff' output, not just" >&2
  echo "the hash, before concluding the patches themselves are wrong.)" >&2
  exit 1
fi
