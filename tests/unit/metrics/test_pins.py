from __future__ import annotations

import pytest

from meeting_minutes_agent.metrics.pins import (
    DEFAULT_COLLAR_SECONDS,
    MetricPins,
    default_metric_pins,
)


def test_metric_pins_content_hash_is_deterministic_regardless_of_construction_order():
    a = MetricPins(meeteval_version="0.4.3", collar_seconds=5.0)
    b = MetricPins(meeteval_version="0.4.3", collar_seconds=5.0)
    assert a.content_hash() == b.content_hash()


def test_metric_pins_content_hash_changes_with_collar():
    a = MetricPins(meeteval_version="0.4.3", collar_seconds=5.0)
    b = MetricPins(meeteval_version="0.4.3", collar_seconds=1.0)
    assert a.content_hash() != b.content_hash()


def test_metric_pins_content_hash_changes_with_meeteval_version():
    a = MetricPins(meeteval_version="0.4.3")
    b = MetricPins(meeteval_version="0.5.0")
    assert a.content_hash() != b.content_hash()


def test_metric_pins_content_hash_changes_with_timing_mode():
    a = MetricPins(meeteval_version="0.4.3", reference_pseudo_word_level_timing="character_based")
    b = MetricPins(meeteval_version="0.4.3", reference_pseudo_word_level_timing="equidistant")
    assert a.content_hash() != b.content_hash()


def test_default_metric_pins_pins_collar_5_seconds():
    pins = default_metric_pins(meeteval_version="0.4.3")
    assert pins.collar_seconds == DEFAULT_COLLAR_SECONDS == 5.0


def test_default_metric_pins_reads_installed_meeteval_version():
    pytest.importorskip("meeteval")
    pins = default_metric_pins()
    assert pins.meeteval_version and pins.meeteval_version != "unknown"


def test_metric_pins_to_dict_round_trips_every_field():
    pins = MetricPins(meeteval_version="0.4.3")
    d = pins.to_dict()
    assert d == {
        "meeteval_version": "0.4.3",
        "collar_seconds": 5.0,
        "reference_pseudo_word_level_timing": "character_based",
        "hypothesis_pseudo_word_level_timing": "character_based_points",
        "reference_sort": "segment",
        "hypothesis_sort": "segment",
    }
