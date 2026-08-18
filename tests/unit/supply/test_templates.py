"""Pin test for the supply block's template hash: a duplicated, independent
copy of the pinned template text lives in THIS test file, separate from the
imported source constants, so an accidental edit to the wording in
``meeting_minutes_agent.supply.templates`` (without a matching, deliberate
update here) changes the hash and fails this test -- catching silent
template drift, not merely re-deriving the same hash from the same
imported strings."""

from __future__ import annotations

from meeting_minutes_agent.runreceipt import config_hash
from meeting_minutes_agent.supply.templates import TEMPLATE_ID, TEMPLATE_SHA256

_EXPECTED_TEMPLATE_ID = "supply-block-v1"

_EXPECTED_FORMAT_HEADER = "=== FORMAT INSTRUCTIONS ==="
_EXPECTED_FORMAT_INSTRUCTIONS = (
    "Use the KNOWN TERMS list below as the exact spelling for any matching "
    "term you hear; do not invent a different spelling for a term already "
    "listed there. Use the SPEAKER MAP below to attribute speech to a "
    "roster name when a speaker cluster id below is confidently that "
    "speaker; otherwise keep the raw speaker cluster id rather than "
    "guessing a name."
)
_EXPECTED_GLOSSARY_HEADER = "=== KNOWN TERMS (glossary) ==="
_EXPECTED_GLOSSARY_EMPTY = "(no known terms yet)"
_EXPECTED_SPEAKER_HEADER = "=== SPEAKER MAP ==="
_EXPECTED_SPEAKER_EMPTY = "(no speaker bindings yet)"


def test_template_id_is_pinned():
    assert TEMPLATE_ID == _EXPECTED_TEMPLATE_ID


def test_template_sha256_matches_an_independently_recomputed_hash_of_the_pinned_text():
    expected = config_hash(
        {
            "template_id": _EXPECTED_TEMPLATE_ID,
            "format_header": _EXPECTED_FORMAT_HEADER,
            "format_instructions": _EXPECTED_FORMAT_INSTRUCTIONS,
            "glossary_header": _EXPECTED_GLOSSARY_HEADER,
            "glossary_empty": _EXPECTED_GLOSSARY_EMPTY,
            "speaker_header": _EXPECTED_SPEAKER_HEADER,
            "speaker_empty": _EXPECTED_SPEAKER_EMPTY,
        }
    )
    assert TEMPLATE_SHA256 == expected


def test_template_sha256_is_a_64_char_hex_digest():
    assert len(TEMPLATE_SHA256) == 64
    int(TEMPLATE_SHA256, 16)  # raises ValueError if not valid hex
