"""High-level per-meeting resolution.

``MeetingResolver`` joins the words / segments / dialogue-act / topic /
abstractive / extractive+summlink layers for ONE meeting into a
:class:`~.models.ResolvedMeeting`: a resolved transcript (segment-level and
dialogue-act-level), the minutes structure, evidence links from each linked
minutes sentence back to its supporting dialogue act(s) and word span, and a
resolved topic tree.

Any pointer that fails to resolve (referenced file missing on disk, or an id
not found inside it) is recorded as an :class:`~.models.OrphanPointer`
diagnostic rather than raising. That keeps the pipeline usable on a corpus
with isolated gaps elsewhere, while still letting a caller assert "zero
orphan pointers" as a checked fact about the specific meetings it resolves.
"""

from __future__ import annotations

from typing import Sequence

from .corpus import NxtCorpus
from .idseq import IdSequence
from .models import (
    EvidenceLink,
    MinutesStructure,
    OrphanPointer,
    ResolvedMeeting,
    Topic,
    TopicNode,
    Utterance,
    Word,
)
from .parsers import (
    parse_abssumm,
    parse_dialogue_acts,
    parse_segments,
    parse_summlink,
    parse_topics,
    parse_words,
)
from .pointers import NitePointer

_WordStore = tuple[tuple[Word, ...], IdSequence]
_DaIdStore = tuple[tuple[str, ...], IdSequence]


