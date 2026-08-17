"""Builds a tiny synthetic NXT annotation tree (three toy meetings) under a
tmp_path, mirroring the AMI directory/filename conventions exactly enough to
exercise discovery and resolution end to end -- WITHOUT ever touching the
real 205 MB annotation release. See CLAUDE.md / the E2 task brief: unit
tests use tiny synthetic fixtures only.

Three meetings, deliberately shaped to cover distinct cases:

- MEET1: full layer stack (words, segments, dialogue acts, abstractive,
  extractive+summlink, topics with one nested subtopic). Every pointer
  resolves -- zero orphans expected.
- MEET2: words+segments+dialogue-acts only (no abstractive/extractive/
  topics) -- exercises partial layer coverage; minutes is None, evidence
  links are empty, still zero orphans.
- MEET3: same stack as MEET1 minus topics, but its summlink deliberately
  references a dialogue act id that does not exist -- exercises orphan
  detection.
"""

from __future__ import annotations

from pathlib import Path

NITE_XMLNS = 'xmlns:nite="http://nite.sourceforge.net/"'
_XML_HEADER = '<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>\n'


def _write(root: Path, subdir: str, name: str, content: str) -> None:
    path = root / subdir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_XML_HEADER + content, encoding="utf-8")


def build_tiny_corpus(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)

    # -- MEET1: full stack, clean -------------------------------------

    _write(
        root,
        "words",
        "MEET1.A.words.xml",
        f"""<nite:root nite:id="MEET1.A.words" {NITE_XMLNS}>
   <w nite:id="MEET1.A.words0" starttime="0.0" endtime="0.5">Hello</w>
   <w nite:id="MEET1.A.words1" starttime="0.5" endtime="0.5" punc="true">,</w>
   <w nite:id="MEET1.A.words2" starttime="0.6" endtime="1.0">team</w>
   <disfmarker nite:id="MEET1.A.words3" starttime="1.0" endtime="1.0"/>
   <w nite:id="MEET1.A.words4" starttime="1.2" endtime="1.6">welcome</w>
</nite:root>
""",
    )
    _write(
        root,
        "words",
        "MEET1.B.words.xml",
        f"""<nite:root nite:id="MEET1.B.words" {NITE_XMLNS}>
   <w nite:id="MEET1.B.words0" starttime="2.0" endtime="2.4">Thanks</w>
   <w nite:id="MEET1.B.words1" starttime="2.4" endtime="2.4" punc="true">.</w>
   <w nite:id="MEET1.B.words2" starttime="2.5" endtime="3.0">Let's</w>
   <w nite:id="MEET1.B.words3" starttime="3.0" endtime="3.4">begin</w>
</nite:root>
""",
    )
    _write(
        root,
        "segments",
        "MEET1.A.segments.xml",
        f"""<nite:root nite:id="MEET1.A.segs" {NITE_XMLNS}>
   <segment nite:id="MEET1.A.seg.1" channel="0" transcriber_start="0.0" transcriber_end="1.6">
      <nite:child href="MEET1.A.words.xml#id(MEET1.A.words0)..id(MEET1.A.words4)"/>
   </segment>
</nite:root>
""",
    )
    _write(
        root,
        "segments",
        "MEET1.B.segments.xml",
        f"""<nite:root nite:id="MEET1.B.segs" {NITE_XMLNS}>
   <segment nite:id="MEET1.B.seg.1" channel="1" transcriber_start="2.0" transcriber_end="3.4">
      <nite:child href="MEET1.B.words.xml#id(MEET1.B.words0)..id(MEET1.B.words3)"/>
   </segment>
</nite:root>
""",
    )
    _write(
        root,
        "dialogueActs",
        "MEET1.A.dialog-act.xml",
        f"""<nite:root nite:id="MEET1.A.dialog-act" {NITE_XMLNS}>
   <dact nite:id="MEET1.A.dialog-act.1">
      <nite:pointer role="da-aspect" href="da-types.xml#id(ami_da_4)"/>
      <nite:child href="MEET1.A.words.xml#id(MEET1.A.words0)..id(MEET1.A.words4)"/>
   </dact>
</nite:root>
""",
    )
    _write(
        root,
        "dialogueActs",
        "MEET1.B.dialog-act.xml",
        f"""<nite:root nite:id="MEET1.B.dialog-act" {NITE_XMLNS}>
   <dact nite:id="MEET1.B.dialog-act.1">
      <nite:pointer role="da-aspect" href="da-types.xml#id(ami_da_4)"/>
      <nite:child href="MEET1.B.words.xml#id(MEET1.B.words0)..id(MEET1.B.words3)"/>
   </dact>
</nite:root>
""",
    )
    _write(
        root,
        "abstractive",
        "MEET1.abssumm.xml",
        f"""<nite:root {NITE_XMLNS}>
<abstract nite:id="MEET1.abstract.1">
<sentence nite:id="MEET1.s.1">The team greeted each other and began the meeting.</sentence>
</abstract>
<decisions nite:id="MEET1.decisions.1">
<sentence nite:id="MEET1.s.2">The team decided to start immediately.</sentence>
</decisions>
</nite:root>
""",
    )
    _write(
        root,
        "extractive",
        "MEET1.extsumm.xml",
        f"""<nite:root nite:id="MEET1.extsumm" {NITE_XMLNS}>
   <extsumm nite:id="MEET1.extsumm.1">
      <nite:child href="MEET1.A.dialog-act.xml#id(MEET1.A.dialog-act.1)"/>
      <nite:child href="MEET1.B.dialog-act.xml#id(MEET1.B.dialog-act.1)"/>
   </extsumm>
</nite:root>
""",
    )
    _write(
        root,
        "extractive",
        "MEET1.summlink.xml",
        f"""<nite:root nite:id="MEET1.summlink" {NITE_XMLNS}>
   <summlink nite:id="MEET1.summlink.1">
      <nite:pointer role="extractive" href="MEET1.A.dialog-act.xml#id(MEET1.A.dialog-act.1)"/>
      <nite:pointer role="abstractive" href="MEET1.abssumm.xml#id(MEET1.s.1)"/>
   </summlink>
   <summlink nite:id="MEET1.summlink.2">
      <nite:pointer role="extractive" href="MEET1.B.dialog-act.xml#id(MEET1.B.dialog-act.1)"/>
      <nite:pointer role="abstractive" href="MEET1.abssumm.xml#id(MEET1.s.2)"/>
   </summlink>
</nite:root>
""",
    )
    _write(
        root,
        "topics",
        "MEET1.topic.xml",
        f"""<nite:root nite:id="MEET1.topic" {NITE_XMLNS}>
   <topic nite:id="MEET1.topic.1" other_description="opening">
      <nite:child href="MEET1.A.words.xml#id(MEET1.A.words0)..id(MEET1.A.words4)"/>
      <topic nite:id="MEET1.topic.1.1" other_description="greeting">
         <nite:child href="MEET1.B.words.xml#id(MEET1.B.words0)..id(MEET1.B.words3)"/>
      </topic>
   </topic>
</nite:root>
""",
    )

    # -- MEET2: words + segments + dialogue acts only ------------------

    _write(
        root,
        "words",
        "MEET2.A.words.xml",
        f"""<nite:root nite:id="MEET2.A.words" {NITE_XMLNS}>
   <w nite:id="MEET2.A.words0" starttime="0.0" endtime="0.4">Okay</w>
   <w nite:id="MEET2.A.words1" starttime="0.5" endtime="0.9">next</w>
</nite:root>
""",
    )
    _write(
        root,
        "segments",
        "MEET2.A.segments.xml",
        f"""<nite:root nite:id="MEET2.A.segs" {NITE_XMLNS}>
   <segment nite:id="MEET2.A.seg.1" channel="0" transcriber_start="0.0" transcriber_end="0.9">
      <nite:child href="MEET2.A.words.xml#id(MEET2.A.words0)..id(MEET2.A.words1)"/>
   </segment>
</nite:root>
""",
    )
    _write(
        root,
        "dialogueActs",
        "MEET2.A.dialog-act.xml",
        f"""<nite:root nite:id="MEET2.A.dialog-act" {NITE_XMLNS}>
   <dact nite:id="MEET2.A.dialog-act.1">
      <nite:pointer role="da-aspect" href="da-types.xml#id(ami_da_4)"/>
      <nite:child href="MEET2.A.words.xml#id(MEET2.A.words0)..id(MEET2.A.words1)"/>
   </dact>
</nite:root>
""",
    )

    # -- MEET3: full stack, but a deliberately broken summlink ----------

    _write(
        root,
        "words",
        "MEET3.A.words.xml",
        f"""<nite:root nite:id="MEET3.A.words" {NITE_XMLNS}>
   <w nite:id="MEET3.A.words0" starttime="0.0" endtime="0.4">Right</w>
   <w nite:id="MEET3.A.words1" starttime="0.5" endtime="0.9">so</w>
</nite:root>
""",
    )
    _write(
        root,
        "segments",
        "MEET3.A.segments.xml",
        f"""<nite:root nite:id="MEET3.A.segs" {NITE_XMLNS}>
   <segment nite:id="MEET3.A.seg.1" channel="0" transcriber_start="0.0" transcriber_end="0.9">
      <nite:child href="MEET3.A.words.xml#id(MEET3.A.words0)..id(MEET3.A.words1)"/>
   </segment>
</nite:root>
""",
    )
    _write(
        root,
        "dialogueActs",
        "MEET3.A.dialog-act.xml",
        f"""<nite:root nite:id="MEET3.A.dialog-act" {NITE_XMLNS}>
   <dact nite:id="MEET3.A.dialog-act.1">
      <nite:pointer role="da-aspect" href="da-types.xml#id(ami_da_4)"/>
      <nite:child href="MEET3.A.words.xml#id(MEET3.A.words0)..id(MEET3.A.words1)"/>
   </dact>
</nite:root>
""",
    )
    _write(
        root,
        "abstractive",
        "MEET3.abssumm.xml",
        f"""<nite:root {NITE_XMLNS}>
<abstract nite:id="MEET3.abstract.1">
<sentence nite:id="MEET3.s.1">Something was said.</sentence>
</abstract>
</nite:root>
""",
    )
    _write(
        root,
        "extractive",
        "MEET3.extsumm.xml",
        f"""<nite:root nite:id="MEET3.extsumm" {NITE_XMLNS}>
   <extsumm nite:id="MEET3.extsumm.1">
      <nite:child href="MEET3.A.dialog-act.xml#id(MEET3.A.dialog-act.1)"/>
   </extsumm>
</nite:root>
""",
    )
    _write(
        root,
        "extractive",
        "MEET3.summlink.xml",
        f"""<nite:root nite:id="MEET3.summlink" {NITE_XMLNS}>
   <summlink nite:id="MEET3.summlink.1">
      <nite:pointer role="extractive" href="MEET3.A.dialog-act.xml#id(MEET3.A.dialog-act.DOES_NOT_EXIST)"/>
      <nite:pointer role="abstractive" href="MEET3.abssumm.xml#id(MEET3.s.1)"/>
   </summlink>
</nite:root>
""",
    )

    return root
