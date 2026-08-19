#!/usr/bin/env bash
# Seal the G1-FLOORS archive: MANIFEST.sha256 over every file (README included).
set -u
source /mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/g1floors/env.sh
( cd "$ARCHIVE_DIR" && find . -type f ! -name 'MANIFEST.sha256' | sort | sed 's|^\./||' | xargs sha256sum ) > "$ARCHIVE_DIR/MANIFEST.sha256"
wc -l "$ARCHIVE_DIR/MANIFEST.sha256"
echo "MANIFEST-DONE"
