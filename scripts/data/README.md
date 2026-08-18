# scripts/data — dataset download + construction

This repository never commits corpus bytes: no audio, no annotations, no derived features.
Everything in this directory reads or writes only under your local data root
(`$SPEECHRL_DATA_DIR`), never Git. The six datasets described below are the ones
`meeting-minutes-agent` actually consumes — AMI and ICSI for meeting speech, MeetingQA and
QMSum for text-layer QA/summarization annotations over that speech, M3-SLU for
speaker-attributed QA, and a bounded MeetingBank audio subset for entity-dense long-form
council meetings.

Dataset identity (source URLs / Hugging Face repo ids, pinned revisions, license, size,
expected on-disk layout, verification hashes) lives in
[`datasets.lock.json`](datasets.lock.json), a **meeting-scoped extract** of the program's
umbrella `docs/datasets.lock.json` (see that file's `provenance` field for the umbrella
commit it was generated from). The umbrella lock remains the program-level authority; this
file exists so an external collaborator can reproduce this repository's data root without
checking out the umbrella repository at all.

## Quick start

```bash
export SPEECHRL_DATA_DIR=/path/to/your/data-root   # required; nothing writes anywhere else
bash scripts/data/setup.sh --help
bash scripts/data/setup.sh --list                  # see all six datasets, download nothing
bash scripts/data/setup.sh                          # download + verify all six (idempotent)
bash scripts/data/setup.sh --dataset ami-meeting-corpus --dataset qmsum
bash scripts/data/setup.sh --verify-only             # re-check what's already on disk
python scripts/data/verify.py                        # same verification, standalone
```

`setup.sh` skips any dataset `verify.py` already reports PASS, so re-running it after an
interrupted download only fetches what is missing. It prints each dataset's license before
downloading it; read those notices, especially MeetingBank's (below).

## Data root

`$SPEECHRL_DATA_DIR` is the one directory these scripts ever touch. Each dataset lands at
`$SPEECHRL_DATA_DIR/datasets/<local_subdir>` exactly as named in `datasets.lock.json`. No
corpus bytes, model weights, or derived audio features are ever committed to this Git
repository — `.gitignore`/review discipline in this repo assumes `$SPEECHRL_DATA_DIR` sits
outside the checkout entirely (e.g. a separate drive or a sibling directory never `git add`ed).

## Dependencies

`bash`, `curl`, `git`, and Python 3.12+ (stdlib only — `verify.py` has no third-party
dependencies). The two Hugging Face–hosted datasets (M3-SLU, MeetingBank) additionally need
the `huggingface-cli` (or `hf`) CLI: `pip install -U huggingface_hub`.

## The six datasets

### AMI Meeting Corpus (`ami-meeting-corpus`)

**What it is.** ~171 Mix-Headset multi-party business-meeting recordings from the AMI
Meeting Corpus, with the official manual (v1.6.2) and automatic (v1.5.1) annotation layers
(named entities, topics, dialogue acts, segments, words, abstractive/extractive summaries).

**Why this research uses it.** The primary meeting-speech carrier: MeetingQA and the
Product domain of QMSum are defined over AMI transcripts and join to this audio by meeting
id.

**Source.** Official form-gated download at
<https://groups.inf.ed.ac.uk/ami/download/> (select "Mix-Headset"); annotation archives and
license text are open HTTP, no form required.

**License.** CC BY 4.0.

**Size.** ~10.8 GiB, 174 files (171 WAV + 2 annotation archives + 1 license file).

**Expected layout** under `datasets/ami/`:

```
amicorpus/<MEETING_ID>/audio/<MEETING_ID>.Mix-Headset.wav   (171 files)
annotations/ami_public_manual_1.6.2.zip
annotations/ami_public_auto_1.5.1.zip
annotations/manual_1.6.2/    (extracted)
annotations/auto_1.5.1/      (extracted)
CCBY4.0.txt
```

**Setup:** `bash scripts/data/setup.sh --dataset ami-meeting-corpus` (fetches the annotation
archives and license automatically; the WAVs require one manual form submission — the
script prints the exact steps).

