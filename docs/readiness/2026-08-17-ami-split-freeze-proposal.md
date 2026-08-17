# D2 — AMI split freeze proposal (2026-08-17)

Task D2 of the founding workplan. Measured locally on CPU from shipped bytes only; zero model
contact, no downloads. Data root: `$SPEECHRL_DATA_DIR`
(`/mnt/e/chao_workspace/exploring-l4-intelligence/speechrl-data`), carrier `ami-meeting-corpus`,
lock key `ami-meeting-corpus` in umbrella `docs/datasets.lock.json`.

## 0. Summary of the recommendation

Adopt the **full-corpus ASR partition** (dev 18 / eval 16) as the single frozen split for this
repository, and additionally record the **shipped `meetings.xml` scenario-only convention** as a
secondary cross-reference. The new local finding that decides the matter is in §3: the two
conventions do **not** conflict in the direction that matters — the ASR dev-18 and eval-16 sets are
disjoint from the shipped scenario-only training set, and the ASR eval-16 is disjoint from the
shipped scenario-only development set. Adopting the ASR partition therefore leaks nothing under
either convention.

## 1. Convention A — full-corpus ASR partition (train 135 / dev 18 / eval 16)

This is the partition the 2026-08-17 carrier manifest materialized:
`derived/carrier-manifests/2026-08-17/ami-dev-partition.manifest.json`.

Verbatim provenance fields from that manifest:

```
"partition_scheme":     "AMI full-corpus ASR partition (train 135 / dev 18 / eval 16)"
"partition_provenance": "published-standard-list-transcribed; NOT sourced from a shipped file"
"condition":            "Mix-Headset (IHM-mix)"
"n_meetings": 18, "n_missing": 0, "total_duration_s": 34801.825, "total_duration_h": 9.667
```

**Provenance caveat, stated honestly.** The 18 dev ids were transcribed from the published standard
partition and then verified to exist on disk. They were **not** read out of any shipped file. I
confirmed this independently: `datasets/ami/annotations/` contains only the two annotation zips,
an extraction receipt, and the two extracted trees; no file matching `*split*`, `*partition*`, or
`*dev*` exists at any depth, and neither `manual_1.6.2` nor `auto_1.5.1` ships a partition list.
The umbrella lock entry carries no split key either. The eval-16 list has the same provenance
status and additionally was never written down anywhere on disk — the manifest records only the
count `eval_meetings_present_on_disk: 16`.

This caveat is real but it is **not** unbounded: §3 shows that 12 of the 18 dev ids and 12 of the
16 eval ids are corroborated by shipped annotation attributes, with zero shipped contradictions.

### Dev — 18 meetings, 34,801.825 s = 9.667 h (WAV headers), 1,113,664,738 bytes

```
ES2011a ES2011b ES2011c ES2011d
IS1008a IS1008b IS1008c IS1008d
TS3004a TS3004b TS3004c TS3004d
IB4001  IB4002  IB4003  IB4004  IB4010  IB4011
```

12 scenario meetings (ES/IS/TS) + 6 non-scenario meetings (IB). All 18 present on disk as
`amicorpus/<ID>/audio/<ID>.Mix-Headset.wav`, mono 16-bit 16 kHz PCM. The same 18 durations summed
from the shipped `meetings.xml` `duration` attribute give 34,926.705 s (9.702 h), a +0.36 %
difference against the WAV headers; **the WAV-header figure is authoritative** for budget purposes.

### Eval / held-out-for-confirmatory — 16 meetings

```
ES2004a ES2004b ES2004c ES2004d
IS1009a IS1009b IS1009c IS1009d
TS3003a TS3003b TS3003c TS3003d
EN2002a EN2002b EN2002c EN2002d
```

All 16 verified present on disk. 12 scenario + 4 non-scenario (EN).

### Held-out remainder — 137 meetings

Everything else on disk. Set arithmetic: 171 on-disk meeting directories − 18 dev − 16 eval = 137.