class MeetingResolver:
    def __init__(self, corpus: NxtCorpus, meeting_id: str):
        self.corpus = corpus
        self.meeting_id = meeting_id
        self._word_stores: dict[str, _WordStore | None] = {}
        self._da_id_stores: dict[str, _DaIdStore | None] = {}
        self._orphans: list[OrphanPointer] = []
        self._da_utterances: tuple[Utterance, ...] | None = None
        self._da_index: dict[str, Utterance] = {}
        self._minutes: MinutesStructure | None = None
        self._minutes_loaded = False

    # -- shared helpers -----------------------------------------------

    def _agents(self) -> list[str]:
        layers = self.corpus.discover_meetings().get(self.meeting_id)
        return sorted(layers.agents) if layers else []

    def _word_store(self, filename: str) -> _WordStore | None:
        if filename not in self._word_stores:
            path = self.corpus.path_for(filename)
            if not path.exists():
                self._word_stores[filename] = None
            else:
                words = tuple(parse_words(path))
                self._word_stores[filename] = (words, IdSequence(w.id for w in words))
        return self._word_stores[filename]

    def _expand_words(self, pointer: NitePointer, source_file: str, source_id: str) -> tuple[Word, ...]:
        store = self._word_store(pointer.filename)
        if store is None:
            self._orphans.append(
                OrphanPointer(source_file, source_id, pointer.raw, "referenced words file not found")
            )
            return ()
        words, index = store
        expansion = index.expand(pointer.start_id, pointer.end_id)
        if expansion.missing_ids:
            for missing in expansion.missing_ids:
                self._orphans.append(
                    OrphanPointer(source_file, source_id, pointer.raw, f"word id not found: {missing}")
                )
            return ()
        return tuple(words[i] for i in expansion.indices)

    @staticmethod
    def _reconstruct_text(words: Sequence[Word]) -> str:
        parts: list[str] = []
        for w in words:
            if w.kind != "w" or not w.text:
                continue
            if w.punc and parts:
                parts[-1] = parts[-1] + w.text
            else:
                parts.append(w.text)
        return " ".join(parts)

    @staticmethod
    def _span(words: Sequence[Word]) -> tuple[float | None, float | None]:
        starts = [w.start for w in words if w.start is not None]
        ends = [w.end for w in words if w.end is not None]
        return (min(starts) if starts else None, max(ends) if ends else None)

    # -- layer resolvers -------------------------------------------------

    def resolve_segments(self) -> tuple[Utterance, ...]:
        """Segment-level transcript: one utterance per raw transcription
        segment, speaker-attributed, using the segment's own
        ``transcriber_start``/``transcriber_end`` when present and falling
        back to its word span otherwise."""

        utterances: list[Utterance] = []
        for agent in self._agents():
            filename = f"{self.meeting_id}.{agent}.segments.xml"
            path = self.corpus.path_for(filename)
            if not path.exists():
                continue
            for seg in parse_segments(path):
                words: list[Word] = []
                for pointer in seg.word_pointers:
                    words.extend(self._expand_words(pointer, filename, seg.id))
                span_start, span_end = self._span(words)
                utterances.append(
                    Utterance(
                        id=seg.id,
                        speaker=agent,
                        start=seg.start if seg.start is not None else span_start,
                        end=seg.end if seg.end is not None else span_end,
                        text=self._reconstruct_text(words),
                        word_ids=tuple(w.id for w in words),
                        meta={"channel": seg.channel} if seg.channel is not None else {},
                    )
                )
        utterances.sort(key=lambda u: (u.start if u.start is not None else float("inf")))
        return tuple(utterances)

    def resolve_dialogue_acts(self) -> tuple[Utterance, ...]:
        """Dialogue-act-level transcript. Cached: also builds the
        ``da_id -> Utterance`` index that :meth:`resolve_evidence_links`
        needs, so it is safe (and cheap) to call this before or via that
        method without re-parsing."""

        if self._da_utterances is not None:
            return self._da_utterances

        utterances: list[Utterance] = []
        index: dict[str, Utterance] = {}
        for agent in self._agents():
            filename = f"{self.meeting_id}.{agent}.dialog-act.xml"
            path = self.corpus.path_for(filename)
            if not path.exists():
                continue
            for da in parse_dialogue_acts(path):
                words: list[Word] = []
                for pointer in da.word_pointers:
                    words.extend(self._expand_words(pointer, filename, da.id))
                start, end = self._span(words)
                utt = Utterance(
                    id=da.id,
                    speaker=agent,
                    start=start,
                    end=end,
                    text=self._reconstruct_text(words),
                    word_ids=tuple(w.id for w in words),
                    meta={"da_type_href": da.da_type_href} if da.da_type_href else {},
                )
                utterances.append(utt)
                index[da.id] = utt

        utterances.sort(key=lambda u: (u.start if u.start is not None else float("inf")))
        self._da_utterances = tuple(utterances)
        self._da_index = index
        return self._da_utterances

    def resolve_minutes(self) -> MinutesStructure | None:
        if not self._minutes_loaded:
            layers = self.corpus.discover_meetings().get(self.meeting_id)
            if layers is not None and layers.has_abstractive:
                filename = f"{self.meeting_id}.abssumm.xml"
                path = self.corpus.path_for(filename)
                if path.exists():
                    self._minutes = parse_abssumm(self.meeting_id, path)
                else:
                    self._orphans.append(
                        OrphanPointer(filename, self.meeting_id, "", "abstractive layer listed but file not found")
                    )
            self._minutes_loaded = True
        return self._minutes

    def _da_id_store(self, filename: str) -> _DaIdStore | None:
        if filename not in self._da_id_stores:
            path = self.corpus.path_for(filename)
            if not path.exists():
                self._da_id_stores[filename] = None
            else:
                das = parse_dialogue_acts(path)
                ids = tuple(d.id for d in das)
                self._da_id_stores[filename] = (ids, IdSequence(ids))
        return self._da_id_stores[filename]

    def _resolve_da_pointer(self, pointer: NitePointer, source_file: str, source_id: str) -> tuple[str, ...]:
        store = self._da_id_store(pointer.filename)
        if store is None:
            self._orphans.append(
                OrphanPointer(source_file, source_id, pointer.raw, "referenced dialog-act file not found")
            )
            return ()
        ids, index = store
        expansion = index.expand(pointer.start_id, pointer.end_id)
        if expansion.missing_ids:
            for missing in expansion.missing_ids:
                self._orphans.append(
                    OrphanPointer(source_file, source_id, pointer.raw, f"dialogue act id not found: {missing}")
                )
            return ()
        return tuple(ids[i] for i in expansion.indices)

    def resolve_evidence_links(self) -> tuple[EvidenceLink, ...]:
        """Each ``summlink`` entry resolved to a full evidence link: the
        abstractive minutes sentence it names, and the extractive dialogue
        act(s) (and their word span) that support it."""

        layers = self.corpus.discover_meetings().get(self.meeting_id)
        if layers is None or not (layers.has_extractive and layers.has_summlink):
            return ()

        self.resolve_dialogue_acts()  # populates self._da_index
        minutes = self.resolve_minutes()
        sentence_index = {s.id: s for s in (minutes.all_sentences() if minutes is not None else ())}

        filename = f"{self.meeting_id}.summlink.xml"
        path = self.corpus.path_for(filename)
        if not path.exists():
            self._orphans.append(
                OrphanPointer(filename, self.meeting_id, "", "summlink layer listed but file not found")
            )
            return ()

        links: list[EvidenceLink] = []
        for link in parse_summlink(path):
            if link.extractive is None or link.abstractive is None:
                self._orphans.append(
                    OrphanPointer(filename, link.id, "", "summlink entry missing extractive or abstractive pointer")
                )
                continue

            da_ids = self._resolve_da_pointer(link.extractive, filename, link.id)
            if not da_ids:
                continue
            utts = [self._da_index[d] for d in da_ids if d in self._da_index]
            for d in da_ids:
                if d not in self._da_index:
                    self._orphans.append(
                        OrphanPointer(filename, link.id, link.extractive.raw, f"dialogue act id not found: {d}")
                    )
            if not utts:
                continue

            sentence = sentence_index.get(link.abstractive.start_id)
            if sentence is None:
                self._orphans.append(
                    OrphanPointer(
                        filename,
                        link.id,
                        link.abstractive.raw,
                        f"abstractive sentence id not found: {link.abstractive.start_id}",
                    )
                )
                continue

            starts = [u.start for u in utts if u.start is not None]
            ends = [u.end for u in utts if u.end is not None]
            speakers = sorted({u.speaker for u in utts})
            links.append(
                EvidenceLink(
                    id=link.id,
                    sentence_id=sentence.id,
                    section=sentence.section,
                    sentence_text=sentence.text,
                    da_ids=tuple(u.id for u in utts),
                    speaker=speakers[0] if len(speakers) == 1 else "|".join(speakers),
                    start=min(starts) if starts else None,
                    end=max(ends) if ends else None,
                    text=" ".join(u.text for u in utts if u.text),
                    word_ids=tuple(w for u in utts for w in u.word_ids),
                )
            )
        return tuple(links)

    def resolve_topics(self) -> tuple[Topic, ...]:
        layers = self.corpus.discover_meetings().get(self.meeting_id)
        if layers is None or not layers.has_topics:
            return ()
        filename = f"{self.meeting_id}.topic.xml"
        path = self.corpus.path_for(filename)
        if not path.exists():
            self._orphans.append(
                OrphanPointer(filename, self.meeting_id, "", "topics layer listed but file not found")
            )
            return ()

        def resolve_node(node: TopicNode) -> Topic:
            words: list[Word] = []
            for pointer in node.word_pointers:
                words.extend(self._expand_words(pointer, filename, node.id))
            start, end = self._span(words)
            return Topic(
                id=node.id,
                description=node.description,
                type_href=node.type_href,
                start=start,
                end=end,
                text=self._reconstruct_text(words),
                word_ids=tuple(w.id for w in words),
                children=tuple(resolve_node(c) for c in node.children),
            )

        return tuple(resolve_node(n) for n in parse_topics(path))

    # -- top level ---------------------------------------------------

    def resolve(self) -> ResolvedMeeting:
        transcript = self.resolve_segments()
        dialogue_acts = self.resolve_dialogue_acts()
        minutes = self.resolve_minutes()
        evidence_links = self.resolve_evidence_links()
        topics = self.resolve_topics()
        return ResolvedMeeting(
            meeting_id=self.meeting_id,
            transcript=transcript,
            dialogue_acts=dialogue_acts,
            minutes=minutes,
            evidence_links=evidence_links,
            topics=topics,
            orphans=tuple(self._orphans),
        )


def resolve_meeting(corpus: NxtCorpus, meeting_id: str) -> ResolvedMeeting:
    """Convenience wrapper: ``MeetingResolver(corpus, meeting_id).resolve()``."""

    return MeetingResolver(corpus, meeting_id).resolve()
