#!/usr/bin/env bash
# scripts/data/setup.sh — collaborator-facing dataset downloader for meeting-minutes-agent.
#
# Downloads the six meeting corpora this repository consumes into $SPEECHRL_DATA_DIR, verifies
# them, and skips anything already verified. Dataset identity (source URLs/HF repo ids, pinned
# revisions, license, expected layout, verification hashes) lives in
# scripts/data/datasets.lock.json, which is a meeting-scoped extract of the program's own
# umbrella lock -- see that file's "provenance" field.
#
# Usage:
#   export SPEECHRL_DATA_DIR=/path/to/your/data-root
#   bash scripts/data/setup.sh --help
#   bash scripts/data/setup.sh --list
#   bash scripts/data/setup.sh                          # download + verify all six, skip complete
#   bash scripts/data/setup.sh --dataset ami-meeting-corpus --dataset qmsum
#   bash scripts/data/setup.sh --verify-only            # skip downloading; just run verify.py
#
# Dependencies: bash, curl, git, python3 (>=3.12), and for the two HF-hosted datasets, the
# `huggingface-cli` (or `hf`) CLI. AMI and ICSI are fetched directly over HTTP from their
# official Edinburgh mirror; MeetingQA and QMSum are fetched with a plain pinned `git clone`;
# M3-SLU and MeetingBank are fetched with `huggingface-cli download` at pinned revisions
# (MeetingBank additionally pulls one Zenodo archive over HTTP for its text/alignment layer).
#
# This script never writes outside $SPEECHRL_DATA_DIR and never touches Git.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCK="$SCRIPT_DIR/datasets.lock.json"
PY="${SPEECHRL_PYTHON:-$(command -v python3 || command -v python || echo python3)}"

ALL_DATASETS=(ami-meeting-corpus icsi-meeting-corpus meetingqa qmsum m3-slu meetingbank)

usage() {
  cat <<'USAGE'
scripts/data/setup.sh — download + verify the meeting-minutes-agent data root

Usage:
  bash scripts/data/setup.sh [--dataset NAME ...] [--verify-only] [--list] [--help]

Options:
  --dataset NAME   Restrict to this dataset (repeatable). Default: all six.
                    Names: ami-meeting-corpus icsi-meeting-corpus meetingqa qmsum m3-slu meetingbank
  --verify-only    Do not download anything; just run scripts/data/verify.py on what is
                    already on disk under $SPEECHRL_DATA_DIR.
  --list           Print the six datasets (name, source kind, license) and exit. Downloads
                    nothing.
  -h, --help       Show this help and exit.

Environment:
  SPEECHRL_DATA_DIR   Required (except for --list/--help). Datasets land under
                      $SPEECHRL_DATA_DIR/datasets/<local_subdir>, matching
                      scripts/data/datasets.lock.json.
  SPEECHRL_HFD_THREADS  aria2c connections per file for HF downloads (default 8).

Idempotent: a dataset already verified by scripts/data/verify.py is skipped without a
re-download. Re-run this script safely after an interrupted download.

Per-dataset license notes are printed before each download; MeetingBank is
CC BY-NC-ND 4.0 (NonCommercial + NoDerivatives -- see scripts/data/README.md) and prints an
explicit warning. Read scripts/data/README.md for what each dataset is, why this research
uses it, and its exact expected on-disk layout.
USAGE
}

log()  { printf '[setup] %s\n' "$*"; }
warn() { printf '[setup] WARNING: %s\n' "$*" >&2; }
die()  { printf '[setup] ERROR: %s\n' "$*" >&2; exit 1; }

# ---- arg parsing --------------------------------------------------------------------------

WANT=()
VERIFY_ONLY=0
LIST_ONLY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dataset)
      [ $# -ge 2 ] || die "--dataset requires a value"
      WANT+=("$2"); shift 2 ;;
    --verify-only) VERIFY_ONLY=1; shift ;;
    --list) LIST_ONLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1 (see --help)" ;;
  esac
done

