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

## 4. Quarantine (rule Q1) -- RETIRED by v1.1, see §11

This section is the v1.0.0 record, kept verbatim for provenance: it is what the 75% quarantine
cost *was* and why the v1.1 question-usage policy replaced it. It is no longer the binding rule;
`AmiRoleRegistry.assert_question_usable` implements §11's policy, not this one.

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
2. **M3-SLU is ADMITTED (v1.1, 2026-08-18)** as a derived dataset with an independent evaluation
   system; its content overlap with governed AMI meetings is a hygiene note, not a bar. See §6 and
   `configs/corpora/m3slu-status.json`.

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

**v1.1 verdict (2026-08-18, supersedes the paragraph below as originally written): ADMITTED, with
the content overlap carried forward as a hygiene note, not a bar.** The owner ruling
(`docs/plans/2026-08-17-founding-workplan.md` §4b item 2): a derived dataset with an independent
evaluation system is not leakage. M3-SLU is scored on its own splits by its own harness; it never
reads or reports against this repository's AMI role registry or frozen ASR partition, so reuse of
its (partially AMI-sourced) content is a hygiene question, not a leakage one. M3-SLU's registry
presence is the sidecar `configs/corpora/m3slu-status.json` rather than a column here, because its
own governance (its splits) is independent of this registry's roster and roles. The measurement
below stands unedited and is *why* the hygiene note exists, not evidence against admission: one
probe instance, `ami_task2_1869`, resolves to **`ES2011a` — a member of our frozen dev-18**.
M3-SLU's AMI material therefore draws from our governed meetings, and there is no shipped field
that tells you which. This does not bar M3-SLU's own standalone discovery or evaluation use; it
means that *if* an M3-SLU instance is ever resolved to a specific AMI meeting and used alongside
this repository's own AMI-derived material in the same analysis, that resolution must run first
and the result must be filtered through this registry's normal exposure rules for the resolved
meeting -- M3-SLU must not be treated as meeting-anonymous by default in that combined-use case.

*Original v1.0.0 framing (retained for provenance):* "The consequence is a leakage warning, not a
convenience. ... If M3-SLU is ever used here, it must first be resolved to meetings by the content
join and then filtered through this registry; it must not be treated as safe by default. Because
that resolution is a derived inference needing its own validation pass, M3-SLU deliberately carries
**no** column in registry v1.0.0." That "barred pending leakage check" reading of the same evidence
is retired by the v1.1 ruling above; the underlying content-join measurement did not change.

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

**Meeting roles (§3): still proposal.** R1-R5 and the five roles are machine-verified and
unchanged since v1.0.0; the choice of R3 (MeetingQA *test* only, for the `qa-eval` *role*) remains
an engineering proposal awaiting owner confirmation. Nothing here authorizes a flight.

**MeetingQA question usage (§4/§11): BINDING as of v1.1 (2026-08-18).** The owner ruling in
`docs/plans/2026-08-17-founding-workplan.md` §4b settles this axis directly: it is no longer the
§4 relaxation option awaiting a decision, because the ruling replaces the role-keyed quarantine
mechanism itself rather than choosing a point on its R3-admits-dev spectrum. §4's 75% figure and
its "37 meetings / 1,703 questions" relaxation estimate are superseded, not merely revised -- see
§11.

**M3-SLU (§6): BINDING as of v1.1 (2026-08-18).** ADMITTED per the derived-dataset ruling; no
longer "barred pending leakage check." See §6's v1.1 verdict and `configs/corpora/m3slu-status.json`.

## 11. v1.1 (2026-08-18 evening) -- question-usage policy replaces the quarantine

Owner rulings recorded in `docs/plans/2026-08-17-founding-workplan.md` §4b (2026-08-18 morning):

1. **Split philosophy (program-wide).** Training-free discovery uses train/dev splits freely at
   every non-confirmatory stage; only test-split numbers are final results. Role registries
   protect **final-reporting sets only** -- AMI eval-16 and MeetingQA *test*-split questions.
   Train/dev questions are a free discovery surface on any meeting except eval-16.
2. **M3-SLU is ADMITTED** (§6).

### What changed

