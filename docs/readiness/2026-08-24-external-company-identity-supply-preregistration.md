# E-EXTERNAL-COMPANY-IDENTITY-SUPPLY preregistration

## Question

Can a public ticker-to-company identity supply provide precise corrective opportunities
for the four frozen Earnings-22 meetings? This is a zero-model feasibility audit. It does
not revise prior loop verdicts and cannot itself admit an Omni flight.

## Frozen evidence and policy

The registry contains only stable company/brand identities: `Jeronimo Martins`,
`TeamViewer`, `Galp`/`Galp Energia`, and `SK Telecom`. Product names, people, financial
facts, and current management are excluded. Each mapping records an official issuer page
and, where needed, a ticker mapping page. Retrieval date is 2026-08-24.

For each frozen turn, exact identity presence in Pass0 means no correction is requested.
Otherwise, contiguous Pass0 n-grams of the same token width are compared with registered
aliases using `SequenceMatcher`; similarity at least 0.75 triggers the canonical company
surface. Reference text is opened once after construction only to score whether the local
audio interval contains an alias. It never creates an alias or trigger.

## Provenance boundary

This source is tagged `PROPOSED_EXTERNAL_PUBLIC_REGISTRY`, not M0. Existing M0 is limited
to material co-shipped with a meeting. Runtime admissibility therefore remains
`pending_owner_ruling`, even if feasibility gates pass. A pass would support a provenance
decision and a separately registered model experiment only.

## Frozen inputs and gates

- Runtime SHA-256: `a2e272852cf35a6a67b9331b405a2472d3d3a217c8738f50693a8ad1898ce4b9`
- Score SHA-256: `163064779b3bf97244612fcd1af5333d04ffafe8a36c97656a32fa54dec70afb`
- Registry SHA-256: `c1e003ed2b6180aa9c66ec7c98298b55e52261321afa3e0dc85ee75eeca20d48`
- Trigger SHA-256: `84caff1fdfd12e4af1a2a16070ef67a590a0e6a0cf56cfe06b0428b729b8d3e3`
- Reader SHA-256: `a9edbef4eff29153180a667dfb1f5f876ac00982c0337801ce25c49cc71472d1`
- Pass0 hashes are those frozen by `E-LOOP-STABILITY-SUPPLY`.
- At least 20 triggered, reference-supported corrective turns in total.
- At least three meetings must have at least three such turns.
- Trigger precision must be at least 90%; recall over reference-defined corrective
  opportunities must be at least 50%.
- Exact Pass0 identities must never trigger, reference use in construction must be zero,
  and every rendered identity context must fit 256 characters.

Only all-gate success returns `EXTERNAL-COMPANY-IDENTITY-SUPPLY-FEASIBLE`. Failure stops
this four-identity branch; thresholds and aliases must not be tuned on the read.
