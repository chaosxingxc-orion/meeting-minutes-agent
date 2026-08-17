"""Corpus-specific directory/filename conventions for an NXT stand-off
release, kept behind one small config object (per E2's design brief: "keep
corpus-specific bits behind a thin config") so a second NXT-family corpus
(ICSI) can plug in its own layout without touching parsers/corpus/resolver.

AMI's manual annotation release lays out each layer in its own top-level
directory, with a bare filename (no directory) inside every href -- e.g.
``extractive/ES2002a.summlink.xml`` contains
``<nite:pointer href="ES2002a.B.dialog-act.xml#id(...)"/>`` with no
``dialogueActs/`` prefix, even though that file actually lives in
``dialogueActs/``. Filenames are unique across the whole release (a given
``<meeting>.<agent>.dialog-act.xml`` exists only under ``dialogueActs/``),
so resolving a bare href filename to a path is a lookup by filename suffix,
not a relative-path join.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CorpusLayout:
    name: str

    words_dir: str = "words"
    segments_dir: str = "segments"
    dialogue_acts_dir: str = "dialogueActs"
    abstractive_dir: str = "abstractive"
    extractive_dir: str = "extractive"
    topics_dir: str = "topics"
    ontologies_dir: str = "ontologies"

    words_suffix: str = ".words.xml"
    segments_suffix: str = ".segments.xml"
    dialogue_act_suffix: str = ".dialog-act.xml"
    abssumm_suffix: str = ".abssumm.xml"
    extsumm_suffix: str = ".extsumm.xml"
    summlink_suffix: str = ".summlink.xml"
    topic_suffix: str = ".topic.xml"

    def _suffix_to_dir(self) -> tuple[tuple[str, str], ...]:
        return (
            (self.dialogue_act_suffix, self.dialogue_acts_dir),
            (self.summlink_suffix, self.extractive_dir),
            (self.extsumm_suffix, self.extractive_dir),
            (self.abssumm_suffix, self.abstractive_dir),
            (self.segments_suffix, self.segments_dir),
            (self.topic_suffix, self.topics_dir),
            (self.words_suffix, self.words_dir),
        )

    def dir_for_filename(self, filename: str) -> str | None:
        """Dispatch a bare NXT href filename (e.g.
        ``ES2002a.B.dialog-act.xml``) to the subdirectory that holds it, by
        suffix. Returns None for a filename this layout does not recognise
        as a per-meeting layer file -- e.g. a shared-ontology reference such
        as ``da-types.xml``, which callers resolve via ``ontologies_dir``
        directly when (and if) they need the ontology gloss, not through
        this per-meeting dispatch."""

        for suffix, subdir in self._suffix_to_dir():
            if filename.endswith(suffix):
                return subdir
        return None


AMI_LAYOUT = CorpusLayout(name="ami")
