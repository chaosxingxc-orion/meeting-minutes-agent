# Material new-surface source selection

## Selected construction

Use [EarningsCallVoice Core-100](https://huggingface.co/datasets/gmarti/EarningsCallVoice)
for authentic short audio, exact transcripts, same-speaker pairs, hashes, and nine
human source-quality gates. Join it by `call_id` to the official
[FinCall-Surprise repository](https://github.com/Tizzzzy/FinCall-Surprise), which
maps full call transcripts to audio and presentation-slide identifiers. Both
releases identify Apache-2.0 as the source license.

This is a short-chunk capability surface. It is intentionally not described as
a full-meeting loop benchmark or as representative of all earnings calls. The
public dataset-card preview exposed the text for `ECV-0001`, so that item is
excluded before deterministic splitting.

## Alternatives not selected

- [ELITR Minuting Corpus](https://ufal.mff.cuni.cz/elitr-minuting-corpus) has
  manually revised transcripts and organizer-written agendas or minutes, but
  its published corpus structure does not list audio as a distributed file.
- The [Zenodo Multimodal Earnings Call Dataset](https://zenodo.org/records/19032377)
  has audio, transcripts, and structured data, but the 43.9 GB release does not
  document the exact human transcript quality gate required by this pilot.
- Full FinCall-Surprise calls remain useful provenance and material sources, but
  its call transcript alone is not substituted for Core-100's exact clip-level
  reference.

## Resource decision

The frozen pilot uses 2019 and 2020 only. These years contain 70 Core-100 items;
after the known exposure exclusion, 69 remain. This supports 20 development,
40 one-shot confirmation, and 9 reserve items without acquiring the 2021 slide
archive. Source containers may include sealed text fields, but discovery code
projects identifiers, hashes, durations, provenance, and quality flags only.
