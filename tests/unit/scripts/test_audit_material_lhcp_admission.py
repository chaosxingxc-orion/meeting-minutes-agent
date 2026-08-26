"""Tests for the metadata-only LHCP admission audit."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path

import pytest


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "audit_material_lhcp_admission.py"
_SPEC = importlib.util.spec_from_file_location("audit_material_lhcp_admission", _SCRIPT)
assert _SPEC and _SPEC.loader
tool = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tool)


def test_normalized_tokens_is_fixed_ascii_form() -> None:
    assert tool.normalized_tokens("Higgs-boson: résumé_2022") == "higgs boson resume 2022"


@pytest.mark.parametrize(
    ("value", "event_id", "friendly_id"),
    [("856696c117.wav", "856696", "117"), ("1109611c314.wav", "1109611", "314")],
)
def test_audio_path_identifier(value: str, event_id: str, friendly_id: str) -> None:
    match = tool.PATH_PATTERN.fullmatch(value)
    assert match is not None
    assert match.group("event_id") == event_id
    assert match.group("friendly_id") == friendly_id


def test_range_reader_refuses_full_body_response() -> None:
    class Response:
        status_code = 200
        url = "https://example.test/file"
        headers = {"content-length": "100"}

        def raise_for_status(self) -> None:
            return None

        def close(self) -> None:
            return None

        @property
        def content(self) -> bytes:  # pragma: no cover - must not be accessed
            raise AssertionError("full body was read")

    class Session:
        def head(self, *args: object, **kwargs: object) -> Response:
            return Response()

        def get(self, *args: object, **kwargs: object) -> Response:
            return Response()

    reader = tool.CountingRangeReader("https://example.test/file", Session())
    with pytest.raises(RuntimeError, match="rejected range request"):
        reader.read(10)
    assert isinstance(reader, io.RawIOBase)
