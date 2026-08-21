# E4-DISJOINT-PREV staged Pass-0 preregistration

Date: 2026-08-21. Status: **REGISTERED BEFORE MODEL CONTACT; server clause superseded by `2026-08-21-e4-disjoint-prevalence-server-amendment.md`**. Owner authorization is the explicit instruction to run the reduced-resource staged Pass-0 option. Maximum authorization is 795 calls and 9,300 audio-seconds; no second-pass call is authorized.

## Question and non-claim

This screening pilot estimates whether the runtime-visible `speaker_wrong_disjoint` prevalence remains near the 48.2938% break-even point on an untouched ContextASR roster. It does not measure carry repair, WER, or policy benefit and cannot confirm E4-DISJOINT.

## Frozen roster and manifests

- Design SHA-256: `78d638065538777364bb98473e133b60a3966dcc7432d05e33cc13b532184cfe`.
- 60-dialogue roster SHA-256: `148de656073e4350667d1f3be04f6bb39e2e5ce4c6942fe45060d3d2b699da21`.
- Runtime manifest SHA-256: `046db6f5b8869dba152cab0c5fe2c22543739ad3e8a7ce531e41e067c6e883d5`; content hash `4ab699d03f55fca4687131e64787a9caa2d24116d362bdfa5952f95c0e3ac311`. It contains no reference transcript or entity list.
- Score manifest SHA-256: `d6f569e12b9d5d429d16ceaa1a41b92a89b891b73fc380899d22deb6f1ca4c68`; content hash `10d95813eb9e95d15eca29dddc355d69fd2875f99f110656ace625a4785d7568`.
- Source JSONL SHA-256: `4bbf64387d1c581df2c7ab5db9af4461e1112ee489377b67084c9b40cb6d45e8`.
- Selection: exclude exactly299 prior dialogues; among remaining dialogues with at least two same-speaker carry mentions, sort by `sha256("e4-disjoint-prev-2026-08-21-v1:" + uniq_id)` and take the first60.

## Frozen model path

- Model: `/home/yansuqing/models/qwen3-omni-30b-a3b-instruct/Qwen3-Omni-30B-A3B-Instruct-Q4_K_M.gguf`, SHA-256 `d9e2876556e7873e02c0359f832432ee2d67ab7dd0cee3efe0f77fd7a1f4dd85`.
- Multimodal projector: `/home/yansuqing/models/qwen3-omni-30b-a3b-instruct/mmproj-Qwen3-Omni-30B-A3B-Instruct-Q8_0.gguf`, SHA-256 `1104376db833f1e89c84834144ac3863340c2cd1ddaeddb39cb0247fb5c20c8d`.
- Server binary SHA-256: `ad694375c10915986a1c5cd7e35edb2962718320d8a9752ae77e41bd0f674fa9`.
- Server arguments: `-c 16384 -np 1 -fa on -ngl 999 -ctk q8_0 -ctv q8_0`; one slot; feature cache `e4-confirmatory-q4km`.
- Request: byte-identical E4-CF system instruction and template, temperature0, seed0, max tokens512, no text supply.

## Frozen stages and budgets

| Stage | Dialogue slice | Calls | Exact audio seconds | Hard cap |
|---:|---|---:|---:|---|
| 20 | `[0,20)` | 265 | 3,087.849 | 265 calls / 3,100 s |
| 40 | `[20,40)` | 265 | 3,075.910 | 265 calls / 3,100 s |
| 60 | `[40,60)` | 265 | 3,068.138 | 265 calls / 3,100 s |

Each stage has a separate responses file and receipt. A failed transport has zero automatic retries. Resume is allowed only for missing request IDs, under a new receipt and the same stage cap. Stage40 may run only if stage20 reads `CONTINUE`; stage60 may run only if stage40 reads `CONTINUE`.

## Frozen read and decisions

State construction is hypothesis-only, chronological, `min_evidence=1`, deduplicated, cap8, with equal nonzero global/speaker/wrong width. Predicate positive means normalized speaker and wrong inventories are disjoint. Gold fields only define natural carry targets and never enter runtime.

The read reports point prevalence, dialogue-cluster bootstrap80%/90% intervals with20,000 fixed-seed replicates, and usable carry fraction. Decisions are frozen in `docs/plans/2026-08-21-e4-disjoint-prevalence-pilot.md`: early low-prevalence thresholds are35% at stage20 and40% at stage40; the stage60 pass requires point prevalence at least48.2938%, 80% lower bound at least40%, and usable carry fraction at least85%.

## Frozen code

- Roster builder `51b0d139b5a81853baaf36a5178d3bf8744a663fdb18364e62649d083bdc31d1`.
- Manifest builder `6339758709651c53e87dba62c0c8dfb034394d472cb16bfd57137541225d872e`.
- Launcher `cc36c97f9831311425fd580238dd206da0292bdd1c062dff5fe4914c97104e81`.
- Read CLI `fa6407bdd2c73bf77b52387514be8f199ce6e9f8534dca46e6fa62d29578d1f4`.
- Aggregator `9f93fd9863dcde9d01bc7a87a7c1771ad9b18f47233aaedc14c9ab625119fc65`.
- Aggregator tests `cb64464e3caf9dd3627fdc3da47acccb8d9a9fa65c3ab64d70452f73278111fc`; roster test `603beac4a20605ad470825cb472ae4fb51fd05b0fa042b49051745ef964774c6`. Seven dedicated/regression tests passed before registration.

All flight and read output paths must not exist before their stage. Reads may expose only aggregate counts and intervals. A screen pass permits budget reconsideration only; it does not authorize E4 second pass or an agent loop.
