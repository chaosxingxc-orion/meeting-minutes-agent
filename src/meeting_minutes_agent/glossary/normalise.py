"""Stage 2: normalise -- unify case/punctuation/whitespace/hyphen variants
of a surface string into one comparable form.

Two surfaces that differ only in capitalization, surrounding punctuation,
internal whitespace run-length, or which hyphen-like character they use
(``-``, non-breaking hyphen, en-dash, em-dash, underscore) normalise to the
same string.
"""

from __future__ import annotations

import re

_HYPHEN_LIKE_RE = re.compile(r"[\-‐‑‒–—_]+")
_PUNCT_RE = re.compile(r"[^\w\s\-]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalise_surface(surface: str) -> str:
    """Lowercase; unify hyphen-like characters to a single ASCII hyphen;
    strip remaining punctuation; collapse whitespace; strip stray leading/
    trailing hyphens and spaces."""

    s = surface.strip().lower()
    s = _HYPHEN_LIKE_RE.sub("-", s)
    s = _PUNCT_RE.sub("", s)
    s = _WS_RE.sub(" ", s).strip()
    s = s.strip("-")
    return s
