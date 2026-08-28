# E-MATERIAL-LHCP-LOCAL-CANDIDATE-CEILING preregistration

## Evidence status and question

This is a post-reference, development-only descriptive audit. The preceding
opportunity audit already opened the 25 LHCP development references and showed
that only 12 frozen semantic top1 activations are local wrong-to-correct
opportunities. Before inspecting row-level candidate labels, freeze this reader
to ask whether the complete eight-candidate meeting inventory contains a larger
local correction ceiling. This audit cannot confirm a new policy.

## Frozen inputs and construction

Reuse the locally acquired 25 development references, the 396-row frozen
semantic trace, and its eight correct-meeting candidates per row. Do not access
the 45 confirmation references, a test split, audio bytes, embeddings, or Omni.
Reconstruct the same whole-meeting `difflib.SequenceMatcher` alignment and
12-token padded reference window used by the preceding audit.

Normalize every candidate canonical to lowercase ASCII alphanumeric tokens. A
candidate is:

- `retain` when its exact canonical occurs in both the current Pass0 slice and
  localized reference window;
- `wrong_to_correct_opportunity` when it occurs in the reference window but not
  the current Pass0 slice;
- `unsupported` otherwise.

For each slice, report whether any of its eight candidates is an opportunity,
the number and semantic ranks of such candidates, whether semantic top1 is one,
and whether any candidate is locally supported. Gold categories are analysis
only and may not select future model calls.

## Decision rules

Return `LHCP_LOCAL_CANDIDATE_POOL_POWER_READY` only when opportunity-bearing
slices number at least 157 and cover at least 15 meetings. Return
`LHCP_LOCAL_CANDIDATE_POOL_EXPLORATORY_ONLY` when at least 50 slices cover at
least 10 meetings. Otherwise return `LHCP_LOCAL_CANDIDATE_POOL_INSUFFICIENT`.

If the pool is insufficient, stop router optimization: candidate extraction is
the binding bottleneck. If the pool is sufficient but semantic top1 captures
less than 70% of opportunity-bearing slices, a rejectable local router is the
next research object. Otherwise the next step is a small, separately registered
Omni capability pilot covering a reference-independent frozen call set.

## Claim boundary

This is an oracle ceiling over an already reference-open development surface.
It does not measure runtime precision, WER improvement, speaker specificity,
generalization, or confirmation performance. No threshold may be tuned from
row-level results and presented as prospective evidence.
