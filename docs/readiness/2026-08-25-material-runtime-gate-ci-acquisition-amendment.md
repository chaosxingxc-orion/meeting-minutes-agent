# E-MATERIAL-RUNTIME-GATE-CI acquisition amendment

## Scope and authority

This amendment is registered before document download. It authorizes retrieval
of exactly the six raw official documents in the frozen source registry to
`E:\datasets\meeting-material-gate-ci\2026-08-25`, deterministic parsing, and
candidate-count admission. It authorizes no reference read, audio decode,
embedding call, Pass0 generation, or Omni call.

The initial source registry SHA-256 was
`fffe1d2a2dbde9496182d77ddb526906c58fbf0f270fa9e30ceac420127d8998`.
It was superseded before any successful download by the registered Costco
source-resolution amendment. The SEC resolution hash was
`b89ca8d48c3f1618e24c05ded4c64dc4471b03e127af799eca8145e2d583eae8`;
after SEC transport rejection and resolution to Costco's official IR-linked
PDF asset, the active registry SHA-256 is
`10f91179311489de67c07b3a28a8c70f33bbef19dca0b8a809db227bae136656`.
After Costco acquisition and before HDFC acquisition, the registered HDFC
transport resolution produced the active SHA-256
`faebcd0427253f35bf312cf5f319bc47f585a94bd0f94fa4bc91a4f999f3f71a`.
After the Ferrari presentation transport failed and before Ferrari acquisition,
the registered same-day SEC exhibit resolution produced the active SHA-256
`a28add11e2f50dbf114f6d28c0f3201cfd896b4b454c1601e4029089b3948c7a`.

The source registry must be hashed before retrieval. Redirects may be recorded,
but an endpoint that returns an unsupported content type is rejected. Raw bytes
remain outside Git. The snapshot output path must not exist before construction
and the builder must refuse overwrite.

## Source policy

Only an issuer page/document or a regulated filing exhibit is allowed. The
publication date must not be later than the meeting date. Results releases,
presentations, financial results, and financial filing exhibits are allowed;
call transcripts, analyst transcripts, and post-meeting recaps are forbidden.

Costco and KKR are frozen as HTML because their admitted contemporaneous
official records are an issuer release page and an SEC Exhibit 99.1. HTML
parsing must retain visible text only and ignore script, style, noscript, and
SVG content. HDFC Bank, Sony, Ferrari, and Sanofi are frozen as PDFs.

## Admission decision

All six local files must exist, match PDF or HTML structure, retain raw SHA-256
provenance, and produce at least eight deterministic candidate surfaces per
meeting. Any failure returns `COHORT_ADMISSION_FAILED`; no meeting or source may
be substituted after this registration. A pass only permits separate Pass0
flight registration. It does not authorize model contact or reference scoring.
