# E4-XDOMAIN-SUPPLY-AUDIT preregistration

Date: 2026-08-21. Status: **REGISTERED BEFORE AGGREGATE CARRY READ**. The owner authorized this zero-model experiment after PR #2 merged. No model contact, audio re-encoding, or PRECOMP rebuild is authorized.

## Scope and frozen inputs

The audit screens whether two real-meeting domains contain enough runtime-extractable, speaker-exclusive lexical carry to justify a later balanced directional pilot. It reads QMSum commit `83d7768c1f2b4dfeb091385d3dc7e239b8e5bb7e`: Product train restricted to AMI `glossary-discovery`, and Academic train joined to local ICSI audio. Product and Academic validation/test content remain unread; Committee is excluded because local audio is absent.

The AMI role registry SHA-256 is `e21a297a31594204bfc96670aa507534340f329688b6baa03db1d65141e8200f`. Reserved or unknown AMI meetings, missing audio, schema drift, a dirty QMSum checkout, or an input identity mismatch fail closed.

## Frozen metrics and decision

The exact lexical proxy, segment-level deduplication, prior-speaker classifications, eligibility rule, per-domain gates, and ordered verdict are frozen in `docs/plans/2026-08-21-e4-xdomain-supply-audit.md`. Queries, answers, topics, summaries, model hypotheses, and reference error labels are prohibited. Outputs contain only aggregate counts, distributions, hashes, and concentration ratios; no transcript or extracted surface is persisted.

A domain passes only with at least 20 meetings, 20 meetings carrying at least two speaker-exclusive units, 100 speaker-exclusive units, 10 strict acronym/alphanumeric units, and no single surface above 20% of exclusive supply. Both domains passing yields `XDOMAIN-SUPPLY-FEASIBLE`; one yields `DOMAIN-LIMITED-SUPPLY`; neither yields `INSUFFICIENT-XDOMAIN-SUPPLY`; any integrity failure yields `INVALID-AUDIT`.

This is an exploratory supply screen, not an effect estimate. Capitalization is known to overstate open-vocabulary proper names in AMI, so the result must remain labelled lexical-proxy supply. A pass permits only a separately preregistered model pilot; it does not authorize one.

## Implementation and sole-read discipline

Implementation and synthetic tests will be added after this registration commit. Before the sole aggregate read, an amendment must record the implementation hash, selected-input manifest hash, and offline test result. The output directory must not exist and the CLI must refuse overwrite. Candidate rules and thresholds cannot change after the read.