[ ${#WANT[@]} -eq 0 ] && WANT=("${ALL_DATASETS[@]}")

for name in "${WANT[@]}"; do
  match=0
  for known in "${ALL_DATASETS[@]}"; do [ "$known" = "$name" ] && match=1; done
  [ "$match" = 1 ] || die "unknown dataset '$name'; known: ${ALL_DATASETS[*]}"
done

# ---- --list (no data root needed) ---------------------------------------------------------

if [ "$LIST_ONLY" = 1 ]; then
  "$PY" - "$LOCK" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    lock = json.load(f)
print(f"{'NAME':<22} {'SOURCE':<20} LICENSE")
for e in lock["datasets"]:
    print(f"{e['name']:<22} {e['source']['kind']:<20} {e['license']}")
PY
  exit 0
fi

# ---- data root -----------------------------------------------------------------------------

: "${SPEECHRL_DATA_DIR:?SPEECHRL_DATA_DIR is not set. Export it to your data root first, e.g.:
  export SPEECHRL_DATA_DIR=/path/to/your/data-root
No corpus bytes for this repository are ever committed to Git; this variable is required.}"

DATA_ROOT="$SPEECHRL_DATA_DIR"
DATASETS_DIR="$DATA_ROOT/datasets"
mkdir -p "$DATASETS_DIR"

command -v "$PY" >/dev/null 2>&1 || die "python3 not found on PATH"
command -v curl  >/dev/null 2>&1 || die "curl not found on PATH"
command -v git   >/dev/null 2>&1 || die "git not found on PATH"

HFD_THREADS="${SPEECHRL_HFD_THREADS:-8}"
HF_CLI="$(command -v hf || command -v huggingface-cli || true)"

log "data root: $DATA_ROOT"
log "requested: ${WANT[*]}"

# ---- helpers to read one field of one lock entry (keeps setup.sh from hand-parsing JSON) ---

lock_field() { # name jq-ish-path -> prints the field, or empty
  "$PY" - "$LOCK" "$1" "$2" <<'PY'
import json, sys
name, path = sys.argv[2], sys.argv[3]
with open(sys.argv[1], encoding="utf-8") as f:
    lock = json.load(f)
entry = next(e for e in lock["datasets"] if e["name"] == name)
node = entry
for key in path.split("."):
    if node is None:
        break
    node = node.get(key) if isinstance(node, dict) else None
print(node if node is not None else "")
PY
}

print_license_notice() { # name
  local name="$1" license note
  license="$(lock_field "$name" license)"
  note="$(lock_field "$name" license_note)"
  log "$name: license = $license"
  case "$license" in
    *nc-nd*|*NC-ND*)
      warn "$name is $license -- NonCommercial AND NoDerivatives. No commercial use;"
      warn "no redistribution of derived material. Internal non-commercial research use only."
      ;;
    *nc*|*NC*)
      warn "$name is $license -- NonCommercial. Research use only, no commercial use."
      ;;
  esac
  [ -n "$note" ] && log "$name: $note" | fold -s -w 100
}

# ---- per-dataset fetchers ----------------------------------------------------------------
# Each fetcher is idempotent: it checks a cheap local marker before doing any network work.

fetch_ami() {
  local dest="$DATASETS_DIR/ami"
  if [ -d "$dest/amicorpus" ] && [ -d "$dest/annotations" ]; then
    log "ami-meeting-corpus: amicorpus/ and annotations/ already present; skipping download"
    return 0
  fi
  mkdir -p "$dest/amicorpus" "$dest/annotations"
  warn "ami-meeting-corpus has no unauthenticated bulk-download endpoint: the official AMI"
  warn "download page (https://groups.inf.ed.ac.uk/ami/download/) requires you to fill in a"
  warn "short form (name + email) before it emails you a personalised wget script."
  warn "  1. Open https://groups.inf.ed.ac.uk/ami/download/ and select 'Meeting Format: Mix-Headset'."
  warn "  2. Submit the form; run the emailed wget script with -P '$dest/amicorpus'."
  warn "  3. Then fetch the two annotation archives + license directly (no form needed):"
  curl -fL --create-dirs -o "$dest/annotations/ami_public_manual_1.6.2.zip" \
    "https://groups.inf.ed.ac.uk/ami/AMICorpusAnnotations/ami_public_manual_1.6.2.zip"
  curl -fL --create-dirs -o "$dest/annotations/ami_public_auto_1.5.1.zip" \
    "https://groups.inf.ed.ac.uk/ami/AMICorpusAnnotations/ami_public_auto_1.5.1.zip"
  curl -fL -o "$dest/CCBY4.0.txt" "https://groups.inf.ed.ac.uk/ami/download/CCBY4.0.txt"
  log "ami-meeting-corpus: annotation archives + license fetched. WAVs need the form step above."
}

