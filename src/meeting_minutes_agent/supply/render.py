"""Deterministic per-chunk prompt-supply block assembly (component C4).

:func:`render_supply_block` is the ONE render function every registered
supply arm goes through (see :mod:`.config`'s docstring); it reads an
:class:`~meeting_minutes_agent.state.episode.EpisodeState` and a
:class:`~.config.SupplyArmConfig` and returns a :class:`SupplyBlock` --
pure, no I/O, no randomness, same inputs always produce the same output
(byte-identical ``text``).

Leakage-tier gate: the glossary section is built through
:func:`meeting_minutes_agent.glossary.provenance.build_runtime_supply_view`
-- the SAME machine-enforced refusal every other runtime consumer uses.
Building a supply block over an episode state whose glossary contains ANY
Tier-M1 entry raises :class:`~meeting_minutes_agent.glossary.provenance.LeakageTierViolation`;
this module adds no separate M1 check of its own; it just never bypasses the
one that already exists.

Truncation order (explicit, documented, deterministic -- read this before
changing any of the three cap fields' behaviour):

1. Each section's OWN cap applies first and independently:
   ``max_glossary_terms`` keeps the top-ranked glossary entries (rank =
   :func:`meeting_minutes_agent.glossary.carry.rank_terms_by_frequency`'s
   order: evidence count desc, first-seen chunk asc, canonical surface asc
   -- the SAME deterministic tie-break
   :func:`meeting_minutes_agent.glossary.gate.apply_inventory_cap` uses, so
   supply-side ranking never disagrees with the gate stage's own inventory
   cap); ``max_speaker_bindings`` keeps the first N bindings sorted by
   ``cluster_id`` ascending (the speaker map has no evidence-count analogue
   to rank on, so alphabetical-by-cluster-id is the deterministic order of
   record).
2. If, AFTER step 1, ``max_supply_tokens_estimate`` is still exceeded, items
   are dropped ONE AT A TIME from the END of each already-capped, already-
   sorted list, checking the whole-block estimate after each drop:
   SPEAKER-MAP entries are dropped first (to empty, if needed), THEN
   glossary entries. Format instructions are NEVER truncated -- they are a
   small, fixed, pinned constant, not a dose-capped item.

   Design rationale (a real choice, stated for review, not a forced
   consequence of the spec): the glossary is this repository's primary
   registered carry axis (backbone design doc SS1's two registered arm
   joints are REVISE-stage glossary carry and INGEST provenance -- the
   speaker map is not one of them), so under a hard token budget the
   glossary is preserved longer than the speaker map.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..glossary.carry import rank_terms_by_frequency
from ..glossary.models import GlossaryEntry
from ..glossary.provenance import build_runtime_supply_view
from ..state.episode import EpisodeState
from ..state.models import SpeakerBinding
from .config import SupplyArmConfig
from .templates import (
    FORMAT_INSTRUCTIONS_TEXT,
    FORMAT_SECTION_HEADER,
    GLOSSARY_EMPTY_LINE,
    GLOSSARY_SECTION_HEADER,
    SPEAKER_EMPTY_LINE,
    SPEAKER_SECTION_HEADER,
    TEMPLATE_ID,
    TEMPLATE_SHA256,
)

_CHARS_PER_TOKEN_ESTIMATE = 4


@dataclass(frozen=True)
class SupplyBlock:
    """The rendered per-chunk injection block plus the accounting a caller
    (a controller, a receipt, a test) needs without re-deriving it from
    ``text``."""

    text: str
    glossary_terms_included: int
    glossary_terms_truncated: int
    speaker_bindings_included: int
    speaker_bindings_truncated: int
    estimated_tokens: int
    truncated_by_token_cap: bool
    template_id: str
    template_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "glossary_terms_included": self.glossary_terms_included,
            "glossary_terms_truncated": self.glossary_terms_truncated,
            "speaker_bindings_included": self.speaker_bindings_included,
            "speaker_bindings_truncated": self.speaker_bindings_truncated,
            "estimated_tokens": self.estimated_tokens,
            "truncated_by_token_cap": self.truncated_by_token_cap,
            "template_id": self.template_id,
            "template_sha256": self.template_sha256,
        }


def _estimate_tokens(text: str) -> int:
    """A cheap, deterministic token-count estimate: ``ceil(len(text) / 4)``
    characters-per-token, a common rough heuristic. Never calls a real
    tokenizer -- this is a dose-cap safety net, not a billing figure."""

    if not text:
        return 0
    return math.ceil(len(text) / _CHARS_PER_TOKEN_ESTIMATE)


def _render_glossary_line(entry: GlossaryEntry) -> str:
    extra_variants = [v for v in entry.variants if v != entry.canonical_surface]
    if extra_variants:
        return f"- {entry.canonical_surface} (aka {', '.join(extra_variants)})"
    return f"- {entry.canonical_surface}"


def _render_speaker_line(binding: SpeakerBinding) -> str:
    return f"Speaker {binding.cluster_id} — likely {binding.roster_name}, per shipped roster"


def _resolved_speaker_map(state: EpisodeState) -> tuple[SpeakerBinding, ...]:
    """One binding per distinct cluster id, using
    :meth:`EpisodeState.resolve_speaker`'s own latest-wins rule (reused, not
    reimplemented), sorted by ``cluster_id`` ascending for a deterministic
    presentation order."""

    cluster_ids = sorted({b.cluster_id for b in state.active_speaker_bindings()})
    resolved = (state.resolve_speaker(cid) for cid in cluster_ids)
    return tuple(b for b in resolved if b is not None)


def _assemble_sections(arm: SupplyArmConfig, glossary_lines: list[str], speaker_lines: list[str]) -> list[str]:
    sections: list[str] = []
    if arm.include_format_instructions:
        sections.append(FORMAT_SECTION_HEADER + "\n" + FORMAT_INSTRUCTIONS_TEXT)
    if arm.include_glossary:
        body = "\n".join(glossary_lines) if glossary_lines else GLOSSARY_EMPTY_LINE
        sections.append(GLOSSARY_SECTION_HEADER + "\n" + body)
    if arm.include_speaker_map:
        body = "\n".join(speaker_lines) if speaker_lines else SPEAKER_EMPTY_LINE
        sections.append(SPEAKER_SECTION_HEADER + "\n" + body)
    return sections


def render_supply_block(state: EpisodeState, *, arm: SupplyArmConfig = SupplyArmConfig()) -> SupplyBlock:
    """Render the deterministic per-chunk supply block for ``state`` under
    ``arm``'s dose caps and section toggles. Raises
    :class:`~meeting_minutes_agent.glossary.provenance.LeakageTierViolation`
    if ``include_glossary`` is true and ``state.glossary`` contains any
    Tier-M1 entry (module docstring)."""

    arm.validate()

    glossary_total = 0
    glossary_lines: list[str] = []
    if arm.include_glossary:
        runtime_glossary = build_runtime_supply_view(state.glossary)
        ranked = rank_terms_by_frequency(runtime_glossary)
        glossary_total = len(ranked)
        capped = ranked[: arm.max_glossary_terms] if arm.max_glossary_terms is not None else ranked
        glossary_lines = [_render_glossary_line(e) for e in capped]

    speaker_total = 0
    speaker_lines: list[str] = []
    if arm.include_speaker_map:
        resolved = _resolved_speaker_map(state)
        speaker_total = len(resolved)
        capped = resolved[: arm.max_speaker_bindings] if arm.max_speaker_bindings is not None else resolved
        speaker_lines = [_render_speaker_line(b) for b in capped]

    truncated_by_token_cap = False
    if arm.max_supply_tokens_estimate is not None:
        while True:
            text = "\n\n".join(_assemble_sections(arm, glossary_lines, speaker_lines))
            if _estimate_tokens(text) <= arm.max_supply_tokens_estimate:
                break
            if speaker_lines:
                speaker_lines = speaker_lines[:-1]
            elif glossary_lines:
                glossary_lines = glossary_lines[:-1]
            else:
                break
            truncated_by_token_cap = True

    text = "\n\n".join(_assemble_sections(arm, glossary_lines, speaker_lines))

    return SupplyBlock(
        text=text,
        glossary_terms_included=len(glossary_lines),
        glossary_terms_truncated=glossary_total - len(glossary_lines),
        speaker_bindings_included=len(speaker_lines),
        speaker_bindings_truncated=speaker_total - len(speaker_lines),
        estimated_tokens=_estimate_tokens(text),
        truncated_by_token_cap=truncated_by_token_cap,
        template_id=TEMPLATE_ID,
        template_sha256=TEMPLATE_SHA256,
    )


__all__ = ["SupplyBlock", "render_supply_block"]