```
EN2001a EN2001b EN2001d EN2001e EN2003a EN2004a EN2005a EN2006a EN2006b EN2009b EN2009c EN2009d
ES2002a ES2002b ES2002c ES2002d ES2003a ES2003b ES2003c ES2003d ES2005a ES2005b ES2005c ES2005d
ES2006a ES2006b ES2006c ES2006d ES2007a ES2007b ES2007c ES2007d ES2008a ES2008b ES2008c ES2008d
ES2009a ES2009b ES2009c ES2009d ES2010a ES2010b ES2010c ES2010d ES2012a ES2012b ES2012c ES2012d
ES2013a ES2013b ES2013c ES2013d ES2014a ES2014b ES2014c ES2014d ES2015a ES2015b ES2015c ES2015d
ES2016a ES2016b ES2016c ES2016d IB4005
IN1001 IN1002 IN1005 IN1007 IN1008 IN1009 IN1012 IN1013 IN1014 IN1016
IS1000a IS1000b IS1000c IS1000d IS1001a IS1001b IS1001c IS1001d IS1002b IS1002c IS1002d
IS1003a IS1003b IS1003c IS1003d IS1004a IS1004b IS1004c IS1004d IS1005a IS1005b IS1005c
IS1006a IS1006b IS1006c IS1006d IS1007a IS1007b IS1007c IS1007d
TS3005a TS3005b TS3005c TS3005d TS3006a TS3006b TS3006c TS3006d TS3007a TS3007b TS3007c TS3007d
TS3008a TS3008b TS3008c TS3008d TS3009a TS3009b TS3009c TS3009d TS3010a TS3010b TS3010c TS3010d
TS3011a TS3011b TS3011c TS3011d TS3012a TS3012b TS3012c TS3012d
```

**Open discrepancy, recorded not resolved.** 137 ≠ the published train count of 135. The published
partition assigns 135 + 18 + 16 = 169 meetings; the disk holds 171. Exactly two meetings are
therefore in the on-disk remainder but not in the published train list, and **no shipped file
identifies which two**. `IS1002a` and `IS1005d` cannot be the pair — the lock entry records them as
`unavailable_scenario_meetings` and they are absent from disk and from `meetings.xml` alike (35
scenario sessions x 4 suffixes − 2 = 138 scenario, + 33 non-scenario = 171). `IB4005` is a
suggestive candidate, being the only IB meeting the dev-18 list leaves behind, but this is
**conjecture and is not adopted**. The freeze below is deliberately written so that nothing depends
on resolving it: the held-out pool is defined by set complement, not by a transcribed train list.

## 2. Convention B — `meetings.xml` `seen_type` (shipped, fully machine-derivable)

Source: `datasets/ami/annotations/manual_1.6.2/corpusResources/meetings.xml`, 171 `<meeting>`
elements, exactly matching the 171 on-disk directories (zero orphans in either direction).

Attribute presence over the 171 meetings: `type` 171, `duration` 171, `visibility` 138,
`seen_type` 118, `k10`/`k5` 138, `topic` 33.

Marginal counts:

| field | values |
|---|---|
| `type` | scenario 138, nonscenario 33 |
| `visibility` | seen 118, unseen 20, absent 33 |
| `seen_type` | training 98, development 20, absent 53 |

**The finding that matters: the cross-tabulation is completely clean.**

| `type` | `visibility` | `seen_type` | n |
|---|---|---|---|
| scenario | seen | training | 98 |
| scenario | seen | development | 20 |
| scenario | **unseen** | *absent* | 20 |
| nonscenario | *absent* | *absent* | 33 |
| | | **total** | **171** |

The prior local audit recorded this convention as "training 98 / development 20 / unmarked 53" and
concluded that a machine-checkable derivation of a partition from local bytes alone is not
possible. That conclusion is correct for the *ASR* partition but **too strong for this one**: the
53 unmarked meetings are not an undifferentiated residue. They decompose exactly into the 20
scenario meetings carrying `visibility="unseen"` and the 33 non-scenario meetings that the
scenario-only convention simply does not cover. `seen_type` is only ever populated for meetings the
annotation release treats as *seen*; the evaluation set is encoded by its absence plus
`visibility="unseen"`.

The scenario-only convention is therefore **train 98 / development 20 / evaluation 20**, and it is
fully derivable from shipped bytes with no transcription. Its evaluation set is:

```
ES2004a ES2004b ES2004c ES2004d   ES2014a ES2014b ES2014c ES2014d
IS1009a IS1009b IS1009c IS1009d   TS3003a TS3003b TS3003c TS3003d
TS3007a TS3007b TS3007c TS3007d
```

Its development set is:

```
ES2003a ES2003b ES2003c ES2003d   ES2011a ES2011b ES2011c ES2011d
IS1008a IS1008b IS1008c IS1008d   TS3004a TS3004b TS3004c TS3004d
TS3006a TS3006b TS3006c TS3006d
```

## 3. Cross-check: how much shipped support does the transcribed ASR list actually have?

This is the substantive new evidence.

