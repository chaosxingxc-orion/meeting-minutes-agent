#!/usr/bin/env bash
# Landing addendum: archive the artefacts land.sh's first revision did not know about --
# the revision-2 invocation wrapper that actually drove invocations 2-5, the per-
# invocation computed meeting lists, and the remaining operator scripts -- then emit the
# descriptive README statistics and regenerate MANIFEST.sha256 over the final set.
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/precomp2/env.sh

cp "$SP/fly2.sh"        "$OUT_DIR/script-fly2.sh"
cp "$SP/wait.sh"        "$OUT_DIR/script-wait.sh"
cp "$SP/watch.sh"       "$OUT_DIR/script-watch.sh"
cp "$SP/readme_stats.py" "$OUT_DIR/readme_stats.py"
cp "$SP/land2.sh"       "$OUT_DIR/script-land2.sh"
for f in "$LOGS"/meetings-*.txt; do [ -e "$f" ] && cp "$f" "$OUT_DIR/$(basename "$f")"; done

echo "=== descriptive statistics ==="
PYTHONPATH="$REPO/src" "$PY" "$SP/readme_stats.py" "$OUT_DIR" "$LOGS" | tee "$LOGS/readme-stats.txt"
cp "$LOGS/readme-stats.txt" "$OUT_DIR/readme-stats.txt"