fetch_icsi() {
  local dest="$DATASETS_DIR/icsi"
  if [ -d "$dest/audio" ] && [ "$(find "$dest/audio" -name '*.wav' 2>/dev/null | wc -l)" -ge 75 ] \
     && [ -d "$dest/annotations" ]; then
    log "icsi-meeting-corpus: audio/ (>=75 wav) and annotations/ already present; skipping download"
    return 0
  fi
  mkdir -p "$dest/audio" "$dest/annotations"
  log "icsi-meeting-corpus: fetching 75 interaction WAVs from the Edinburgh NXT mirror (~7.7 GiB)"
  local prefix="https://groups.inf.ed.ac.uk/ami/ICSIsignals/NXT"
  # The mirror lists one WAV per meeting under this prefix; meeting IDs come from the manifest
  # shipped with the umbrella lock's revision note (Bxxx/Bedxxx/Bmrxxx/Bnsxxx/Btrxxx/Buwxxx).
  # A plain directory listing is the simplest robust source of the exact filename set:
  local listing="$dest/.meeting-id-listing.html"
  curl -fsSL "$prefix/" -o "$listing" 2>/dev/null || warn "icsi-meeting-corpus: directory listing fetch failed; see README for the manual fallback"
  if [ -s "$listing" ]; then
    grep -oE '[A-Za-z0-9]+\.interaction\.wav' "$listing" | sort -u | while read -r fname; do
      [ -s "$dest/audio/$fname" ] && continue
      curl -fL -o "$dest/audio/$fname" "$prefix/$fname"
    done
  fi
  curl -fL -o "$dest/annotations/ICSI_core_NXT.zip" \
    "https://groups.inf.ed.ac.uk/ami/ICSICorpusAnnotations/ICSI_core_NXT.zip"
  curl -fL -o "$dest/annotations/ICSI_plus_NXT.zip" \
    "https://groups.inf.ed.ac.uk/ami/ICSICorpusAnnotations/ICSI_plus_NXT.zip"
  curl -fL -o "$dest/annotations/ICSI_original_transcripts.zip" \
    "https://groups.inf.ed.ac.uk/ami/ICSICorpusAnnotations/ICSI_original_transcripts.zip"
  curl -fL -o "$dest/CCBY4.0.txt" "https://groups.inf.ed.ac.uk/ami/download/CCBY4.0.txt"
}

fetch_git_dataset() { # name url rev dest
  local name="$1" url="$2" rev="$3" dest="$4"
  if [ -d "$dest/.git" ]; then
    log "$name: already cloned; fetching + checking out pinned revision"
    git -C "$dest" fetch --quiet origin "$rev" 2>/dev/null || true
  else
    log "$name: cloning $url"
    git clone --quiet "$url" "$dest"
  fi
  git -C "$dest" checkout --quiet "$rev" || die "$name: could not check out pinned revision $rev"
}

fetch_hf_dataset() { # name repo_id rev dest repo_type
  local name="$1" repo_id="$2" rev="$3" dest="$4" repo_type="${5:-dataset}"
  [ -n "$HF_CLI" ] || die "$name: no 'hf' or 'huggingface-cli' found on PATH. Install huggingface_hub: pip install -U huggingface_hub"
  mkdir -p "$dest"
  log "$name: downloading $repo_id @ $rev -> $dest"
  "$HF_CLI" download "$repo_id" --repo-type "$repo_type" --revision "$rev" --local-dir "$dest"
}