### ICSI Meeting Corpus (`icsi-meeting-corpus`)

**What it is.** 75 mixed "interaction" WAVs (71.7 hours) from the ICSI Meeting Corpus, with
core/plus NXT annotation archives (words, segments, MRDA dialogue acts, abstractive/
extractive summaries, topic segmentation) and the original `.mrt` transcripts. No
named-entity layer exists upstream for ICSI.

**Why this research uses it.** The second meeting-speech carrier; supplies the audio behind
QMSum's Academic (ICSI) domain.

**Source.** Open HTTP from the Edinburgh NXT signal mirror, no registration —
<https://groups.inf.ed.ac.uk/ami/icsi/download/>. This is *not* the LDC-licensed ICSI
release.

**License.** CC BY 4.0 (declared verbatim on both the corpus home page and its license
page).

**Size.** ~7.8 GiB, 80 files (75 WAV + 3 annotation archives + 2 license files).

**Expected layout** under `datasets/icsi/`:

```
audio/<MeetingID>.interaction.wav   (75 files)
annotations/ICSI_core_NXT.zip
annotations/ICSI_plus_NXT.zip
annotations/ICSI_original_transcripts.zip
CCBY4.0.txt
LICENSE-ICSI-verbatim.txt
```

**Setup:** `bash scripts/data/setup.sh --dataset icsi-meeting-corpus`

### MeetingQA (`meetingqa`)

**What it is.** Extractive question-answering annotations over AMI meeting transcripts
(ACL 2023, Prasad et al.): 7,735 QA instances across 166 AMI meetings, plus the processed
transcripts they were annotated on. No audio of its own.

**Why this research uses it.** Text-layer QA carrier; every meeting id resolves inside the
`ami-meeting-corpus` record, so speech-side use joins against those bytes.

**Source.** `git clone https://github.com/adobe-research/meetingqa.git`, pinned to commit
`5e3d1fbf4fefb60790d2445ce6721085b274024b`.

**License.** CC BY-NC-SA 4.0 — NonCommercial and ShareAlike bind every downstream use.

**Size.** ~297 MiB, 255 files.

**Expected layout** under `datasets/meetingqa/`:

```
AllData/
DataCollection/
PostAnnotationProcessing/
ProcessedTranscripts/
qaCode/
requirements/
LICENSE
README.md
```

**Setup:** `bash scripts/data/setup.sh --dataset meetingqa`

### QMSum (`qmsum`)

**What it is.** Query-based multi-domain meeting summarization (NAACL 2021, Zhong et al.):
1,810 queries over 232 meetings across three domains — Product (AMI, 137 meetings),
Academic (ICSI, 59 meetings), Committee (parliamentary transcripts, 36 meetings, no local
audio counterpart in this repository).

**Why this research uses it.** Text-layer ORG/SUPPLY carrier; the Product and Academic
domains join to `ami-meeting-corpus` and `icsi-meeting-corpus` respectively by meeting id.

**Source.** `git clone https://github.com/Yale-LILY/QMSum.git`, pinned to commit
`83d7768c1f2b4dfeb091385d3dc7e239b8e5bb7e`.

**License.** MIT.

**Size.** ~118 MiB, 718 files.

**Expected layout** under `datasets/qmsum/`:

```
data/              (jsonl transcripts + query/summary annotations, split by domain)
extracted_span/
figures/
model_output/
data_process.ipynb
LICENSE
README.md
```

**Setup:** `bash scripts/data/setup.sh --dataset qmsum`

### M3-SLU (`m3-slu`)

**What it is.** Speaker-attributed QA and speaker-attribution-matching over multi-party
speech (LREC 2026 submission, arXiv:2510.19358): two Hugging Face repos (Task1, Task2)
together holding 10,908 rows of id/instruction/question/answer/script/n_speakers/data_source
plus 155 audio-bearing parquet shards (CHIME-6, MELD, MultiDialog and AMI source audio).

**Why this research uses it.** QA-face probe carrier over multi-party speech. M3-SLU ids
are corpus-tagged sequence ids, not source meeting ids, so no per-meeting join back to
`ami-meeting-corpus` is possible from the release metadata alone.

