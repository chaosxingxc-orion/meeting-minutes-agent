"""Tests for :mod:`meeting_minutes_agent.heads.request`: the shared
``HeadRequest`` shape and its transport-kwargs seam."""

from __future__ import annotations

from pathlib import Path

from meeting_minutes_agent.heads.request import HeadRequest, build_supplied_text


def test_build_supplied_text_drops_none_and_empty_preserving_order():
    assert build_supplied_text("a", None, "", "b") == ("a", "b")


def test_build_supplied_text_all_none_gives_empty_tuple():
    assert build_supplied_text(None, None) == ()


def test_to_transport_kwargs_matches_transport_request_field_names():
    req = HeadRequest(
        task_instruction="do the thing",
        supplied_text=("part-1", "part-2"),
        decoding_params={"temperature": 0.0},
        template_id="t-v1",
        template_sha256="deadbeef",
    )
    kwargs = req.to_transport_kwargs(request_id="req-1", audio_path=Path("chunk.wav"), audio_seconds=12.5)

    assert kwargs == {
        "request_id": "req-1",
        "task_instruction": "do the thing",
        "audio_path": Path("chunk.wav"),
        "audio_seconds": 12.5,
        "supplied_text": ("part-1", "part-2"),
        "decoding_params": {"temperature": 0.0},
    }
    # template identity is caller-side ledger metadata, never sent on the wire
    assert "template_id" not in kwargs
    assert "template_sha256" not in kwargs


def test_to_dict_shape():
    req = HeadRequest(
        task_instruction="do the thing",
        supplied_text=("a",),
        decoding_params={"k": 1},
        template_id="t-v1",
        template_sha256="deadbeef",
    )
    assert req.to_dict() == {
        "task_instruction": "do the thing",
        "supplied_text": ["a"],
        "decoding_params": {"k": 1},
        "template_id": "t-v1",
        "template_sha256": "deadbeef",
    }
