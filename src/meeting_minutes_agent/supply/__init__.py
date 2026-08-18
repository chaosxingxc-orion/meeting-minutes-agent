"""E7a -- prompt-supply assembly (component C4).

Renders the per-chunk injection block from an
:class:`~meeting_minutes_agent.state.episode.EpisodeState`: glossary roster
rendering (leakage-tier gated, reusing
:mod:`meeting_minutes_agent.glossary.provenance`), speaker-map rendering,
pinned format instructions, and dose caps. See :mod:`.render` for the one
deterministic render function and its documented truncation order, and
:mod:`.config` for the arm-switches-as-data dataclass.
"""

from __future__ import annotations

from .config import SupplyArmConfig
from .render import SupplyBlock, render_supply_block
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

__all__ = [
    "SupplyArmConfig",
    "SupplyBlock",
    "render_supply_block",
    "TEMPLATE_ID",
    "TEMPLATE_SHA256",
    "FORMAT_SECTION_HEADER",
    "FORMAT_INSTRUCTIONS_TEXT",
    "GLOSSARY_SECTION_HEADER",
    "GLOSSARY_EMPTY_LINE",
    "SPEAKER_SECTION_HEADER",
    "SPEAKER_EMPTY_LINE",
]
