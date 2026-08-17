"""One parse function per NXT file kind. Each function reads a single file
and returns the RAW model for that layer only -- pointers are parsed (see
:mod:`pointers`) but not expanded against any other file; that cross-file
join is :mod:`resolver`'s job.

Uses stdlib :mod:`xml.etree.ElementTree` only (no lxml dependency). Every
id-bearing child element is captured in document order regardless of
whether its tag is one this reader specifically understands -- skipping an
unrecognised tag would shift the position-based id-range math in
:mod:`idseq` for every element after it, silently corrupting range
expansion. See ``parse_words`` for where this matters most (AMI mixes
``<disfmarker>``, ``<gap>``, ``<vocalsound>`` into the word id sequence
alongside ``<w>``).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .models import (
    DialogueActRaw,
    MinutesSentence,
    MinutesStructure,
    SegmentRaw,
    SummlinkRaw,
    TopicNode,
    Word,
)
from .pointers import NitePointer, parse_pointer

NITE_NS = "http://nite.sourceforge.net/"
NITE_ID = f"{{{NITE_NS}}}id"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _float_or_none(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _child_pointers(elem: ET.Element) -> tuple[NitePointer, ...]:
    """``<nite:child href="...">`` elements directly under ``elem``,
    parsed into pointers, in document order. A ``child`` with no (or an
    unparseable) href is skipped rather than raising -- callers that care
    about that discrepancy see it show up as a shorter word span, and the
    orphan-pointer machinery in ``resolver`` is what's meant to surface
    real corpus problems, not this low-level parse step."""

    pointers: list[NitePointer] = []
    for child in elem:
        if _local(child.tag) != "child":
            continue
        href = child.get("href")
        if not href:
            continue
        pointers.append(parse_pointer(href))
    return tuple(pointers)


# ---------------------------------------------------------------------------
# words.xml
# ---------------------------------------------------------------------------


def parse_words(path: Path) -> list[Word]:
    tree = ET.parse(path)
    words: list[Word] = []
    for elem in tree.getroot():
        identifier = elem.get(NITE_ID)
        if identifier is None:
            continue  # not id-bearing; cannot be a range endpoint or member
        tag = _local(elem.tag)
        text = elem.text.strip() if (tag == "w" and elem.text and elem.text.strip()) else None
        words.append(
            Word(
                id=identifier,
                kind=tag,
                text=text,
                start=_float_or_none(elem.get("starttime")),
                end=_float_or_none(elem.get("endtime")),
                punc=elem.get("punc") == "true",
                vocal_type=elem.get("type") if tag != "w" else None,
            )
        )
    return words


# ---------------------------------------------------------------------------
# segments.xml
# ---------------------------------------------------------------------------


def parse_segments(path: Path) -> list[SegmentRaw]:
    tree = ET.parse(path)
    segments: list[SegmentRaw] = []
    for elem in tree.getroot():
        if _local(elem.tag) != "segment":
            continue
        identifier = elem.get(NITE_ID)
        if identifier is None:
            continue
        segments.append(
            SegmentRaw(
                id=identifier,
                channel=elem.get("channel"),
                start=_float_or_none(elem.get("transcriber_start")),
                end=_float_or_none(elem.get("transcriber_end")),
                word_pointers=_child_pointers(elem),
            )
        )
    return segments


# ---------------------------------------------------------------------------
# dialog-act.xml
# ---------------------------------------------------------------------------


def parse_dialogue_acts(path: Path) -> list[DialogueActRaw]:
    tree = ET.parse(path)
    acts: list[DialogueActRaw] = []
    for elem in tree.getroot():
        if _local(elem.tag) != "dact":
            continue
        identifier = elem.get(NITE_ID)
        if identifier is None:
            continue
        da_type_href: str | None = None
        for child in elem:
            if _local(child.tag) == "pointer" and child.get("role") == "da-aspect":
                da_type_href = child.get("href")
                break
        acts.append(
            DialogueActRaw(
                id=identifier,
                da_type_href=da_type_href,
                word_pointers=_child_pointers(elem),
            )
        )
    return acts


# ---------------------------------------------------------------------------
# topic.xml (recursive: topics nest subtopics)
# ---------------------------------------------------------------------------


def parse_topics(path: Path) -> list[TopicNode]:
    tree = ET.parse(path)

    def build(elem: ET.Element) -> TopicNode:
        identifier = elem.get(NITE_ID)
        type_href: str | None = None
        children: list[TopicNode] = []
        for child in elem:
            ctag = _local(child.tag)
            if ctag == "pointer" and child.get("role") == "scenario_topic_type":
                type_href = child.get("href")
            elif ctag == "topic":
                children.append(build(child))
        return TopicNode(
            id=identifier or "",
            description=elem.get("other_description"),
            type_href=type_href,
            word_pointers=_child_pointers(elem),
            children=tuple(children),
        )

    return [build(elem) for elem in tree.getroot() if _local(elem.tag) == "topic"]


# ---------------------------------------------------------------------------
# abssumm.xml (authored text, no pointers)
# ---------------------------------------------------------------------------

_SECTION_TAGS = ("abstract", "actions", "decisions", "problems")


def parse_abssumm(meeting_id: str, path: Path) -> MinutesStructure:
    tree = ET.parse(path)
    sections: dict[str, list[MinutesSentence]] = {name: [] for name in _SECTION_TAGS}
    for elem in tree.getroot():
        tag = _local(elem.tag)
        if tag not in sections:
            continue
        for sentence in elem:
            if _local(sentence.tag) != "sentence":
                continue
            identifier = sentence.get(NITE_ID)
            if identifier is None:
                continue
            text = "".join(sentence.itertext()).strip()
            sections[tag].append(MinutesSentence(id=identifier, section=tag, text=text))
    return MinutesStructure(meeting_id=meeting_id, sections={k: tuple(v) for k, v in sections.items()})


# ---------------------------------------------------------------------------
# extsumm.xml
# ---------------------------------------------------------------------------


def parse_extsumm(path: Path) -> list[NitePointer]:
    """AMI's extsumm files hold exactly one ``<extsumm>`` group (observed:
    137/137), but this does not assume that -- pointers from every group in
    the file are pooled together."""

    tree = ET.parse(path)
    pointers: list[NitePointer] = []
    for group in tree.getroot():
        if _local(group.tag) != "extsumm":
            continue
        pointers.extend(_child_pointers(group))
    return pointers


# ---------------------------------------------------------------------------
# summlink.xml
# ---------------------------------------------------------------------------


def parse_summlink(path: Path) -> list[SummlinkRaw]:
    tree = ET.parse(path)
    links: list[SummlinkRaw] = []
    for elem in tree.getroot():
        if _local(elem.tag) != "summlink":
            continue
        identifier = elem.get(NITE_ID)
        if identifier is None:
            continue
        extractive: NitePointer | None = None
        abstractive: NitePointer | None = None
        for child in elem:
            if _local(child.tag) != "pointer":
                continue
            href = child.get("href")
            if not href:
                continue
            pointer = parse_pointer(href)
            role = child.get("role")
            if role == "extractive":
                extractive = pointer
            elif role == "abstractive":
                abstractive = pointer
        links.append(SummlinkRaw(id=identifier, extractive=extractive, abstractive=abstractive))
    return links