**Source.** Hugging Face, `M3-SLU/M3-SLU-Task1` @ `c3836ecf34f2a1e7c4efb75ed84cb6e5f64cafe2`
and `M3-SLU/M3-SLU-Task2` @ `5ee25ccd444daadc40f331dc406b07f9617d66a7`.

**License.** CC BY 4.0.

**Size.** ~39.8 GiB, 162 files (7 text `.jsonl` + 155 parquet shards).

**Expected layout** under `datasets/m3-slu/`:

```
m3-slu-task1-preview.text.jsonl
m3-slu-task1-sample.text.jsonl
m3-slu-task2-preview.text.jsonl
m3-slu-task2-sample.text.jsonl
audio/task1/   (44 parquet shards)
audio/task2/   (111 parquet shards)
```

**Setup:** `bash scripts/data/setup.sh --dataset m3-slu`

### MeetingBank (`meetingbank`)

**What it is.** Entity-dense, long-form US city-council meetings (ACL 2023, Hu et al.,
arXiv:2305.17529): per-bill Legistar agenda-item summaries and word-timestamped ASR
transcripts across all six cities in the text layer, plus a deliberately **bounded** audio
subset — 81.78 hours / 50 meetings across 3 of 6 cities (2.3% of the full 3,579-hour corpus).
The shipped reference transcripts are machine ASR output, so transcript-level WER against
them measures agreement with another recognizer, not accuracy; valid surfaces are
summarization, spoken QA, and agenda-item segmentation.

**Why this research uses it.** The only meeting-minutes carrier in this catalogue that ships
its own speech bytes at all; text layer is complete for the whole corpus.

**Source.** Hugging Face `huuuyeah/meetingbank` (text) and `huuuyeah/MeetingBank_Audio`
(audio archives), plus one Zenodo archive (DOI `10.5281/zenodo.7989108`) for the
text/alignment layer.

**License.** **CC BY-NC-ND 4.0** — the most restrictive of three conflicting upstream
declarations (see `datasets.lock.json`'s `license_note` for the full three-way conflict).
**NonCommercial: no commercial use. NoDerivatives: do not redistribute adapted or derived
material.** Internal non-commercial research use is unaffected, but any external release of
this subset or of material derived from it must resolve the licensing conflict with the
authors first. `setup.sh` prints this warning explicitly before downloading.

**Size.** Text layer ~5.8 GiB (1,420 files); bounded audio subset ~4.4 GiB (3 city archives,
81.78 hours, 50 meetings).

**Expected layout** under `datasets/meetingbank/`:

```
text/zenodo/MeetingBank.zip        (+ extracted/)
text/hf/                            (huuuyeah/meetingbank)
audio-subset/archives/              (Seattle-mp3-9.zip, Denver-13.zip, LongBeach-mp3-4.zip)
```

**Setup:** `bash scripts/data/setup.sh --dataset meetingbank`

## Verifying what's on disk

`scripts/data/verify.py` is stdlib-only Python (no install needed) and never touches the
network. It checks, per dataset: presence under `$SPEECHRL_DATA_DIR/datasets/<local_subdir>`,
file-count and total-size closure against the meeting lock, and every hash the lock records
(license files, annotation/audio archives, git commit identity). It prints a PASS / MISSING /
MISMATCH table and exits 0 only if every requested dataset passes.

```bash
python scripts/data/verify.py --help
python scripts/data/verify.py                       # verify all six
python scripts/data/verify.py --dataset qmsum
python scripts/data/verify.py --quiet                # table only, no per-check detail
```

Where the umbrella lock has no per-file hash for every payload file (e.g. AMI's 171
individual WAVs, or M3-SLU's 155 parquet shards, whose per-shard LFS SHA-256 values live only
in the umbrella's private acquisition receipt), `verify.py` and `datasets.lock.json`'s
`hash_coverage_note` say so explicitly and fall back to file-count and total-size closure for
that subtree — this is a lock-coverage gap, not a download error.