fetch_meetingqa() {
  local rev dest
  rev="$(lock_field meetingqa revision)"
  dest="$DATASETS_DIR/meetingqa"
  fetch_git_dataset meetingqa "https://github.com/adobe-research/meetingqa.git" "$rev" "$dest"
}

fetch_qmsum() {
  local rev dest
  rev="$(lock_field qmsum revision)"
  dest="$DATASETS_DIR/qmsum"
  fetch_git_dataset qmsum "https://github.com/Yale-LILY/QMSum.git" "$rev" "$dest"
}

fetch_m3slu() {
  local dest="$DATASETS_DIR/m3-slu"
  mkdir -p "$dest/audio/task1" "$dest/audio/task2"
  fetch_hf_dataset m3-slu-task1 "M3-SLU/M3-SLU-Task1" "c3836ecf34f2a1e7c4efb75ed84cb6e5f64cafe2" "$dest/audio/task1"
  fetch_hf_dataset m3-slu-task2 "M3-SLU/M3-SLU-Task2" "5ee25ccd444daadc40f331dc406b07f9617d66a7" "$dest/audio/task2"
  log "m3-slu: audio parquet shards land under audio/task1 and audio/task2; those parquet files"
  log "m3-slu: already carry the id/instruction/question/answer/script/n_speakers/data_source"
  log "m3-slu: text columns for their rows, so no separate text-only fetch is needed."
}

fetch_meetingbank() {
  local dest="$DATASETS_DIR/meetingbank"
  mkdir -p "$dest/text/hf" "$dest/text/zenodo" "$dest/audio-subset/archives"
  fetch_hf_dataset meetingbank-text "huuuyeah/meetingbank" "5b4fb6f67f490be93e249d70b732780932d19fe3" "$dest/text/hf"
  if [ ! -s "$dest/text/zenodo/MeetingBank.zip" ]; then
    log "meetingbank: fetching the Zenodo text/alignment archive (637 MB, all six cities)"
    curl -fL -o "$dest/text/zenodo/MeetingBank.zip" "https://zenodo.org/records/7989108/files/MeetingBank.zip"
    ( cd "$dest/text/zenodo" && "$PY" -c "import zipfile; zipfile.ZipFile('MeetingBank.zip').extractall('extracted')" )
  fi
  warn "meetingbank: the audio subset is a BOUNDED, city-stratified sample (81.78h / 50 meetings"
  warn "meetingbank: of the 3,579h full corpus) packaged as per-city multi-GB zip archives on"
  warn "meetingbank: huuuyeah/MeetingBank_Audio. Fetch only the 3 archives named in"
  warn "meetingbank: scripts/data/datasets.lock.json (Seattle-mp3-9.zip, Denver-13.zip,"
  warn "meetingbank: LongBeach-mp3-4.zip) rather than the whole repository -- see README.md."
  fetch_hf_dataset meetingbank-audio-index "huuuyeah/MeetingBank_Audio" \
    "27779a666ff5fd879f4c5567489ff47e82364abd" "$dest/audio-subset/_repo_index" >/dev/null 2>&1 || \
    warn "meetingbank: could not list huuuyeah/MeetingBank_Audio; fetch the 3 named archives manually"
}

# ---- dispatch --------------------------------------------------------------------------

if [ "$VERIFY_ONLY" = 0 ]; then
  for name in "${WANT[@]}"; do
    print_license_notice "$name"
    case "$name" in
      ami-meeting-corpus)  fetch_ami ;;
      icsi-meeting-corpus) fetch_icsi ;;
      meetingqa)           fetch_meetingqa ;;
      qmsum)                fetch_qmsum ;;
      m3-slu)               fetch_m3slu ;;
      meetingbank)          fetch_meetingbank ;;
    esac
  done
else
  log "--verify-only: skipping all downloads"
fi

# ---- verify ---------------------------------------------------------------------------

log "verifying: ${WANT[*]}"
VERIFY_ARGS=()
for name in "${WANT[@]}"; do VERIFY_ARGS+=(--dataset "$name"); done
"$PY" "$SCRIPT_DIR/verify.py" "${VERIFY_ARGS[@]}"
