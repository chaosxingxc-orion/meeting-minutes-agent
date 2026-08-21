# E4-DISJOINT-PREV Pass-0 flight evidence

- Registered maximum: 795 calls and 9,300 audio-seconds; no second pass.
- Actual: 795/795 calls succeeded, zero retry/error/skip, 9,231.897 audio-seconds (2.564 hours).
- Stage20: 265 calls, 3,087.849 seconds.
- Stage40 increment: 265 calls, 3,075.910 seconds.
- Stage60 increment: 265 calls, 3,068.138 seconds.
- Runtime manifest content hash: `4ab699d03f55fca4687131e64787a9caa2d24116d362bdfa5952f95c0e3ac311`.
- Model and projector hashes matched the registration. The current server stack is pinned by `docs/readiness/2026-08-21-e4-disjoint-prevalence-server-amendment.md`.

Three responses reached the 512-token generation cap (`12316-3` turn1, `03879-5` turn5, and `11721-3` turn1). They span at most eight natural targets. The frozen scorer retained them. Even deleting all eight targets under the worst point-estimate direction leaves `(86-8)/(163-8)=50.32%`, above the 48.29% break-even threshold. This is a labelled truncation diagnostic, not a replacement verdict.

## Artifact hashes

- Stage20 responses: `2786a0c5edde176f7fc85f5dd846457b2d69333fa47aa149f3ff88f3871e4197`.
- Stage20 receipt: `787ade1628ef1c1eeed8db77833a2f08e139010d061daf81b0de660f83f29c8b`.
- Stage40 responses: `52f927700dd913f6da31fba3c24bff712cb90046b3d68bf7414ae25022cb4950`.
- Stage40 receipt: `78c64b1d0842ca2546a030869b1391e1776298543b80422f49a2ae9fc9d40c2b`.
- Stage60 responses: `90e6beab340cef2d46adeb9c7d1476ad6f518aea49c7b2648d5f41d0cda9dc84`.
- Stage60 receipt: `97cbb6de47b2f6f3a5c3df6d6174f365fe695091a33b44c958833dfadb457ac6`.

Responses contain model hypotheses and are evidence artifacts; Wiki pages must link to this README rather than reproduce their content.