v1.0.0 quarantined a MeetingQA question the instant its meeting was spoken for by any AMI role
other than `qa-eval` (§4) -- a role-keyed mechanism that discarded 75.2% of MeetingQA (5,817 of
7,735 questions) as a side effect of an unrelated axis (which AMI role a meeting plays in *this
repository's own* pipeline). v1.1 replaces that mechanism with a question-usage policy keyed
directly on the two things ruling 1 names: eval-16 membership and MeetingQA's own split for that
meeting. The five AMI meeting roles, R1-R5, and eval-16's sanctity are **unchanged** -- v1.1 adds
a second, independent axis rather than editing the first:

| policy | condition | meaning |
|---|---|---|
| `untouchable` | meeting ∈ eval-16 (any MeetingQA split) | Same meaning as `held-out-confirmatory`: no exposure, no scoring, no discovery. Ever. |
| `reserved-final-reporting` | meeting ∉ eval-16, MeetingQA split = test | Reserved for Stage-3 final reporting; not a discovery surface pre-registration. |
| `usable-discovery` | meeting ∉ eval-16, MeetingQA split ∈ {train, dev} | Free discovery surface at every non-confirmatory stage -- **the asr-eval dev-18 flight set included**. |
| `no-meetingqa` | meeting has no MeetingQA coverage | Not applicable; nothing to gate. |

Because MeetingQA ships one split per *meeting* (never per question), this is a per-meeting
classification, exactly like the AMI role -- but along an orthogonal axis. A held-out-reserve
meeting's audio/transcript stays unexposable via `assert_exposable` (unchanged); its MeetingQA
train/dev questions can still be `usable-discovery`, because "any meeting except eval-16" in
ruling 1 governs MeetingQA question use, not this repository's own AMI-exposure rules for that
meeting under a different corpus. The two axes are independent by design.

### New counts (measured, `scripts/build_ami_role_registry.py`, 2026-08-18)

| policy | meetings | questions |
|---|---:|---:|
| `usable-discovery` | **101** | **4,732** |
| `reserved-final-reporting` | 49 | 2,235 |
| `untouchable` | 16 | 768 |
| `no-meetingqa` | 5 | 0 |
| **total** | **171** | **7,735** |

**Recovery: 4,732 usable-discovery questions, up from v1.0.0's 1,918 `qa-eval`-only figure** (a
2.47x increase) -- without touching a single AMI role or eval-16's sanctity. The recovery has two
sources: (a) held-out-137 meetings whose AMI role was `glossary-discovery` or `held-out-reserve`
now contribute their train/dev MeetingQA questions (90 meetings, the bulk of the gain); (b) the
asr-eval dev-18 flight set's own train/dev-split MeetingQA questions (11 of its 18 meetings) are
now usable for discovery too, per ruling 1's explicit "including dev-18". The `reserved-final-reporting`
count (49 meetings / 2,235 questions) is the old `qa-eval` role's 42 meetings plus dev-18's 7
test-split meetings -- the full non-eval-16 test-split surface, reserved for Stage-3. `untouchable`
(16/768) is exactly eval-16, unconditionally, confirmed directly: `EN2002a` carries MeetingQA
*dev*-split questions and is still `untouchable`, because eval-16 membership is checked before
MeetingQA split.

### Interpretation calls made while implementing (state them, per the build instructions)

1. **Question usage and AMI meeting role are independent gates, not a hierarchy.** Ruling 1 reads
   "any meeting except eval-16" literally, without carving out `held-out-reserve` or
   `glossary-discovery` meetings. A MeetingQA question about a `held-out-reserve` meeting is
   `usable-discovery` even though that meeting's own audio/transcript remains unexposable via
   `assert_exposable`. This is implemented as two orthogonal surfaces: this repository's own
   AMI-driven pipeline (chunking, glossary mining, minutes generation) is gated by
   `MeetingRole`/`assert_exposable`, unchanged; the MeetingQA question-answering surface is gated
   by `QuestionUsagePolicy`/`assert_question_usable`, new in v1.1. Using a MeetingQA question does
   not, by itself, expose that meeting under our own AMI role rules.
2. **Accessor shape.** "New policy accessors (`usable_discovery_questions()`,
   `reserved_test_questions()`, `untouchable_questions()`)" are implemented as
   `AmiRoleRegistry` methods returning the tuple of meeting ids carrying that policy, mirroring the
   existing `meetings_with_role` convention -- not per-question-id filters. A separate module-level
   `filter_question_ids_by_policy(registry, questions, policy)` (replacing v1.0.0's
   `quarantined_question_ids`) covers the question-id-stream use case for an eventual MeetingQA
   loader.
3. **Registry data shape.** v1.0.0's `quarantine.meetings` carried an explicit 124-row exception
   list. Since the v1.1 policy now partitions the *entire* 171-meeting roster (not a 25% minority),
   an explicit per-meeting list would duplicate data already in each meeting's own record
   (`role`, `meetingqa_split`, `meetingqa_questions`); the registry instead declares only the
   aggregate `question_usage.counts` block, cross-checked against the per-meeting recomputation at
   load time -- the same pattern `role_counts` already uses.
4. **`QuarantinedQuestionError` kept, repurposed.** Reserved-final-reporting and no-MeetingQA
   refusals still raise `QuarantinedQuestionError` (the "not usable *yet*" refusal); an eval-16
   refusal raises `HeldOutLeakageError` (the "never usable" refusal) -- unconditionally, regardless
   of `QuestionUsagePolicy`, matching how eval-16 already refuses AMI exposure via the same
   exception type.

### Reproduction

Unchanged from §9, now producing the v1.1 registry (`schema_version: "1.1.0"`):

```bash
python scripts/build_ami_role_registry.py \
  --data-root "$SPEECHRL_DATA_DIR/datasets" \
  --table-out docs/readiness/2026-08-18-ami-overlap-matrix.md
pytest tests/unit/corpora
```
