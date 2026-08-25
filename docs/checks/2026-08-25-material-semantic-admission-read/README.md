# Material Semantic Admission Read

The frozen ID-only audit returned
`ADMISSION_FAILED_NO_REFERENCE_UNREAD_MEETINGS`.

The Earnings-22 roster contains 125 unique meetings. The completed E4 v2
discovery read accounts for 80 IDs and the completed E4 v3 reserve read accounts
for the other 45. Their overlap is zero and their union is 125, leaving zero
reference-unread meetings against the minimum of six.

This read opened only the frozen roster and input manifests. It made zero
reference-content reads, material downloads, audio decodes, embedding calls, or
Omni calls. Exact input hashes and counts are recorded in
[`verdict.json`](verdict.json).
