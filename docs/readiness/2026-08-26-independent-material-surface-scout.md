# Independent material surface scout

## Decision

Select **LHCP-ASR** as the primary candidate for the next independent material-conditioned
ASR surface. Do not admit it yet. The candidate is `SOURCE_ENDPOINT_FOUND_JOIN_PENDING`:
the accessible Hugging Face mirror contains audio and transcripts but omits slides; official
CERN Indico pages expose per-contribution slide and recording attachments, but the exact 72-talk
join has not yet been proven.

Before this record was written, case-insensitive searches over this repository and the umbrella
repository returned no occurrence of `LHCP-ASR`, `mllp/LHCP`, `Chinese-LiPS`, or
`BAAI/Chinese-LiPS`. No corpus audio, transcript row, slide, or reference file was downloaded or
read during scouting. Only papers, dataset cards, file trees, licenses, and aggregate metadata were
inspected.

## Candidate matrix

| Candidate | Audio/reference | Legal material | Independence | Decision |
|---|---|---|---|---|
| [LHCP-ASR](https://www.isca-archive.org/interspeech_2025/santamariajorda25_interspeech.html) | 72 real talks / 30 h with manually revised verbatim references | Per-talk PDF/PPTX slides; presentation plus Q&A | No prior local/umbrella occurrence | **Primary; source closure required** |
| [Chinese-LiPS](https://github.com/flageval-baai/Chinese-LiPS) | 100.84 h, 207 speakers, manual transcripts | Synchronized slide video and extracted slide text | Validation/test remain unread | Secondary construction-isolated fallback |
| [Earnings25](https://huggingface.co/datasets/florencejiang/earnings25) | 514 full calls / 498 h with named speaker turns | No bundled call material | New, except one viewer-exposed segmented call | Hold: transcript provenance and material join are not closed |
| [PriMock57](https://github.com/babylonhealth/primock57) | 57 two-party consultations with manual turn transcripts | Clinician notes are written during or after the call | New | Reject as same-call input: temporal leakage |
| [SlideSpeech](https://slidespeech.github.io/) | 473 h selected by ASR/subtitle agreement | Synchronized slide OCR | New | Reject for strict confirmation: references are not human verbatim |
| SlideASR-Bench | Synthetic SlideASR-S is public; real SlideASR-R is absent | Slide images/entity lists | Already acquired and consumed upstream | Reject as independent evidence |
| SPGISpeech 2.0 | Professionally transcribed, speaker-tagged | Would require an external join | New | Reject: license forbids linking to another dataset |

## Why LHCP-ASR is the best fit

The official paper reports 14/15 development/test talks from 2020 and 11/32 from 2022:
25 development talks (10.4 h) and 47 confirmation talks (19.6 h). Talks are approximately
25-minute technical presentations followed by 5-minute Q&A, so the surface contains a dominant
speaker plus real multi-speaker tails. Each original talk ships with video, timed SRT, and the
speaker's PDF or PPTX slides. The evaluation references were manually created or post-edited and
cross-reviewed under published guidelines.

The pinned audio/text mirror is `mllp/LHCP-ASR@1583283ffe91ee22f7e547fc1248c3646f68fe43`.
Its 17 long-form evaluation shards total 6,705,900,572 bytes (6.25 GiB), so the evaluation-only
acquisition is practical on `D:`. The mirror declares CC BY-NC-ND 4.0. This is a conference-talk
surface, not a general business-meeting benchmark; it can confirm material use and dominant-speaker
plus-Q&A behavior, but cannot by itself establish full meeting-loop generalization.

## Required admission sequence

1. Enumerate CERN Indico events
   [856696](https://indico.cern.ch/event/856696/timetable/?view=standard) (2020) and
   [1109611](https://indico.cern.ch/event/1109611/timetable/?view=nicecompact) (2022). Their JSON
   exports provide contribution IDs, attachment download URLs, filenames, sizes, and checksums.
2. Build a metadata-only join using audio path, conference year, talk identifier, and slide URL.
   Project no transcript field and save a join receipt with hashes and orphan counts.
3. Freeze the published development splits for construction and both test splits for one-shot
   confirmation. Keep all reference text sealed until the prebuilt reader runs.
4. Census slide readability and candidate supply before any model contact. A missing/scan-only
   slide deck fails closed; do not substitute OCR or another document after split release.
5. Only after source closure, register a new Pass0/material-attribution experiment with complete
   per-chunk trace retention. The fixed diarizer, slicer, and preprocessing remain unchanged.

No model authorization is implied by this scout.

## Post-scout update

`E-MATERIAL-LHCP-ADMISSION` subsequently closed the exact 72/72 identifier join and
72/72 material coverage on the same day. The `JOIN_PENDING` decision above remains
the historical scout verdict, not the current admission status.
