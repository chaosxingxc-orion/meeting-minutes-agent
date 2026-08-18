"""Synthetic chunk-transcript fixtures for the glossary pipeline's tests.

``CHUNK_0_TEXT`` is hand-traceable end to end against
:mod:`meeting_minutes_agent.glossary.extract`'s three rule-based miners:
"Ortega" and "Fitzgerald" each appear twice as a non-sentence-initial
capitalized run AND (being repeated, length>=4, non-stopword words) once
more via the repeated-OOV miner, so after
:func:`~meeting_minutes_agent.glossary.dedupe.dedupe_candidates` each has
evidence_count 3 and both survive the default gate
(``min_evidence=2``) -- see ``docs/plans/`` and the module docstrings for
why this cross-miner overlap is expected, not a bug. This gives every
pipeline/arm test exactly two well-formed post-gate entries to work with
(needed for the ``deranged`` arm's derangement, which is a no-op below two
entries).
"""

from __future__ import annotations

CHUNK_0_TEXT = (
    "Today Ortega raised the first item. "
    "Later Ortega closed the discussion. "
    "Meanwhile Fitzgerald joined the call. "
    "Afterward Fitzgerald left the room."
)

# A second chunk, same two speakers of interest, for cross-chunk carry
# integration checks: Ortega recurs (evidence should ACCUMULATE across the
# chunk boundary); Harrison is new to this chunk only.
CHUNK_1_TEXT = (
    "Ortega proposed an amendment today. "
    "Ortega then asked Harrison to second the amendment. "
    "Harrison seconded the amendment."
)
