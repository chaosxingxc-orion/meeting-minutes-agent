# G1 floors campaign — ONE-SHOT DESCRIPTIVE READ — 2026-08-20 (UTC)

> The registered one-shot read of the flown G1 floors campaign
> (`docs/checks/2026-08-19-g1-floors-flight/`, 72/72 items, 1,932 calls). Zero model contact:
> every number here comes from already-flown reply JSONLs scored against AMI/MeetingQA gold.
> **Descriptive only — no branch verdicts** (`scripts/g1_read.py`'s own module contract).
> The narrative record is `docs/readiness/2026-08-19-g1-floors-verdict.md`.

## 1. What ran

| stage | command | output |
|---|---|---|
| the read | `scripts/g1_read.py` (`script-read.sh`) | `verdict.json`, `report.txt` |
| the supplement | `supplement.py` (`script-supplement.sh`) | `supplement.json`, `supplement.txt` |
| the arm contrasts | `ablations.py` (`script-ablations.sh`) | `ablations.json`, `ablations.txt` |
| table rendering | `render-tables.py` | (stdout only; feeds the verdict document's tables) |

`scripts/g1_read.py` scores the transcribe head on all four arms (cpWER, secondary
speaker-confusion, primary tcpWER−tcORC@5s, grammar compliance; per arm × meeting and pooled)
and bootstraps the deployment gap on cpWER. It does **not** emit SAER-M, QA, or gaps on the
other metrics; `supplement.py` supplies exactly those, using only committed scoring functions
(`heads.qa.parse_qa_response` + `g1_scoring.arm_qa_report`,
`heads.minutes.parse_minutes_response` + `g1_scoring.meeting_saer_m`, and
`g1_scoring.compute_deployment_gap` re-applied to the per-meeting numbers `verdict.json`
already carries — same seed 20260818, 10,000 replicates, 90 % percentile CI).

Roster: dev-18, all 18 meetings, all four arms — `g1_campaign.meetings_for_mode("floors")`,
never a hand-typed list. Pins hash `d9a9d122…c247f`. Read created 2026-08-20T00:14:15Z.

## 2. Machinery state at read time (disclosed)

The read ran at repository HEAD `5fd9a185a391ad6672af57c7c557fc100447f505` **plus two
uncommitted pre-read repairs**, which the commit carrying this directory lands:

1. **`scripts/g1_read.py` could not score Z-nodiar at all.** Its `run_read` passed
   `vad_manifest_dir=None` unconditionally and the CLI exposed no flag for it, so the fourth
   registered arm — whose slice plan exists only in the PRECOMP VAD supplement's manifest —
   failed closed with `G1VadSupplementMissingError`. A `--vad-manifest-dir` flag was added and
   threaded through (2 unit tests).
2. **A slice whose gold reference carries zero words aborted the whole read.** Every WER-family
   rate divides by the reference word count, so meeteval returns `error_rate=None` for such a
   pair and `ConfusionCostResult.confusion_cost` computed `None - None` → `TypeError`. The
   first read attempt died on this after ~30 minutes with no output written (the one-shot guard
   was never armed, so this read is still the first and only completed one).
   `g1_scoring.score_transcribe_slice` now checks the denominator first and records the slice as
   `reference_empty` with `cp_wer=None`, excluded from every mean and counted in its own
   disclosure — never folded into an ORC refusal and never scored as the 1.0 an empty
   *hypothesis* earns. A `TimestampValidationError` inside the time-constrained pair is likewise
   demoted to a per-slice refusal instead of aborting the read (7 further unit tests).

Full suite after both repairs: **1,521 passed, 6 skipped** (1,512 + 9 new tests). The flight
archive's own `MANIFEST.sha256` verified: 114 entries, 0 FAILED.

## 3. No run-dir mutation

The five response sinks under
`$SPEECHRL_DATA_DIR/derived/meeting-minutes/g1/runs/2026-08-19-g1-floors/responses/` are
**byte-identical before and after the read** — all five sha256s match
`docs/checks/2026-08-19-g1-floors-flight/response-sinks.sha256` exactly. Nothing under the run
directory was written, moved, or re-hashed; the read opens the sinks read-only.

The read ran under a 32 GiB address-space rlimit (the P-PROMPT read's own ORC discipline), so an
infeasible ORC dynamic program raises `MemoryError` and is recorded as a refusal rather than
inviting the OOM killer. Zero `MemoryError` refusals were recorded; all 12 confusion refusals
came from the deterministic `orc_dp_bound` state-space cap.

## 4. Headline numbers (the verdict document is the narrative authority)

| arm | pooled mean cpWER | secondary confusion | primary tcpWER−tcORC@5s | grammar |
|---|---:|---:|---:|---:|
| Z-turn (deployment) | 0.6099 | +0.2054 | +0.1042 | 0.9972 |
| Z-oracle (ceiling) | 0.6061 | +0.2195 | +0.1131 | 0.9984 |
| Z-free | 0.8726 | +0.4001 | n/a | 1.0000 |
| Z-nodiar | 0.8816 | +0.3841 | n/a | 1.0000 |

Deployment gap (Z-turn − Z-oracle, 18-meeting clustered paired bootstrap, 90 % CI): cpWER
**+0.0037 [−0.0124, +0.0193]**, CI includes zero. Only the primary confusion cost's CI excludes
zero (−0.0090 [−0.0160, −0.0025]). QA macro-F1 0.0725 (Z-turn) / 0.0970 (Z-oracle) on the
capped 200. SAER-M is **not scoreable** on these replies (sentence-id join = 0; see the verdict
document §4).

## 5. Files

- `verdict.json` — the read's full output: per-arm × per-meeting × per-slice records, pooled
  numbers, the cpWER deployment gap, and the gap's meeting roster.
- `report.txt` — the read's own text summary.
- `supplement.json` / `supplement.txt` — QA, SAER-M, and the per-metric gaps.
- `ablations.json` / `ablations.txt` — the Z-free / Z-nodiar arm contrasts under the same
  clustered paired bootstrap (the preregistration's CI rule binds every comparison, not only the
  deployment gap).
- `script-read.sh`, `script-supplement.sh`, `script-ablations.sh`, `supplement.py`,
  `ablations.py`, `render-tables.py` — every operator script, archived verbatim.
- `read-console.log` — the read's non-JSON console output.
- `MANIFEST.sha256` — sha256 of every file in this directory.

Licences: AMI CC BY 4.0 (transcription/attribution/minutes numbers); MeetingQA CC BY-NC-SA
(every QA-derived number).
