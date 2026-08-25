# E-MEETING-MATERIAL-SUPPLY-AUDIT verdict

## Decision

`MEETING-MATERIAL-SUPPLY-INSUFFICIENT` — do not admit an Omni flight, GRPO,
GEPA, EM update, or multimodal policy search from this branch.

## Evidence

The official-material boundary passed: three meetings were eligible, all 49
candidates had exact source provenance, and construction used neither Pass0 nor
reference text. The runtime budget also passed.

The supply boundary failed decisively. Among 979 turns, the correct-material arm
made 418 activations but only three were reference-supported (0.72% precision).
It recovered 3 of 30 available opportunities (10% recall), with support confined
to one meeting. Its precision advantage over the equal-dose deranged arm was only
0.72 percentage points, far below the frozen 30-point gate.

## Claim boundary

This result rejects the frozen fuzzy trigger, not meeting materials as an evidence
source and not Omni's ability to consume a correctly routed term. The inventory
contains 30 oracle-visible opportunities, so the remaining bottleneck is selecting
the right candidate for the current chunk without using gold.

No post-read threshold or inventory change is allowed. The next admissible branch
is a separately registered, zero-model router audit on independent meetings. It
must stratify short abbreviations versus proper names, define a confusability
reject rule before reference access, and retain the deranged-dose control.

- [Acquisition receipt](../checks/2026-08-25-meeting-material-supply-acquisition/README.md)
- [One-shot evidence](../checks/2026-08-25-meeting-material-supply-read/README.md)
- [Preregistration](2026-08-25-meeting-material-supply-audit-preregistration.md)
