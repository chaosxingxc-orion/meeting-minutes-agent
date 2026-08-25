# E-MATERIAL-RUNTIME-GATE-CI source-resolution amendment

The first acquisition attempt stopped on the first file before any successful
download because Costco's frozen issuer page returned HTTP 429. No later source
was attempted and the material directory remained empty.

Before retry, the Costco source is resolved to the same-day SEC Form 8-K
Exhibit 99.1 for the same Q1 FY2022 results. This remains the same meeting,
issuer, reporting period, publication date, and document content class; only
the allowed publisher class changes from issuer to regulated filing archive.
It is not a meeting replacement and no reference, Pass0, retrieval score, or
outcome informed the change.

The superseded registry SHA-256 is
`fffe1d2a2dbde9496182d77ddb526906c58fbf0f270fa9e30ceac420127d8998`.
The active registry SHA-256 is
`b89ca8d48c3f1618e24c05ded4c64dc4471b03e127af799eca8145e2d583eae8`.

The SEC exhibit was then confirmed in the application browser, but both curl
and Invoke-WebRequest were rejected by SEC automated-traffic controls; the
external material directory was still empty. Before a second retry, Costco is
therefore resolved to the PDF asset linked by its official IR release page and
served from its Q4 delivery CDN. It has the same issuer, Q1 FY2022 release,
publication date, and content. This transport-only resolution is again frozen
before any successful download. The next active registry hash supersedes the
SEC-registry hash above.
The final active registry SHA-256 is
`10f91179311489de67c07b3a28a8c70f33bbef19dca0b8a809db227bae136656`.
