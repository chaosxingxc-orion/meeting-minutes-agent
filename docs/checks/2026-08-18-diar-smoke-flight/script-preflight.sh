#!/bin/bash
# DIAR-SMOKE preflight: repo state, pytest, tooling staging, hash verification,
# launcher summary-only. No diarization contact happens here.
set -u
export PYTHONDONTWRITEBYTECODE=1

REPO=/mnt/d/chao_workspace/exploring-l4-intelligence/papers/meeting-minutes-agent
DATA=/mnt/e/chao_workspace/exploring-l4-intelligence/speechrl-data
RUNROOT=$DATA/derived/meeting-minutes/diar-smoke
TOOLING=$RUNROOT/tooling
SP=/mnt/c/Users/35686/AppData/Local/Temp/claude/D--chao-workspace-exploring-l4-intelligence-studies-speech-aware-evidence-acquisition/6d9f1834-68e9-41a7-bbcc-724898cf15a9/scratchpad/diar
LOGS=$SP/logs
PY=/home/chao/.venvs/speechrl/bin/python
EXPECTED_HEAD=53bc5e191c56f2125953a7411c9ce9baa64023dd

mkdir -p "$LOGS" "$TOOLING"
FAIL=0

echo "=== [1] git state ==="
HEAD=$(git -C "$REPO" rev-parse HEAD)
DIRTY=$(git -C "$REPO" status --porcelain)
echo "HEAD: $HEAD"
if [ "$HEAD" != "$EXPECTED_HEAD" ]; then echo "PREFLIGHT FAIL: HEAD is not $EXPECTED_HEAD"; FAIL=1; fi
if [ -n "$DIRTY" ]; then echo "PREFLIGHT FAIL: tree dirty:"; echo "$DIRTY"; FAIL=1; else echo "tree: clean"; fi

echo "=== [2] stage tooling to E: ==="
cp "$SP/sortformer_diarize_arm_a.py" "$TOOLING/"
cp "$SP/arm-config.json" "$TOOLING/"
ls -l "$TOOLING"

echo "=== [3] hash verification ==="
MODELDIR=$DATA/models/diar-sortformer-4spk-v2
BIN=/home/chao/nemo-speech.cpp/build/cuda-diar/bin/nemo-speech
{
  echo "# expected-hash table (pin sources: umbrella docs/datasets.lock.json diar-sortformer-4spk-v2;"
  echo "# umbrella docs/checks/meeting-minutes-agent/2026-08-18-diar-acquisition/README.md;"
  echo "# meeting repo configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json audio_sha256)"
} > "$LOGS/hash-verify.log"

check_hash () {  # check_hash <expected> <path> <label>
  local expected=$1 path=$2 label=$3
  local actual
  actual=$(sha256sum "$path" | awk '{print $1}')
  if [ "$actual" = "$expected" ]; then
    echo "OK   $label  $actual" | tee -a "$LOGS/hash-verify.log"
  else
    echo "FAIL $label  expected=$expected actual=$actual" | tee -a "$LOGS/hash-verify.log"
    FAIL=1
  fi
}

check_hash b371afce2c4958186469df33d939936b9746c89f38b10a69cfd2c61254e83329 "$MODELDIR/diar_streaming_sortformer_4spk-v2.nemo" "arm-A-nemo-checkpoint"
check_hash 0679cfeb1ce356d0dea9470b31274f4bfc7eb927497d82005483770666da998a "$MODELDIR/diar_streaming_sortformer_4spk-v2.q8_0.gguf" "arm-B-gguf-checkpoint"
check_hash 1a3e3f4fe7db4c48e5d6e44a76d5adf2bbfef80024c023b0eab2766eb61aca78 "$BIN" "arm-B-binary-nemo-speech"
check_hash 63459ac9811903fe49f79982e9155b457425fa62c5f1f47d4047f512cd348c83 "$DATA/datasets/ami/amicorpus/ES2011b/audio/ES2011b.Mix-Headset.wav" "wav-ES2011b"
check_hash 0d992a210480c6e9652b317ed7f66261e80a1aa86f7e5c3dffd10e81b8e30de2 "$DATA/datasets/ami/amicorpus/IS1008b/audio/IS1008b.Mix-Headset.wav" "wav-IS1008b"
check_hash 22bc4c5ef7c033427426e84b168f71d162a42ed287ae4781aa2f6c06b67a6177 "$DATA/datasets/ami/amicorpus/IS1008d/audio/IS1008d.Mix-Headset.wav" "wav-IS1008d"
check_hash 3c8e8e9f4b24cc9a8c2fa5932cbecebcf9d14b6b415ac48d6229547fc014c9b2 "$DATA/datasets/ami/amicorpus/TS3004b/audio/TS3004b.Mix-Headset.wav" "wav-TS3004b"

echo "--- first-pin hashes (no prior per-file pin exists in any Git manifest for these two) ---" | tee -a "$LOGS/hash-verify.log"
for m in ES2011a TS3004d; do
  h=$(sha256sum "$DATA/datasets/ami/amicorpus/$m/audio/$m.Mix-Headset.wav" | awk '{print $1}')
  echo "PIN  wav-$m  $h" | tee -a "$LOGS/hash-verify.log"
done

echo "--- WAV header sanity (all six) ---" | tee -a "$LOGS/hash-verify.log"
"$PY" - "$DATA" <<'PYEOF' 2>&1 | tee -a "$LOGS/hash-verify.log"
import sys, wave
data = sys.argv[1]
bad = 0
for m in ("ES2011a", "ES2011b", "IS1008b", "IS1008d", "TS3004b", "TS3004d"):
    p = f"{data}/datasets/ami/amicorpus/{m}/audio/{m}.Mix-Headset.wav"
    with wave.open(p, "rb") as w:
        rate, ch, width, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
    ok = rate == 16000 and ch == 1 and width == 2
    print(f"{'OK  ' if ok else 'FAIL'} {m}: {rate} Hz, {ch} ch, {8*width}-bit, {n/rate:.1f} s")
    bad += 0 if ok else 1
sys.exit(1 if bad else 0)
PYEOF
[ ${PIPESTATUS[0]} -ne 0 ] && FAIL=1

echo "=== [4] full pytest ==="
cd "$REPO"
PYTHONPATH=$REPO/src "$PY" -m pytest -q > "$LOGS/preflight-pytest.log" 2>&1
PYTEST_RC=$?
tail -4 "$LOGS/preflight-pytest.log"
echo "pytest rc=$PYTEST_RC"
[ $PYTEST_RC -ne 0 ] && FAIL=1

echo "=== [5] launcher --summary-only ==="
PYTHONPATH=$REPO/src "$PY" "$REPO/scripts/launch_diar_smoke.py" --data-dir "$DATA" --summary-only 2>&1 | tee "$LOGS/preflight-summary-only.log"
[ ${PIPESTATUS[0]} -ne 0 ] && FAIL=1

echo "=== [6] tree still clean after preflight ==="
DIRTY2=$(git -C "$REPO" status --porcelain)
if [ -n "$DIRTY2" ]; then echo "PREFLIGHT FAIL: tree dirtied by preflight:"; echo "$DIRTY2"; FAIL=1; else echo "tree: clean"; fi

if [ $FAIL -ne 0 ]; then echo "PREFLIGHT: FAIL"; exit 1; fi
echo "PREFLIGHT: PASS"
