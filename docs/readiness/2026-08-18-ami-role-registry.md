# AMI role registry (2026-08-18)

The G1 precondition from the 2026-08-17 deep check, as recorded in
`docs/plans/2026-08-17-founding-workplan.md` §5 and
`docs/readiness/2026-08-18-g1-preregistration-draft.md` §5: *an AMI role registry — one role per
meeting: glossary-discovery / ASR-eval / QA-eval, machine-checked fail-closed — committed BEFORE
flight, with the MeetingQA overlap matrix as its input.* It supersedes the plain split freeze
(`2026-08-17-ami-split-freeze-proposal.md`), which it consumes rather than replaces: the frozen
ASR partition is still the authority on dev-18 / eval-16, and this registry is what makes that
freeze survive contact with the other corpora annotating the same meetings.

Measured on CPU from shipped bytes only; zero model contact, no downloads, ~10 s.

Artifacts:

| what | where |
|---|---|
| registry (data) | `configs/corpora/ami-role-registry.json` |
| loader + validator | `src/meeting_minutes_agent/corpora/roles.py` |
| tests | `tests/unit/corpora/test_roles.py` (30) |
| overlap matrix, machine | `docs/readiness/2026-08-18-ami-overlap-matrix.json` |
| overlap matrix, readable | `docs/readiness/2026-08-18-ami-overlap-matrix.md` (171 rows) |
| builder | `scripts/build_ami_role_registry.py` |

## 1. Why the registry is not optional

Three corpora annotate the *same* 171 AMI meetings under three mutually unaware splits: our frozen
ASR partition (dev 18 / eval 16 / held-out 137), MeetingQA's meeting-level split, and QMSum's
Product split. The measured collision is not marginal — it is total:

- **Every one of our dev-18 meetings carries MeetingQA questions** (806 of them), scattered across
  all three MeetingQA splits (8 dev / 7 test / 3 train meetings).
- **Every one of our eval-16 meetings carries MeetingQA questions** (768), likewise scattered
  (3 dev / 5 test / 8 train).

Without a registry, the G1 flight set doubles as QA evaluation material, and the confirmatory
hold-out is reachable through a side corpus that never heard of our freeze. The registry closes
that by construction rather than by discipline.

## 2. Overlap matrix — summary

171 on-disk AMI meetings. Full per-meeting table in
`docs/readiness/2026-08-18-ami-overlap-matrix.md`.

### Marginals

| axis | values |
|---|---|
| our ASR partition | dev-18 **18**, eval-16 **16**, held-out-137 **137** |
| MeetingQA split | train **64**, dev **48**, test **54**, absent **5** (166 meetings, 7,735 questions) |
| QMSum Product split | train **97**, val **20**, test **20**, absent **34** (137 meetings) |
| full annotation stack | **134** of 171 |

### Our ASR partition × MeetingQA split (meetings)

| | MQA train | MQA dev | MQA test | absent | total |
|---|---:|---:|---:|---:|---:|
| **dev-18** | 3 | 8 | 7 | 0 | 18 |
| **eval-16** | 8 | 3 | 5 | 0 | 16 |
| **held-out-137** | 53 | 37 | 42 | 5 | 137 |
| **total** | 64 | 48 | 54 | 5 | 171 |

The five meetings MeetingQA does not cover are `IN1005`, `IN1007`, `IN1008`, `IN1012`, `IN1013`.

### Our ASR partition × QMSum (meetings)

| | QMSum train | QMSum val | QMSum test | absent | total |
|---|---:|---:|---:|---:|---:|
| **dev-18** | 4 | 0 | 8 | 6 | 18 |
| **eval-16** | 8 | 0 | 4 | 4 | 16 |
| **held-out-137** | 85 | 20 | 8 | 24 | 137 |

**A numeric coincidence worth naming so nobody trips on it: QMSum's AMI material is also 137
meetings, and it is NOT our held-out-137.** QMSum ∩ held-out-137 = 113. The other 24 QMSum
meetings are exactly the 12 scenario members of our dev-18 and the 12 scenario members of our
eval-16. The two "137"s are unrelated sets that happen to have the same cardinality.

### Correction to an inherited figure

The workplan §5 and the G1 draft refer to *"the MeetingQA 80:10:10 overlap matrix"*. MeetingQA's
shipped AMI split is **not** 80:10:10 in any measured direction: by meetings it is 64 / 48 / 54
(38.6 % / 28.9 % / 32.5 %), and by questions 3,007 / 2,252 / 2,476 (38.9 % / 29.1 % / 32.0 %). The
question-title split and the `ProcessedTranscripts/Annotated-AMI-QA/<split>/` directory split agree
exactly, so this is the release's own split, not a parsing artefact. The "80:10:10" description
should be retired wherever it is repeated.

## 3. Role assignment

Rules, applied in order, first match wins — so the assignment is **total** over the roster and
exactly one role lands per meeting:

