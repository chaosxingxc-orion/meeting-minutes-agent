# SAER-M — minutes-level speaker-attribution metric (definition)

Status: **PRE-REGISTERED-DRAFT, pending coordinator review** (task E5 of the 2026-08-17 founding
workplan; L4 owns the eventual preregistration write-up that cites this document — see the
workplan §3 L4 row). This document is the metric's authoritative definition; the reference
implementation is `src/meeting_minutes_agent/metrics/saer_m.py` and must never diverge from what
is written here without both being updated together.

## Why this metric exists

The protocol needs a minutes-level speaker-attribution number, not a transcript-level one. The
WER-family metrics in `metrics/wer.py` (tcpWER, tcORC-WER, cpWER, ORC-WER) score attribution at
the *transcript* level — did the system's stream-per-speaker output line up against the reference
stream-per-speaker output. They say nothing about whether the *minutes* — the abstractive
sentences an agent actually produces as its deliverable — correctly credit the right speaker for
each claim. No published metric in this family measures that; we define our own, hence
"self-derived" in the deep-check registered changes' language, and hence PRE-REGISTERED-DRAFT
rather than a settled citation.

SAER-M stands for **Speaker-Attribution Error Rate — Minutes**. It is computed per meeting (and
aggregated across meetings by simple micro-averaging over all scored sentences, unless a later
document specifies a macro-average instead — that choice is left open here and must be pinned
before any headline number is reported).

## What it measures

For every **minutes sentence that has at least one gold evidence link** (an E2-resolved
`EvidenceLink`, i.e. an AMI/ICSI `summlink` entry tying an abstractive sentence to the extractive
dialogue act(s) that support it), SAER-M asks one question: **did the system attribute that
sentence to the right speaker?**

- **Gold speaker(s) for a sentence** = the set of speakers on the dialogue act(s) any evidence
  link names for that sentence (see "Ambiguous gold" below for the multi-speaker case).
- **Predicted speaker for a sentence** = whatever speaker identity the system's minutes-generation
  head attaches to that sentence, or nothing at all if the head produced the sentence without an
  attribution.

**Per-statement attribution accuracy** = (# sentences scored `correct`) / (# sentences with at
least one gold evidence link). This is the headline number. Sentences with no gold evidence link
at all are never in the accuracy denominator (there is nothing to check the prediction against);
see "hallucinated-speaker" below for what happens when the system attributes one anyway.

## Error taxonomy

Every minutes sentence that appears on the gold side, the predicted side, or both is classified
into exactly one of five outcomes:

| outcome | gold evidence? | system prediction? | condition | counts toward accuracy denominator? |
|---|---|---|---|---|
| `correct` | yes | yes | predicted speaker ∈ gold speaker set | yes (numerator + denominator) |
| `wrong_speaker` | yes | yes | predicted speaker ∉ gold speaker set | yes (denominator only) |
| `unattributed` | yes | no | system produced the sentence with no speaker attribution at all | yes (denominator only) |
| `hallucinated_speaker` | no | yes | system attributed a speaker to a sentence with no gold evidence link | **no** — reported separately |
| `not_scored` | no | no | neither side has anything for this sentence id | no — bookkeeping only |

`wrong_speaker`, `unattributed`, and `hallucinated_speaker` are the three named error kinds the
task brief requires; `not_scored` is a bookkeeping category (it should be empty or near-empty in
practice — a sentence id with neither gold evidence nor a prediction should not normally appear in
either input at all, but the reference implementation still classifies it explicitly rather than
raising, so a caller can audit "did I actually cover every sentence I meant to score").

## Ambiguous gold (multi-speaker evidence)

`MeetingResolver.resolve_evidence_links` (E2) already collapses a multi-agent dialogue-act span
into one `EvidenceLink.speaker` string of the form `"speakerA|speakerB"` when the supporting
dialogue acts come from more than one agent, and a single minutes sentence can have more than one
`summlink` entry pointing into it. SAER-M folds every speaker named by every evidence link for a
sentence into one **gold speaker set**, and scores a prediction `correct` if it names *any* member
of that set. This is a deliberate leniency: when the reference material itself does not pin the
claim to one speaker, the metric should not manufacture a single correct answer to be wrong
against. A future revision MAY tighten this (e.g. a separate "ambiguous-gold" bucket scored
separately) if the multi-speaker case turns out to be common enough to matter — flagged here for
coordinator review, not resolved.

## Worked micro-examples

Six minutes sentences from a toy two-speaker meeting (`spk_a`, `spk_b`), gold evidence from E2,
system predictions from a hypothetical minutes head:

| sentence id | gold evidence link speaker(s) | system prediction | outcome | why |
|---|---|---|---|---|
| `s.1` | `spk_a` | `spk_a` | `correct` | prediction matches the single gold speaker |
| `s.2` | `spk_b` | `spk_a` | `wrong_speaker` | gold says `spk_b`, system said `spk_a` |
| `s.3` | `spk_a` | *(none)* | `unattributed` | gold evidence exists; system produced the sentence with no speaker at all |
| `s.4` | *(none)* | `spk_b` | `hallucinated_speaker` | no `summlink` entry ties `s.4` to any dialogue act, yet the system named a speaker |
| `s.5` | `spk_a\|spk_b` (two summlink entries, one per speaker) | `spk_b` | `correct` | `spk_b` is a member of the gold set `{spk_a, spk_b}` — the ambiguous-gold leniency above |
| `s.6` | *(none)* | *(none)* | `not_scored` | neither side has anything for this id (bookkeeping only, e.g. a sentence id one caller referenced but the other did not) |

Accuracy over this toy meeting: 2 `correct` / (2 `correct` + 1 `wrong_speaker` + 1 `unattributed`)
= 2/4 = **0.5**. `s.4` (`hallucinated_speaker`) and `s.6` (`not_scored`) are excluded from that
denominator and reported as their own counts, per the table above.

## Implementation

`src/meeting_minutes_agent/metrics/saer_m.py`:

- `SpeakerAttributionPrediction(sentence_id, predicted_speaker)` — one system guess.
- `compute_saer_m(evidence_links, predictions) -> SaerMReport` — builds the gold speaker table from
  a sequence of E2 `EvidenceLink`s, joins it against the predictions, classifies every sentence id
  seen on either side, and returns the accuracy plus every error-taxonomy count plus the
  per-sentence breakdown (`SaerMReport.per_sentence`, one `SentenceAttributionResult` per sentence
  id, for audit).

The implementation takes `EvidenceLink` objects directly (E2's resolved evidence-link structure,
not raw XML) — SAER-M is defined at the resolved-evidence layer, not the corpus-parsing layer, so
it applies unchanged to any corpus E2 grows to cover (AMI today; ICSI's dialogue-act layer is
structurally compatible).

## Open questions for coordinator review (do not resolve unilaterally)

1. **Cross-meeting aggregation.** Micro- vs macro-average across meetings once more than one
   meeting is scored — left open above.
2. **Ambiguous-gold leniency.** Whether "correct if the prediction names any member of the gold
   set" is the right call long-term, or whether ambiguous-gold sentences should be a separate,
   non-accuracy-denominator bucket (mirroring how `hallucinated_speaker` is already held out).
3. **Section weighting.** Whether `abstract`/`actions`/`decisions`/`problems` sentences should be
   weighted equally in the headline number, or reported per-section (the reference implementation
   does not currently split by section; `EvidenceLink.section` is available on every gold record if
   a per-section breakdown is wanted later).
