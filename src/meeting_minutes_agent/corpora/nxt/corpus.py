"""Corpus-wide discovery: which meetings exist, and which NXT layers each
one has, plus resolving a bare href filename to its path under the
annotation root. Pure filesystem/`Path.glob` work -- no XML parsing here
(that starts in :mod:`resolver`, lazily, only for meetings actually being
resolved)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from .layout import AMI_LAYOUT, CorpusLayout


@dataclass
class MeetingLayers:
    """Which layers exist for one meeting id, discovered from filenames
    alone. ``agents`` is the set of per-speaker letters seen in the words
    layer (AMI: normally A-D, occasionally +E)."""

    meeting_id: str
    agents: set[str] = field(default_factory=set)
    has_words: bool = False
    has_segments: bool = False
    has_dialogue_acts: bool = False
    has_abstractive: bool = False
    has_extractive: bool = False
    has_summlink: bool = False
    has_topics: bool = False


def _meeting_agent_pattern(suffix: str) -> re.Pattern[str]:
    return re.compile(r"^(?P<meeting>.+)\.(?P<agent>[A-Za-z])" + re.escape(suffix) + r"$")


def _meeting_only_pattern(suffix: str) -> re.Pattern[str]:
    return re.compile(r"^(?P<meeting>.+)" + re.escape(suffix) + r"$")


class NxtCorpus:
    def __init__(self, root: Path | str, layout: CorpusLayout = AMI_LAYOUT):
        self.root = Path(root)
        self.layout = layout
        self._meetings_cache: dict[str, MeetingLayers] | None = None

    def path_for(self, filename: str) -> Path:
        """Resolve a bare NXT href filename to its path under the corpus
        root, dispatching by suffix via the layout config. Falls back to
        the ontologies directory for filenames the layout does not
        recognise as a per-meeting layer file (e.g. ``da-types.xml``)."""

        subdir = self.layout.dir_for_filename(filename)
        if subdir is None:
            return self.root / self.layout.ontologies_dir / filename
        return self.root / subdir / filename

    def discover_meetings(self, *, refresh: bool = False) -> Mapping[str, MeetingLayers]:
        """Scan the corpus root once and cache the result (a full-corpus
        scan is cheap -- filenames only, no XML parsing -- but there's no
        reason to redo it for every meeting when resolving many). Pass
        ``refresh=True`` to force a re-scan (e.g. after the corpus changed
        on disk)."""

        if self._meetings_cache is None or refresh:
            self._meetings_cache = self._scan()
        return self._meetings_cache

    def _scan(self) -> dict[str, MeetingLayers]:
        meetings: dict[str, MeetingLayers] = {}

        def get(meeting_id: str) -> MeetingLayers:
            return meetings.setdefault(meeting_id, MeetingLayers(meeting_id=meeting_id))

        layout = self.layout

        words_dir = self.root / layout.words_dir
        if words_dir.is_dir():
            pattern = _meeting_agent_pattern(layout.words_suffix)
            for p in words_dir.glob(f"*{layout.words_suffix}"):
                m = pattern.match(p.name)
                if not m:
                    continue
                layers = get(m.group("meeting"))
                layers.has_words = True
                layers.agents.add(m.group("agent"))

        segments_dir = self.root / layout.segments_dir
        if segments_dir.is_dir():
            pattern = _meeting_agent_pattern(layout.segments_suffix)
            for p in segments_dir.glob(f"*{layout.segments_suffix}"):
                m = pattern.match(p.name)
                if not m:
                    continue
                get(m.group("meeting")).has_segments = True

        da_dir = self.root / layout.dialogue_acts_dir
        if da_dir.is_dir():
            pattern = _meeting_agent_pattern(layout.dialogue_act_suffix)
            for p in da_dir.glob(f"*{layout.dialogue_act_suffix}"):
                m = pattern.match(p.name)
                if not m:
                    continue
                get(m.group("meeting")).has_dialogue_acts = True

        abstractive_dir = self.root / layout.abstractive_dir
        if abstractive_dir.is_dir():
            pattern = _meeting_only_pattern(layout.abssumm_suffix)
            for p in abstractive_dir.glob(f"*{layout.abssumm_suffix}"):
                m = pattern.match(p.name)
                if not m:
                    continue
                get(m.group("meeting")).has_abstractive = True

        extractive_dir = self.root / layout.extractive_dir
        if extractive_dir.is_dir():
            extsumm_pattern = _meeting_only_pattern(layout.extsumm_suffix)
            for p in extractive_dir.glob(f"*{layout.extsumm_suffix}"):
                m = extsumm_pattern.match(p.name)
                if not m:
                    continue
                get(m.group("meeting")).has_extractive = True

            summlink_pattern = _meeting_only_pattern(layout.summlink_suffix)
            for p in extractive_dir.glob(f"*{layout.summlink_suffix}"):
                m = summlink_pattern.match(p.name)
                if not m:
                    continue
                get(m.group("meeting")).has_summlink = True

        topics_dir = self.root / layout.topics_dir
        if topics_dir.is_dir():
            pattern = _meeting_only_pattern(layout.topic_suffix)
            for p in topics_dir.glob(f"*{layout.topic_suffix}"):
                m = pattern.match(p.name)
                if not m:
                    continue
                get(m.group("meeting")).has_topics = True

        return meetings


def layer_counts(meetings: Mapping[str, MeetingLayers]) -> dict[str, int]:
    """Corpus-wide layer coverage counts, grouped the way the 2026-08-17
    local audit reports them (words+segments; abstractive; extractive+
    summlink; topics+dialogue-acts) so the two can be diffed directly."""

    values = list(meetings.values())
    return {
        "words_and_segments": sum(1 for m in values if m.has_words and m.has_segments),
        "abstractive": sum(1 for m in values if m.has_abstractive),
        "extractive_and_summlink": sum(1 for m in values if m.has_extractive and m.has_summlink),
        "topics_and_dialogue_acts": sum(1 for m in values if m.has_topics and m.has_dialogue_acts),
    }