**Dev.** All 12 scenario members of the ASR dev-18 (`ES2011a-d`, `IS1008a-d`, `TS3004a-d`) carry
shipped `seen_type="development"`. Not one carries `training`. The remaining 6 (`IB4001-4`,
`IB4010`, `IB4011`) are non-scenario, a class the shipped convention leaves entirely unmarked, so
they can be neither corroborated nor contradicted. **12/18 corroborated, 0/18 contradicted,
6/18 out of scope.**

**Eval.** 12 of the 16 (`ES2004a-d`, `IS1009a-d`, `TS3003a-d`) carry shipped
`visibility="unseen"` — i.e. the shipped release also treats them as evaluation material. The
other 4 (`EN2002a-d`) are non-scenario and out of scope. **12/16 corroborated, 0/16 contradicted.**

**Where the two conventions genuinely disagree.** The shipped development-20 minus the ASR dev-18
is exactly 8 meetings: `ES2003a-d` and `TS3006a-d`. The ASR partition assigns these to train; the
scenario-only convention calls them development. Symmetrically, `ES2014a-d` and `TS3007a-d` are
shipped-unseen (scenario-only evaluation) but fall in the ASR partition's train pool.

**Why that disagreement is harmless here.** This study performs no training. "Train" is not a
fitting set; it is an unused held-out pool. The only leakage question is whether anything we
*expose the frozen core to* is somebody's evaluation material. Checked directly:

- ASR dev-18 ∩ scenario-only evaluation-20 = **empty**.
- ASR eval-16 ∩ scenario-only development-20 = **empty**.
- ASR eval-16 ∩ scenario-only training-98 = **empty**.

So exposing the ASR dev-18 as the discovery surface touches no evaluation set under either
convention, and the ASR eval-16 remains untouched under both. The 8-meeting disagreement lives
entirely inside the never-exposed pool.

## 4. Freeze proposal

1. **Adopt Convention A**, the full-corpus ASR partition, as this repository's single frozen split.
   Rationale, in order of weight: (a) it is the comparability anchor for the cpWER / ORC-WER
   measurements this study reports, which is where published AMI numbers live; (b) it is already
   materialized and budgeted — flight G1 is scoped against its 9.667 h; (c) its dev set includes
   6 non-scenario meetings, so the discovery surface is not exclusively the remote-control design
   scenario, which matters directly for the entity-density weakness quantified in the L2 census;
   (d) §3 shows it now carries real shipped corroboration and zero shipped contradiction.
2. **Discovery surface** = the dev 18 ids listed in §1, Mix-Headset condition only.
3. **Held out** = the eval 16 ids listed in §1, plus the 137-meeting remainder. Nothing in this set
   may be exposed to the frozen core, and no gold annotation from it may enter a runtime path.
4. **Record Convention B as a secondary cross-reference**, with the ids enumerated in §2, so that
   comparisons against the scenario-only summarization literature remain possible without
   re-deriving anything. It is a reference, not a second live split — a single split governs
   exposure.
5. **Carry the provenance caveat forward verbatim** into any registration that binds these ids:
   the dev-18 and eval-16 lists are published-standard lists transcribed from knowledge, partially
   corroborated by shipped attributes as in §3, and not sourced from a shipped file. If an
   authoritative published list is ever fetched, re-verify these 34 ids against it before treating
   any number computed on them as comparable to published results.
6. **Resolve the prior internal inconsistency.** The SAEA readiness draft
   `docs/readiness/2026-08-17-carrier-inventory-and-split-policy-draft.md` instructs in §2/§4.3
   that dev/eval ids "must be taken from the official partition lists in
   `ami_public_manual_1.6.2.zip`, never hand-rolled", while its own §6.3 records that the zip ships
   no partition list. That instruction is unsatisfiable as written. This proposal supersedes it for
   this repository: the ids are fixed by §1, their provenance is stated in full, and the shipped
   corroboration in §3 is the substitute for the list the zip does not contain.
7. **Leave the 135-vs-137 discrepancy open** and do not let anything depend on it. The held-out
   pool is defined by complement of the two named sets, so the freeze is well-defined regardless.

## 5. Reproduction

Read-only, CPU, ~1 s. WSL2 `Ubuntu-24.04`, `~/.venvs/speechrl`, `PYTHONDONTWRITEBYTECODE=1`.
The measurements above come from `meetings.xml`, the on-disk `amicorpus/` directory listing, WAV
headers via `soundfile`, and the carrier manifest. No annotation content and no audio samples were
read.
