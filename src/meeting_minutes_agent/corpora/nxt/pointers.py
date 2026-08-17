"""NXT stand-off pointer syntax.

An ``nite:child`` or ``nite:pointer`` element's ``href`` attribute names a
target file and either one element id or an inclusive id RANGE within that
one file, e.g.::

    ES2002a.A.words.xml#id(ES2002a.A.words0)
    ES2002a.A.words.xml#id(ES2002a.A.words0)..id(ES2002a.A.words12)

This module only parses that *syntax*. Expanding a range into the concrete
elements it covers requires the parsed target file's document order and
lives in :mod:`idseq`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HREF_RE = re.compile(r"^(?P<filename>[^#]+)#id\((?P<start>[^)]+)\)(?:\.\.id\((?P<end>[^)]+)\))?$")


class MalformedPointerError(ValueError):
    """Raised when an href does not match the two NXT id-pointer forms this
    reader supports: ``file#id(x)`` or ``file#id(x)..id(y)``."""


@dataclass(frozen=True)
class NitePointer:
    raw: str
    filename: str
    start_id: str
    end_id: str | None

    @property
    def is_range(self) -> bool:
        return self.end_id is not None


def parse_pointer(href: str) -> NitePointer:
    """Parse one ``href`` attribute value into a :class:`NitePointer`.

    Raises :class:`MalformedPointerError` for anything that is not one of
    the two supported forms (this reader targets the AMI/ICSI NXT releases,
    not the full NXT query-language pointer grammar)."""

    match = _HREF_RE.match(href.strip())
    if match is None:
        raise MalformedPointerError(f"unrecognized NXT pointer syntax: {href!r}")
    return NitePointer(
        raw=href,
        filename=match.group("filename"),
        start_id=match.group("start"),
        end_id=match.group("end"),
    )
