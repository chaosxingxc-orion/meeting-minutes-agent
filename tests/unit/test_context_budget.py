"""Tests for :mod:`meeting_minutes_agent.context_budget`: the plan-time
serving-context assertion (13 tok/s audio, ``slot_context_tokens`` as a
declared config value -- never a hard-coded 49,152 -- and the
safety-margined fit check every planned request must pass)."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.context_budget import (
    DEFAULT_SLOT_CONTEXT_TOKENS,
    SlotContextConfig,
    SlotContextExceededError,
    assert_fits,
)


def test_default_slot_context_is_12288_not_49152():
    # analysis SS2: slot.n_ctx = n_ctx / n_parallel = 49152 / 4 = 12288.
    assert DEFAULT_SLOT_CONTEXT_TOKENS == 12288


def test_required_tokens_floor_quantizes_the_audio_term():
    config = SlotContextConfig(fixed_reserve_tokens=0, completion_tokens_per_audio_second=0.0)
    # 59.9s floors to 59 whole seconds of audio tokens, not 59.9.
    assert config.required_tokens(59.9) == 59 * 13


def test_required_tokens_sums_audio_reserve_and_completion():
    config = SlotContextConfig(fixed_reserve_tokens=950, completion_tokens_per_audio_second=4.0)
    # 90s: floor(90)*13 + 950 + 4.0*90 = 1170 + 950 + 360 = 2480
    assert config.required_tokens(90.0) == 2480


def test_fits_respects_the_safety_margin():
    config = SlotContextConfig(
        slot_context_tokens=1000, fixed_reserve_tokens=0, completion_tokens_per_audio_second=0.0, safety_margin=0.9
    )
    # budget = 900 tokens; 900/13 = 69.2s -> 69s fits (897 <= 900), 70s does not (910 > 900)
    assert config.fits(69.0) is True
    assert config.fits(70.0) is False


def test_assert_fits_raises_slot_context_exceeded_with_a_readable_message():
    config = SlotContextConfig(slot_context_tokens=1000, fixed_reserve_tokens=0, completion_tokens_per_audio_second=0.0)
    with pytest.raises(SlotContextExceededError, match="exceeds"):
        assert_fits(2400.0, config, label="40-minute single-pass request")


def test_assert_fits_passes_silently_when_within_budget():
    config = SlotContextConfig()
    assert_fits(60.0, config)  # does not raise


def test_the_40_minute_single_request_is_refuted_at_the_locked_np4_config():
    # docs/readiness/2026-08-18-chunk-slice-granularity-analysis.md SS3:
    # 2400s of audio alone is 31,200 tokens = 2.54x the whole -np4 slot.
    config = SlotContextConfig()  # the flown -c 49152 -np 4 default
    with pytest.raises(SlotContextExceededError):
        assert_fits(2400.0, config, label="E3's ~40-minute chunk as one request")


def test_the_same_2400s_request_fits_at_np1_equivalent_slot():
    # Same audio, a wider declared slot (-np1-equivalent, 49152 tokens):
    # proves the check reads slot_context_tokens as CONFIG, not a constant.
    wide = SlotContextConfig(slot_context_tokens=49152)
    assert_fits(2400.0, wide, label="same request at -np1")  # does not raise


def test_the_90s_transport_slice_comfortably_fits_the_default_slot():
    config = SlotContextConfig()
    assert_fits(90.0, config, label="90s transport slice")  # does not raise
    assert config.required_tokens(90.0) == 2480  # analysis SS8.1's own worked example


@pytest.mark.parametrize(
    "kwargs",
    [
        {"slot_context_tokens": 0},
        {"slot_context_tokens": -1},
        {"audio_tokens_per_second": 0},
        {"fixed_reserve_tokens": -1},
        {"completion_tokens_per_audio_second": -1.0},
        {"safety_margin": 0.0},
        {"safety_margin": 1.5},
    ],
)
def test_slot_context_config_validation_rejects_bad_fields(kwargs):
    with pytest.raises(ValueError):
        SlotContextConfig(**kwargs).validate()


def test_required_tokens_rejects_negative_audio_seconds():
    with pytest.raises(ValueError):
        SlotContextConfig().required_tokens(-1.0)


def test_max_feasible_audio_seconds_is_a_conservative_lower_bound():
    config = SlotContextConfig()
    ceiling = config.max_feasible_audio_seconds()
    assert config.fits(ceiling) is True
    assert config.fits(ceiling + 5.0) is False