| rule | condition | role |
|---|---|---|
| **R1** | meeting ∈ frozen ASR dev-18 | `asr-eval` |
| **R2** | meeting ∈ frozen ASR eval-16 | `held-out-confirmatory` |
| **R3** | meeting ∈ held-out-137 **and** ∈ MeetingQA *test* split | `qa-eval` |
| **R4** | meeting ∈ held-out-137, not R3, full annotation stack | `glossary-discovery` |
| **R5** | otherwise | `held-out-reserve` |

| role | n | meaning |
|---|---:|---|
| `asr-eval` | **18** | G1 flight set: chunked transcription + attribution scoring |
| `qa-eval` | **42** | MeetingQA evaluation surface — the only role whose questions are usable |
| `glossary-discovery` | **76** | term-mining discovery surface; never scored as eval |
| `held-out-confirmatory` | **16** | frozen eval-16. No exposure, no scoring, no discovery. Ever |
| `held-out-reserve` | **19** | held-out remainder with no assigned role. No exposure |
| | **171** | |

`asr-eval` and `qa-eval` are exposable only for their own purpose; the two `held-out-*` roles are
unexposable. "Full annotation stack" = abstractive + extsumm + summlink + topics + dialogue acts +
words + segments all present in `ami_public_manual_1.6.2`. Per-layer coverage reconciles exactly
with the 2026-08-17 local audit (142 / 137 / 137 / 139 / 139 / 171 / 171), which is the same
reconciliation `scripts/nxt_reconcile.py` asserts.

### Hard constraints, and where each is enforced

| constraint | enforcement |
|---|---|
| no meeting carries two roles | the five role sets are asserted pairwise disjoint with union = roster (`test_no_meeting_carries_two_roles`); a duplicated meeting key in the JSON raises `DuplicateRoleError` via an `object_pairs_hook` rather than being silently last-wins |
| nothing in eval-16 gets any discovery/eval role | `HeldOutLeakageError` at load if any eval-16 meeting holds an active role, *and* at load if one is merely relabelled into the anonymous reserve; `assert_exposable` refuses all 16 at call time |
| the freeze cannot be edited from the data file | the file's `frozen_splits` lists must equal `FROZEN_DEV_18` / `FROZEN_EVAL_16` in `roles.py`, and `asr-eval` must be exactly the dev-18 |
| straddling questions are quarantined | `assert_question_usable` admits only `qa-eval` meetings; the declared quarantine must equal the recomputed one, question counts included |

## 4. Quarantine (rule Q1)

**Q1: a MeetingQA question is usable only when its meeting's registry role is `qa-eval`.** Every
other MeetingQA question straddles roles — its meeting is spoken for by the ASR flight set, by
glossary discovery, or is held out — and is quarantined.

**124 of the 166 MeetingQA meetings are quarantined, carrying 5,817 of the 7,735 questions (75.2 %).
1,918 questions on 42 meetings remain usable** (14–145 per meeting).

| quarantined because its role is | meetings | questions |
|---|---:|---:|
| `glossary-discovery` | 76 | 3,295 |
| `asr-eval` (the G1 flight set) | 18 | 806 |
| `held-out-confirmatory` (eval-16) | 16 | 768 |
| `held-out-reserve` | 14 | 948 |
| **total** | **124** | **5,817** |

By MeetingQA split, the quarantine takes **all 48 dev meetings** (2,252 questions), **all 64 train
meetings** (3,007), and **12 of the 54 test meetings** (558 — the 7 that are our dev-18 and the 5
that are our eval-16).

The quarantine is listed explicitly at meeting granularity in the registry's `quarantine.meetings`
array — all 124 entries, each with its role, MeetingQA split, question count and reason. Individual
question ids are derived rather than duplicated: `roles.quarantined_question_ids(registry,
questions)` returns them from any MeetingQA record stream, which keeps the list from drifting out
of sync with the release and avoids committing 5,817 ids that are already fully determined by the
meeting-level list.

**This 75 % cost is the honest price of the one-role rule and should be read as a decision surface,
not as settled.** It follows from R3 admitting only MeetingQA's *test* split. Measured alternative:
relaxing R3 to admit MeetingQA's *dev* split as well would move **37** held-out meetings into
`qa-eval` (31 taken from `glossary-discovery`, 6 from `held-out-reserve`), recovering **1,703**
questions — quarantine would fall to 4,114 of 7,735 (53.2 %) — while shrinking the discovery pool
from 76 meetings to **45**. That trade is an owner decision; it is recorded here and **not** taken.

## 5. Cross-corpus advisories (recorded, not enforced)

1. **QMSum overlaps our flight set.** 8 of QMSum's 20 Product *test* meetings are in our dev-18
   (`ES2011a-d`, `TS3004a-d`), and 4 more are in our eval-16 (`ES2004a-d`). Any QMSum summarization
   number this repository ever reports on those meetings is a number on material we exposed; it
   must carry that declaration. The registry records QMSum membership per meeting but assigns no
   QMSum role — QMSum is not a role-bearing surface here.
2. **M3-SLU cannot be governed by this registry as it ships.** See §6.

## 6. M3-SLU join verdict

The census claim under test was that no per-meeting join to AMI is possible from M3-SLU's text
layer. **Verified, and extended to the audio layer — but with an important qualification.**

