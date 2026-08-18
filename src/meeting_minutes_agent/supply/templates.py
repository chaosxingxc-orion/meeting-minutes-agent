"""Pinned template strings for the per-chunk prompt-supply block.

Every string here is a constant -- never built from f-strings with runtime
content -- so the whole template can be identity-hashed once
(:data:`TEMPLATE_ID` / :data:`TEMPLATE_SHA256`, via
:func:`meeting_minutes_agent.runreceipt.config_hash`, the repo's one
canonical hashing entry point) and that hash is stable across every call to
:func:`meeting_minutes_agent.supply.render.render_supply_block` -- only the
per-episode CONTENT (glossary terms, speaker bindings) varies per call, never
the template's own wording.
"""

from __future__ import annotations

from ..runreceipt import config_hash

TEMPLATE_ID = "supply-block-v1"

FORMAT_SECTION_HEADER = "=== FORMAT INSTRUCTIONS ==="
FORMAT_INSTRUCTIONS_TEXT = (
    "Use the KNOWN TERMS list below as the exact spelling for any matching "
    "term you hear; do not invent a different spelling for a term already "
    "listed there. Use the SPEAKER MAP below to attribute speech to a "
    "roster name when a speaker cluster id below is confidently that "
    "speaker; otherwise keep the raw speaker cluster id rather than "
    "guessing a name."
)

GLOSSARY_SECTION_HEADER = "=== KNOWN TERMS (glossary) ==="
GLOSSARY_EMPTY_LINE = "(no known terms yet)"

SPEAKER_SECTION_HEADER = "=== SPEAKER MAP ==="
SPEAKER_EMPTY_LINE = "(no speaker bindings yet)"

TEMPLATE_SHA256 = config_hash(
    {
        "template_id": TEMPLATE_ID,
        "format_header": FORMAT_SECTION_HEADER,
        "format_instructions": FORMAT_INSTRUCTIONS_TEXT,
        "glossary_header": GLOSSARY_SECTION_HEADER,
        "glossary_empty": GLOSSARY_EMPTY_LINE,
        "speaker_header": SPEAKER_SECTION_HEADER,
        "speaker_empty": SPEAKER_EMPTY_LINE,
    }
)

__all__ = [
    "TEMPLATE_ID",
    "TEMPLATE_SHA256",
    "FORMAT_SECTION_HEADER",
    "FORMAT_INSTRUCTIONS_TEXT",
    "GLOSSARY_SECTION_HEADER",
    "GLOSSARY_EMPTY_LINE",
    "SPEAKER_SECTION_HEADER",
    "SPEAKER_EMPTY_LINE",
]
