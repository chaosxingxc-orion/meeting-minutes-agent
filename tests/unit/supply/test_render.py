"""Tests for :mod:`meeting_minutes_agent.supply.render`: determinism, the
M1 leakage-tier refusal, per-section dose caps, and the documented
speaker-map-before-glossary token-cap truncation order."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.glossary.models import LeakageTier, ProvenanceTag
from meeting_minutes_agent.glossary.provenance import LeakageTierViolation
from meeting_minutes_agent.state.episode import EpisodeState
from meeting_minutes_agent.supply.config import SupplyArmConfig
from meeting_minutes_agent.supply.render import render_supply_block
from meeting_minutes_agent.supply.templates import (
    FORMAT_INSTRUCTIONS_TEXT,
    FORMAT_SECTION_HEADER,
    GLOSSARY_EMPTY_LINE,
    GLOSSARY_SECTION_HEADER,
    SPEAKER_EMPTY_LINE,
    SPEAKER_SECTION_HEADER,
    TEMPLATE_ID,
    TEMPLATE_SHA256,
)

from .fixtures import glossary_entry, state_with_three_terms_and_three_speakers


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------


def test_render_is_deterministic_for_identical_inputs():
    state = state_with_three_terms_and_three_speakers()
    arm = SupplyArmConfig(max_glossary_terms=2, max_speaker_bindings=2)

    block_a = render_supply_block(state, arm=arm)
    block_b = render_supply_block(state, arm=arm)

    assert block_a == block_b
    assert block_a.text == block_b.text


def test_render_with_empty_state_uses_placeholder_lines():
    block = render_supply_block(EpisodeState())
    assert GLOSSARY_EMPTY_LINE in block.text
    assert SPEAKER_EMPTY_LINE in block.text
    assert block.glossary_terms_included == 0
    assert block.speaker_bindings_included == 0
    assert block.truncated_by_token_cap is False


def test_render_carries_template_identity():
    block = render_supply_block(EpisodeState())
    assert block.template_id == TEMPLATE_ID
    assert block.template_sha256 == TEMPLATE_SHA256


def test_render_includes_format_instructions_by_default():
    block = render_supply_block(EpisodeState())
    assert FORMAT_SECTION_HEADER in block.text
    assert FORMAT_INSTRUCTIONS_TEXT in block.text


# ---------------------------------------------------------------------------
# M1 leakage-tier refusal (reuses glossary.provenance, no separate check)
# ---------------------------------------------------------------------------


def test_render_refuses_when_glossary_holds_an_m1_entry():
    state = EpisodeState().with_glossary_chunk(
        [glossary_entry("SecretCode", provenance=ProvenanceTag.METADATA, tier=LeakageTier.M1)]
    )
    with pytest.raises(LeakageTierViolation) as exc_info:
        render_supply_block(state)
    assert "SecretCode" in str(exc_info.value)


def test_render_does_not_refuse_on_m1_when_glossary_section_is_excluded():
    state = EpisodeState().with_glossary_chunk(
        [glossary_entry("SecretCode", provenance=ProvenanceTag.METADATA, tier=LeakageTier.M1)]
    )
    block = render_supply_block(state, arm=SupplyArmConfig(include_glossary=False))
    assert GLOSSARY_SECTION_HEADER not in block.text
    assert "SecretCode" not in block.text


# ---------------------------------------------------------------------------
# section toggles
# ---------------------------------------------------------------------------


def test_section_toggles_omit_their_headers():
    state = state_with_three_terms_and_three_speakers()
    block = render_supply_block(
        state,
        arm=SupplyArmConfig(include_glossary=False, include_speaker_map=False, include_format_instructions=False),
    )
    assert FORMAT_SECTION_HEADER not in block.text
    assert GLOSSARY_SECTION_HEADER not in block.text
    assert SPEAKER_SECTION_HEADER not in block.text
    assert block.text == ""


# ---------------------------------------------------------------------------
# per-section dose caps: deterministic ranking + truncation counts
# ---------------------------------------------------------------------------


def test_glossary_cap_keeps_the_highest_ranked_terms_in_rank_order():
    state = state_with_three_terms_and_three_speakers()
    block = render_supply_block(state, arm=SupplyArmConfig(max_glossary_terms=2))

    assert block.glossary_terms_included == 2
    assert block.glossary_terms_truncated == 1
    # Alpha (evidence 5) then Beta (evidence 3, chunk 0) rank ahead of
    # Gamma (evidence 3, chunk 1) -- Gamma is the one dropped.
    alpha_pos = block.text.index("Alpha")
    beta_pos = block.text.index("Beta")
    assert alpha_pos < beta_pos
    assert "Gamma" not in block.text


def test_glossary_line_renders_extra_variants_but_not_a_bare_repeat():
    state = state_with_three_terms_and_three_speakers()
    block = render_supply_block(state)
    assert "- Beta (aka B.)" in block.text
    assert "- Alpha\n" in block.text
    assert "- Alpha (aka" not in block.text


def test_speaker_cap_keeps_first_n_by_cluster_id_alphabetical_order():
    state = state_with_three_terms_and_three_speakers()
    block = render_supply_block(state, arm=SupplyArmConfig(max_speaker_bindings=2))

    assert block.speaker_bindings_included == 2
    assert block.speaker_bindings_truncated == 1
    assert "Speaker S1" in block.text
    assert "Speaker S2" in block.text
    assert "Speaker S3" not in block.text  # alphabetically last, dropped


def test_speaker_line_format():
    state = state_with_three_terms_and_three_speakers()
    block = render_supply_block(state)
    assert "Speaker S1 — likely Alice, per shipped roster" in block.text


def test_zero_caps_produce_empty_sections_not_errors():
    state = state_with_three_terms_and_three_speakers()
    block = render_supply_block(state, arm=SupplyArmConfig(max_glossary_terms=0, max_speaker_bindings=0))
    assert block.glossary_terms_included == 0
    assert block.glossary_terms_truncated == 3
    assert block.speaker_bindings_included == 0
    assert block.speaker_bindings_truncated == 3
    assert GLOSSARY_EMPTY_LINE in block.text
    assert SPEAKER_EMPTY_LINE in block.text


# ---------------------------------------------------------------------------
# whole-block token cap: explicit, documented truncation order
# ---------------------------------------------------------------------------


def test_token_cap_is_a_noop_when_already_under_budget():
    state = state_with_three_terms_and_three_speakers()
    full = render_supply_block(state)
    capped = render_supply_block(state, arm=SupplyArmConfig(max_supply_tokens_estimate=full.estimated_tokens))
    assert capped == full
    assert capped.truncated_by_token_cap is False


def test_token_cap_truncates_speaker_map_before_glossary_documented_order():
    """The documented rule (supply.render module docstring): once the
    whole-block token cap forces cuts beyond the per-section caps, SPEAKER
    entries are dropped before GLOSSARY entries. Swept over a wide range of
    caps rather than one hand-picked number, so this is a real order
    invariant, not a coincidence of one arithmetic value."""

    state = state_with_three_terms_and_three_speakers()
    full = render_supply_block(state)
    assert full.glossary_terms_included == 3
    assert full.speaker_bindings_included == 3

    for cap in range(full.estimated_tokens, -1, -5):
        block = render_supply_block(state, arm=SupplyArmConfig(max_supply_tokens_estimate=cap))
        if block.glossary_terms_included < 3:
            assert block.speaker_bindings_included == 0, (
                f"cap={cap}: glossary was truncated to {block.glossary_terms_included} while "
                f"{block.speaker_bindings_included} speaker binding(s) still remained -- "
                "violates the documented speaker-before-glossary truncation order"
            )


def test_token_cap_never_truncates_format_instructions():
    state = state_with_three_terms_and_three_speakers()
    block = render_supply_block(state, arm=SupplyArmConfig(max_supply_tokens_estimate=1))
    assert FORMAT_SECTION_HEADER in block.text
    assert FORMAT_INSTRUCTIONS_TEXT in block.text
    assert block.speaker_bindings_included == 0
    assert block.glossary_terms_included == 0
    assert block.truncated_by_token_cap is True


def test_arm_config_rejects_negative_caps():
    with pytest.raises(ValueError):
        render_supply_block(EpisodeState(), arm=SupplyArmConfig(max_glossary_terms=-1))
