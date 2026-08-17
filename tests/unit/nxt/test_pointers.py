from __future__ import annotations

import pytest

from meeting_minutes_agent.corpora.nxt.pointers import MalformedPointerError, parse_pointer


def test_parse_pointer_single_id():
    p = parse_pointer("ES2002a.A.words.xml#id(ES2002a.A.words0)")
    assert p.filename == "ES2002a.A.words.xml"
    assert p.start_id == "ES2002a.A.words0"
    assert p.end_id is None
    assert p.is_range is False


def test_parse_pointer_range():
    p = parse_pointer("ES2002a.A.words.xml#id(ES2002a.A.words0)..id(ES2002a.A.words12)")
    assert p.filename == "ES2002a.A.words.xml"
    assert p.start_id == "ES2002a.A.words0"
    assert p.end_id == "ES2002a.A.words12"
    assert p.is_range is True


def test_parse_pointer_preserves_raw():
    href = "ES2002a.A.words.xml#id(ES2002a.A.words0)"
    assert parse_pointer(href).raw == href


@pytest.mark.parametrize(
    "bad_href",
    [
        "",
        "no-hash-at-all.xml",
        "file.xml#not-an-id-pointer",
        "file.xml#id(x)..id(y)..id(z)",
    ],
)
def test_parse_pointer_rejects_malformed(bad_href):
    with pytest.raises(MalformedPointerError):
        parse_pointer(bad_href)
