"""Deterministic organization helpers for official meeting materials."""

from __future__ import annotations

from html.parser import HTMLParser
import re


_MIXED_OR_ACRONYM = re.compile(
    r"\b(?:[A-Z]{2,}[A-Z0-9&+.-]*|(?=[A-Za-z0-9&+.-]*[A-Za-z])(?=[A-Za-z0-9&+.-]*[0-9])[A-Za-z0-9&+.-]+)\b"
)
_PROPER_TOKEN = r"(?:[A-Z][a-z0-9&+.-]+|[A-Z]{2,}[A-Z0-9&+.-]*)"
_TITLE_SEQUENCE = re.compile(rf"\b{_PROPER_TOKEN}(?:\s+{_PROPER_TOKEN}){{1,3}}\b")
_SPACE = re.compile(r"\s+")

_GENERIC = {
    "adjusted ebitda",
    "annual report",
    "balance sheet",
    "business update",
    "cash flow",
    "conference call",
    "financial highlights",
    "financial results",
    "first half",
    "first quarter",
    "full year",
    "income statement",
    "investor briefing",
    "investor presentation",
    "net income",
    "operating income",
    "quarter results",
    "results presentation",
    "second quarter",
    "third quarter",
}


class _VisibleTextParser(HTMLParser):
    _SKIP_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.casefold() in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            value = _SPACE.sub(" ", data).strip()
            if value:
                self.parts.append(value)


def normalize_material_surface(value: str) -> str:
    """Normalize whitespace and edge punctuation without semantic rewriting."""

    return _SPACE.sub(" ", value.strip(" \t\r\n,;:()[]{}|/"))


def extract_visible_html_text(value: str) -> str:
    """Extract deterministic visible HTML text without executing page code."""

    parser = _VisibleTextParser()
    parser.feed(value)
    parser.close()
    return "\n".join(parser.parts)


def classify_material_document(header: bytes, suffix: str) -> str:
    """Classify a material from its header and registered filename suffix."""

    if header.startswith(b"%PDF-"):
        return "pdf"
    normalized = header.lstrip().lower()
    html_suffix = suffix.casefold() in {".htm", ".html"}
    regular_html = b"<!doctype html" in normalized or b"<html" in normalized
    sec_exhibit = normalized.startswith(b"<document>") and b"<type>ex-99.1" in normalized
    return "html" if html_suffix and (regular_html or sec_exhibit) else "unsupported"


def extract_candidate_surfaces(text: str) -> list[dict[str, str]]:
    """Return deterministic acronym/alphanumeric/title-case candidate surfaces."""

    found: dict[str, dict[str, str]] = {}
    for kind, pattern in (("acronym_or_alphanumeric", _MIXED_OR_ACRONYM), ("title_case", _TITLE_SEQUENCE)):
        for match in pattern.finditer(text):
            surface = normalize_material_surface(match.group(0))
            key = surface.casefold()
            if len(surface) < 2 or key in _GENERIC:
                continue
            if key not in found:
                found[key] = {"surface": surface, "kind": kind}
    return [found[key] for key in sorted(found)]