*Field join: impossible.* The text layer (`m3-slu-task{1,2}-{preview,sample}.text.jsonl`) carries
exactly eight keys across all 10,808 sampled instances: `id`, `instruction`, `question`, `answer`,
`script`, `n_speakers`, `data_source`, `_shard`. The parquet layer adds exactly one further column,
`audio`, a `struct<bytes: binary, path: string>` — and `path` is only `<id>.wav`
(`ami_task2_1719.wav`), a restatement of the corpus-tagged sequence id. There is no meeting id, no
session field, no timing, and no mapping from M3-SLU's `<spk1>`/`<spk2>` tags to AMI's participant
letters. `data_source` distinguishes AMI (1,086 task-1 + 2,131 task-2 instances) from CHIME-6,
MELD and MultiDialog, and nothing finer. **No field join exists.**

*Content join: feasible, and demonstrated.* The `script` field is verbatim AMI dialogue. Matching a
normalised 12-token n-gram from each instance's longest turns against an index of 166 AMI
transcripts resolved **10 of 12** probe instances to **exactly one** meeting each — different
meetings for different instances, which is the signature of a real join rather than noise. The two
misses are consistent with source meetings outside the 166-meeting index.

**The consequence is a leakage warning, not a convenience.** One probe instance, `ami_task2_1869`,
resolves to **`ES2011a` — a member of our frozen dev-18**. M3-SLU's AMI material therefore draws
from our governed meetings, and there is no shipped field that tells you which. If M3-SLU is ever
used here, it must first be resolved to meetings by the content join and then filtered through this
registry; it must not be treated as safe by default. Because that resolution is a derived inference
needing its own validation pass, M3-SLU deliberately carries **no** column in registry v1.0.0.

## 7. Consequences for G1 (flagged, not resolved)

The flight set's annotation coverage is uneven, and the G1 draft's arms depend on layers that 6 of
the 18 dev meetings do not have:

| dev-18 subset | words / segments | topics | dialogue acts | abstractive | extractive + summlink |
|---|:---:|:---:|:---:|:---:|:---:|
| `ES2011a-d`, `IS1008a-d`, `TS3004a-d` (12) | yes | yes | yes | yes | yes |
| `IB4003`, `IB4010`, `IB4011` | yes | yes | `IB4003` only | yes | **no** |
| `IB4001`, `IB4002`, `IB4004` | yes | **no** | **no** | **no** | **no** |

- **Oracle-diar timing is safe for all 18**: words and segments cover all 171 meetings, so the
  binding timing rule (segment timing from the oracle-diar layer, never synthetic timestamps) holds
  across the whole flight set.
- **Topic-aligned chunking (E3) has no topic boundaries for `IB4001`, `IB4002`, `IB4004`.** The
  Z-chunked arm needs a declared fallback for those three, and the fallback must be reported as a
  named condition rather than silently mixed into the arm.
- **SAER-M has no evidence-linked reference for any of the 6 IB meetings** (no extractive/summlink,
  and no abstractive for three of them). The minutes arm is scoreable on 12 of 18 meetings; n for
  the minutes metric is 12, not 18, and the power calculation must use 12.

## 8. Provenance and caveats

- The dev-18 / eval-16 ids carry the split freeze's provenance caveat **verbatim**: they are
  published-standard lists transcribed from knowledge, corroborated by shipped `meetings.xml`
  attributes (12/18 and 12/16, zero contradictions), and **not** sourced from a shipped file. The
  registry reproduces this in `provenance.asr_partition`; the freeze's instruction to re-verify the
  34 ids against an authoritative published list, should one ever be fetched, still stands.
- MeetingQA membership comes from `AllData/Dataset/final-AMI-{train,dev,test}.json` field `title`,
  cross-checked against `ProcessedTranscripts/Annotated-AMI-QA/<split>/` (exact agreement on all
  three splits; the builder aborts if they ever disagree). The `longer`, `ms` and `aug` variants
  are the same meeting-level split and add no meetings.
- QMSum membership is `data/Product/{train,val,test}/<meeting>.json`. QMSum's Academic (ICSI) and
  Committee (parliamentary) domains contain no AMI ids.
- The 135-vs-137 discrepancy the freeze left open stays open and stays harmless: the held-out pool
  is defined by set complement, so the registry is well-defined regardless.

## 9. Reproduction

Read-only, CPU, no model contact. WSL2 `Ubuntu-24.04`, `~/.venvs/speechrl`,
`PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=<repo>/src`:

```bash
python scripts/build_ami_role_registry.py \
  --data-root "$SPEECHRL_DATA_DIR/datasets" \
  --table-out docs/readiness/2026-08-18-ami-overlap-matrix.md
pytest tests/unit/corpora
```

The builder is deterministic and rewrites the registry, the machine matrix and the readable table
in place; `pytest tests/unit/corpora` re-checks the committed registry against every hard
constraint, so a hand-edit that breaks one fails the suite.

## 10. Status

**Proposal.** The rule set, the counts and the checks are machine-verified, but the choice of R3
(MeetingQA *test* only) and the resulting 75 % quarantine are engineering proposals awaiting owner
confirmation, as is the §4 relaxation option. Nothing here authorizes a flight.
