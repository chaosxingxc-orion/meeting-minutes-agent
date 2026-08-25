# E4-XDOMAIN-SUPPLY-AUDIT-v3 preregistration

Date: 2026-08-22. Status: **REGISTERED BEFORE ANY RESERVE CONTENT READ**. The owner explicitly authorized this zero-model narrow-class reserve audit. No model contact, audio acquisition, audio decoding, or discovery reread is authorized.

## Question and frozen sample

The audit asks whether the untouched Earnings-22 reserve has enough speaker-exclusive recurrence in two technically defensible upstream classes, `ABBREVIATION` and `ALPHANUMERIC`, to justify later model-experiment design. It uses the 45 rows already assigned `reserve` by the v2 salted split in parent manifest `configs/probes/e4_xdomain_supply_v2/2026-08-21-input-manifest.json`, canonical content hash `67f0fc955ff9057ee5819ee3f05957ad1a04d2603564ba75366d4d319e2bd313`, at source commit `c05ab6fd8b4b627d123c922a22a39e993dd37635`.

The v3 reader must reject any discovery row and must never open, parse, or aggregate the 80 discovery files. Hashing and split identity were frozen before v2; v3 creates a reserve-only manifest containing no transcript content, surface, entity ID, or per-meeting statistic.

## Frozen proxy and counting rule

Only `ABBREVIATION` and `ALPHANUMERIC` mentions are admitted. Every other upstream class is excluded. Mentions without a valid aligned timestamp are conservatively excluded and counted only in aggregate. Surface normalization, 90-second pseudo-slices, `speaker × slice × surface` deduplication, and prior-speaker carry classification are unchanged from v2. A meeting is eligible when it has at least two speaker-exclusive carry units.

The class choice is a legitimate discovery-to-reserve selection prompted by v2's ontology finding. The quantitative gates are not fitted to discovery: they retain v2's absolute supply scale. The reserve must contain exactly 45 meetings, at least 20 eligible meetings, at least 100 speaker-exclusive carry units, and no single surface above 20% of exclusive supply.

## Ordered decision and interpretation

Integrity, schema, manifest, split, or discovery-isolation failure yields `INVALID-AUDIT`. Passing every supply gate yields `EARNINGS22-NARROW-SUPPLY-FEASIBLE`; otherwise the result is `INSUFFICIENT-EARNINGS22-NARROW-SUPPLY`.

A pass confirms only holdout supply for this narrow lexical proxy. It does not establish audio availability, transcription benefit, speaker-routing benefit, false-hint safety, or an agent-loop improvement operator. It authorizes only a separate audio-license and minimal-acquisition decision. A failure stops the Earnings-22 route without relaxing classes or gates.

Implementation and synthetic tests follow this registration. Before the sole reserve read, an amendment must freeze implementation hashes, the reserve-manifest hash, and offline test results. The CLI must refuse an existing output directory. No schema recovery or second reserve read is authorized under v3.
