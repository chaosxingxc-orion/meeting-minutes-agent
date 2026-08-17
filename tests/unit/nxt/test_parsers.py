from __future__ import annotations

from pathlib import Path

from meeting_minutes_agent.corpora.nxt.parsers import (
    parse_abssumm,
    parse_dialogue_acts,
    parse_extsumm,
    parse_segments,
    parse_summlink,
    parse_topics,
    parse_words,
)

NITE_XMLNS = 'xmlns:nite="http://nite.sourceforge.net/"'


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# words
# ---------------------------------------------------------------------------


def test_parse_words_captures_text_time_and_punc(tmp_path):
    content = f"""<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>
<nite:root nite:id="M.A.words" {NITE_XMLNS}>
   <w nite:id="M.A.words0" starttime="1.0" endtime="1.5">Hello</w>
   <w nite:id="M.A.words1" starttime="1.5" endtime="1.5" punc="true">,</w>
   <w nite:id="M.A.words2" starttime="1.6" endtime="2.0">world</w>
</nite:root>
"""
    path = _write(tmp_path, "M.A.words.xml", content)
    words = parse_words(path)
    assert [w.id for w in words] == ["M.A.words0", "M.A.words1", "M.A.words2"]
    assert words[0].text == "Hello"
    assert words[0].start == 1.0 and words[0].end == 1.5
    assert words[1].punc is True
    assert words[2].text == "world"


def test_parse_words_keeps_non_lexical_tags_in_id_sequence(tmp_path):
    # disfmarker/gap/vocalsound carry no lexical text but MUST still occupy
    # an id slot -- this is the AMI surprise the resolver's range math
    # depends on.
    content = f"""<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>
<nite:root nite:id="M.A.words" {NITE_XMLNS}>
   <w nite:id="M.A.words0" starttime="1.0" endtime="1.2">um</w>
   <disfmarker nite:id="M.A.words1" starttime="1.2" endtime="1.2"/>
   <vocalsound nite:id="M.A.words2" starttime="1.2" endtime="1.4" type="laugh"/>
   <gap nite:id="M.A.words3" starttime="1.4" endtime="1.4"/>
   <w nite:id="M.A.words4" starttime="1.5" endtime="1.8">yeah</w>
</nite:root>
"""
    path = _write(tmp_path, "M.A.words.xml", content)
    words = parse_words(path)
    assert len(words) == 5
    kinds = [w.kind for w in words]
    assert kinds == ["w", "disfmarker", "vocalsound", "gap", "w"]
    assert words[1].text is None
    assert words[2].vocal_type == "laugh"
    assert words[4].text == "yeah"


# ---------------------------------------------------------------------------
# segments
# ---------------------------------------------------------------------------


def test_parse_segments_reads_times_channel_and_child_pointer(tmp_path):
    content = f"""<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>
<nite:root nite:id="M.A.segs" {NITE_XMLNS}>
   <segment nite:id="M.seg.1" channel="0" transcriber_start="1.0" transcriber_end="2.0">
      <nite:child href="M.A.words.xml#id(M.A.words0)..id(M.A.words4)"/>
   </segment>
</nite:root>
"""
    path = _write(tmp_path, "M.A.segments.xml", content)
    segments = parse_segments(path)
    assert len(segments) == 1
    seg = segments[0]
    assert seg.id == "M.seg.1"
    assert seg.channel == "0"
    assert seg.start == 1.0 and seg.end == 2.0
    assert len(seg.word_pointers) == 1
    assert seg.word_pointers[0].start_id == "M.A.words0"
    assert seg.word_pointers[0].end_id == "M.A.words4"


# ---------------------------------------------------------------------------
# dialogue acts
# ---------------------------------------------------------------------------


def test_parse_dialogue_acts_reads_type_ref_and_word_pointer(tmp_path):
    content = f"""<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>
<nite:root nite:id="M.A.dialog-act" {NITE_XMLNS}>
   <dact nite:id="M.A.dialog-act.1">
      <nite:pointer role="da-aspect" href="da-types.xml#id(ami_da_4)"/>
      <nite:child href="M.A.words.xml#id(M.A.words0)..id(M.A.words2)"/>
   </dact>
</nite:root>
"""
    path = _write(tmp_path, "M.A.dialog-act.xml", content)
    acts = parse_dialogue_acts(path)
    assert len(acts) == 1
    assert acts[0].id == "M.A.dialog-act.1"
    assert acts[0].da_type_href == "da-types.xml#id(ami_da_4)"
    assert acts[0].word_pointers[0].start_id == "M.A.words0"


