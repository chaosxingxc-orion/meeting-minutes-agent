# L1 — AMI abstractive summary reference multiplicity (2026-08-17)

Task L1 of the founding workplan. Measured locally on CPU from shipped bytes only; zero model
contact. Source: `$SPEECHRL_DATA_DIR/datasets/ami/annotations/manual_1.6.2/abstractive/`.

## Finding: AMI abstractive summaries are strictly single-reference

142 `*.abssumm.xml` files, one per meeting, covering 142 of the 171 meetings. Every one of the 142
carries **exactly one annotator's summary**. The distribution of distinct annotator identities per
meeting is `{1: 142}` — no meeting has two, none has zero.

The annotator identity is not inferred; it is carried in the NXT element ids. Each file's root
children are `<abstract>`, `<actions>`, `<decisions>`, `<problems>` (all four present in all 142
files, 568 sections total), and each id has the form `<meeting>.<annotator>.<section>.<n>`, e.g.
`ES2002a.rdhillon.abstract.1`, with sentence ids `ES2002a.rdhillon.s.1`. Parsing the annotator
field out of every id in every file yields exactly one distinct value per meeting.

Seven annotator identities appear across the corpus, and their per-meeting counts sum to exactly
142:

| annotator | meetings |
|---|---|
| `rdhillon` | 42 |
| `JacquelinePalmer` | 42 |
| `elana` | 27 |
| `vkaraisk` | 13 |
| `dharshi` | 13 |
| `s9553330` | 3 |
| `rdhillon_cc` | 2 |

That is a **partition of the corpus across annotators**, not overlapping coverage. Several people
annotated AMI, but no meeting was annotated twice.

Scale of the reference material, for calibration: 2,649 summary sentences and 40,958 summary words
in total, i.e. a mean of 18.65 sentences / 288.4 words per meeting across the four sections.

### The `participantSummaries` layer does not supply a second reference

The obvious candidate for a multi-reference set is `participantSummaries/` (323 files over 89
meetings; 73 meetings have 4 files, 6 have 3, 3 have 2, 7 have 1). It does not qualify. Its root
element is `participant_abstract` with ids of the form `ES2002aID.pabstract.1`,
`ES2002aPM.pabstract.1`, `ES2002aUI.pabstract.1`, `ES2002aME.pabstract.1` — the discriminator is
the participant **role** (ID / PM / UI / ME), not an annotator. These are four summaries written
from four different participants' perspectives: different targets, not independent renderings of
one target. Averaging or max-ing a metric over them measures perspective spread, not annotator
agreement, and must not be reported as an agreement band.

## What this means for evaluation claims

1. **No human-agreement ceiling can be computed from AMI itself.** An inter-annotator ceiling
   requires at least two independent references for the same meeting. AMI ships one. There is no
   arrangement of the shipped files that produces a second one.
2. **Every AMI summarization number this study reports is a point estimate against a single
   reference.** ROUGE, SAER-M, or any other reference-based summary metric computed on AMI has no
   inter-annotator band, and none may be implied. Language such as "approaches human agreement",
   "within the human range", or "close to the annotator ceiling" is unsupported on AMI and must not
   appear.
3. **Uncertainty that *can* be reported is sampling uncertainty, not agreement uncertainty.** A
   confidence interval over the 18 dev meetings (or a bootstrap over meetings) describes variation
   across meetings given one annotator. It is a legitimate interval and should be reported, but it
   answers a different question than an agreement band and must be labelled as such.
4. **Single-reference metrics systematically understate quality.** A generated summary can be
   correct and useful while overlapping poorly with the one reference that happens to exist. This
   biases absolute scores downward. It does not, in general, bias *arm-vs-arm differences* under a
   fixed reference, which is why the comparative design (naive / zero / carry arms) remains the
   sound way to use AMI — differences under a shared single reference are interpretable even when
   the absolute level is not.
5. **If a ceiling is required, it must come from outside AMI.** Options, in preference order:
   a corpus that ships multiple references per instance; a second reference authored under an
   explicit protocol and registered as a derived asset with its own provenance; or dropping the
   ceiling claim. Note that authoring references is annotation work, not measurement, and would
   need its own authorization — it is out of scope for this repository as currently chartered.

## Reproduction

Read-only, CPU, <5 s. Parses all 142 `abssumm` files plus a sample of `participantSummaries`, and
extracts annotator identity from NXT element ids. No model contact, no downloads.
