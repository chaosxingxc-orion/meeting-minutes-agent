# E-MEETING-MATERIAL-SUPPLY-AUDIT preregistration

## Question

Can meeting-contemporaneous official issuer material provide a precise, distributed,
and provenance-bearing supply of professional-term correction candidates for the four
frozen Earnings-22 meetings? This is a zero-model feasibility audit. It does not revise
the failed output-only retrieval verdicts and cannot itself admit an Omni flight.

## Frozen research boundary

The frozen meetings are `4430051`, `4443920`, `4461799`, and `4483589`. Their Pass0
responses and hashes are inherited unchanged from `E-STABLE-ERROR-SUPPLY`. Diarization,
chunking, preprocessing, model output, and reference alignment are fixed.

Only an issuer-controlled IR or newsroom document that unambiguously names the target
quarter is eligible. The document must have been available no later than the meeting.
Exact publication evidence is recorded; an ambiguous timestamp is a temporal failure,
not an invitation to infer availability. Retrieval records URL, retrieval time, media
type, byte count, and SHA-256. Materials are stored outside Git.

## ORG construction policy

PDF text extraction is deterministic. Before any reference read, a material-only
candidate registry is frozen from:

- company, product, service, platform, programme, asset, field, and business-unit names;
- abbreviations and mixed letter-number terms;
- issuer-specific multiword terms.

People, isolated numbers, currencies, dates, generic financial vocabulary, and terms
without an exact source span are excluded. Every candidate retains meeting ID, document
hash, page, source text, canonical form, aliases, and category. Normalization is limited
to case, punctuation, whitespace, hyphen, and plural variants. No Pass0 or reference text
may add, delete, rename, or categorize a candidate.

## SUPPLY construction policy

Pass0 is used only as a runtime-legal trigger query. Exact canonical or alias presence
requests no correction. Otherwise, equal-width contiguous Pass0 n-grams are compared
with frozen aliases using `SequenceMatcher`; the threshold is fixed at `0.75`. At most
four unique candidates and 256 rendered characters are supplied per turn. Ranking is
similarity descending, then canonical form ascending.

A deranged control rotates each eligible, candidate-bearing meeting to the next eligible
meeting's registry in ascending file-ID order. It uses the same trigger, dose, and ranking policy. The reference is opened
once after the source registry, candidate registry, trigger implementation, runtime
manifest, score manifest, and reader hashes are frozen.

## Frozen gates

All gates must pass:

- eligible official material for at least three of four meetings;
- 100% source-span provenance and zero construction-time reference reads;
- at least 20 triggered, reference-supported corrective turns in total;
- at least three meetings with at least three corrective turns each;
- correct-material trigger precision at least 90% and recall at least 50%;
- correct-material precision exceeds the deranged arm by at least 30 percentage points;
- zero exact-form triggers and zero context-budget violations.

The one-shot verdict is `MEETING-MATERIAL-SUPPLY-FEASIBLE` only if every gate passes.
Otherwise it is `MEETING-MATERIAL-SUPPLY-INSUFFICIENT`. No threshold, alias, source, or
candidate may be changed after the reference read. A passing result permits only a new,
separately registered Omni experiment.