# ---------------------------------------------------------------------------
# topics (recursive)
# ---------------------------------------------------------------------------


def test_parse_topics_recurses_into_subtopics(tmp_path):
    content = f"""<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>
<nite:root nite:id="M.topic" {NITE_XMLNS}>
   <topic nite:id="M.topic.1" other_description="opening">
      <nite:child href="M.A.words.xml#id(M.A.words0)..id(M.A.words2)"/>
      <topic nite:id="M.topic.1.1" other_description="greeting">
         <nite:child href="M.B.words.xml#id(M.B.words0)..id(M.B.words1)"/>
      </topic>
   </topic>
</nite:root>
"""
    path = _write(tmp_path, "M.topic.xml", content)
    topics = parse_topics(path)
    assert len(topics) == 1
    top = topics[0]
    assert top.id == "M.topic.1"
    assert top.description == "opening"
    assert len(top.word_pointers) == 1
    assert len(top.children) == 1
    assert top.children[0].id == "M.topic.1.1"
    assert top.children[0].description == "greeting"


def test_parse_topics_reads_scenario_type_pointer(tmp_path):
    content = f"""<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>
<nite:root nite:id="M.topic" {NITE_XMLNS}>
   <topic nite:id="M.topic.1" other_description="intro">
      <nite:pointer role="scenario_topic_type" href="default-topics.xml#id(top.4)"/>
      <nite:child href="M.A.words.xml#id(M.A.words0)"/>
   </topic>
</nite:root>
"""
    path = _write(tmp_path, "M.topic.xml", content)
    topics = parse_topics(path)
    assert topics[0].type_href == "default-topics.xml#id(top.4)"


# ---------------------------------------------------------------------------
# abssumm
# ---------------------------------------------------------------------------


def test_parse_abssumm_reads_sections_and_sentences(tmp_path):
    content = f"""<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>
<nite:root {NITE_XMLNS}>
<abstract nite:id="M.abstract.1">
<sentence nite:id="M.s.1">The team greeted each other.</sentence>
</abstract>
<decisions nite:id="M.decisions.1">
<sentence nite:id="M.s.2">They decided to start.</sentence>
</decisions>
</nite:root>
"""
    path = _write(tmp_path, "M.abssumm.xml", content)
    minutes = parse_abssumm("M", path)
    assert minutes.meeting_id == "M"
    assert [s.text for s in minutes.sections["abstract"]] == ["The team greeted each other."]
    assert [s.text for s in minutes.sections["decisions"]] == ["They decided to start."]
    assert minutes.sections["actions"] == ()
    assert minutes.sections["problems"] == ()
    assert len(minutes.all_sentences()) == 2


# ---------------------------------------------------------------------------
# extsumm / summlink
# ---------------------------------------------------------------------------


def test_parse_extsumm_pools_child_pointers(tmp_path):
    content = f"""<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>
<nite:root nite:id="M.extsumm" {NITE_XMLNS}>
   <extsumm nite:id="M.extsumm.1">
      <nite:child href="M.A.dialog-act.xml#id(M.A.dialog-act.1)"/>
      <nite:child href="M.B.dialog-act.xml#id(M.B.dialog-act.1)"/>
   </extsumm>
</nite:root>
"""
    path = _write(tmp_path, "M.extsumm.xml", content)
    pointers = parse_extsumm(path)
    assert [p.start_id for p in pointers] == ["M.A.dialog-act.1", "M.B.dialog-act.1"]


def test_parse_summlink_pairs_extractive_and_abstractive(tmp_path):
    content = f"""<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>
<nite:root nite:id="M.summlink" {NITE_XMLNS}>
   <summlink nite:id="M.summlink.1">
      <nite:pointer role="extractive" href="M.A.dialog-act.xml#id(M.A.dialog-act.1)"/>
      <nite:pointer role="abstractive" href="M.abssumm.xml#id(M.s.1)"/>
   </summlink>
</nite:root>
"""
    path = _write(tmp_path, "M.summlink.xml", content)
    links = parse_summlink(path)
    assert len(links) == 1
    assert links[0].extractive.filename == "M.A.dialog-act.xml"
    assert links[0].extractive.start_id == "M.A.dialog-act.1"
    assert links[0].abstractive.filename == "M.abssumm.xml"
    assert links[0].abstractive.start_id == "M.s.1"
