# E-MATERIAL-LHCP-FULL-POOL-CEILING preregistration

## Evidence status and question

This is a post-reference, development-only descriptive audit. The frozen
eight-key inventory was selected by salted hash rather than slice relevance and
contains only 39 oracle opportunity slices. Before inspecting full-pool local
labels, freeze this reader to ask whether the original meeting-material pool
contains enough local wrong-to-correct supply to justify a new extractor.

## Frozen inputs and construction

Reuse the SHA-256-bound LHCP material candidate pool, the already acquired 25
development references, and the 396-row semantic trace. Filter the source pool
to the exact 25 development meeting identities and require 4,886 unique
meeting-canonical candidates. Do not reparse PDFs or access confirmation, test,
audio, embedding, or Omni resources.

Reconstruct the preceding whole-meeting `difflib.SequenceMatcher` alignment
and 12-token padded reference windows. For every slice, evaluate every source
candidate from its meeting. A candidate is a wrong-to-correct opportunity only
when its exact lowercase ASCII-alphanumeric canonical occurs in the localized
reference window and not in the current Pass0 slice. Report opportunity slices,
meetings, unique candidates, category and normalized phrase-length strata.

## Decision rules

Return `LHCP_FULL_MATERIAL_POOL_POWER_READY` only for at least 157 opportunity
slices across at least 15 meetings. Return
`LHCP_FULL_MATERIAL_POOL_EXPLORATORY_ONLY` for at least 50 slices across at
least 10 meetings. Otherwise return `LHCP_FULL_MATERIAL_POOL_INSUFFICIENT`.

If insufficient, stop the LHCP material-candidate correction branch. If the
full pool passes while the frozen eight-key pool fails, candidate extraction is
the binding engineering target; register a reference-blind extractor before
any further embedding or Omni contact.

## Claim boundary

This is an oracle source-coverage ceiling on already opened development
references. It does not provide a runtime selector, precision estimate, WER
gain, speaker-specific result, or independent confirmation. Gold labels may not
select future calls or candidate thresholds.
