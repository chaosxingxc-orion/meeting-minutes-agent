"""NXT (Nite XML Toolkit) stand-off annotation reader.

AMI Meeting Corpus manual annotations (release 1.6.2) and ICSI's NXT release
are both stand-off XML in this family: a per-speaker `words` layer carries
the transcript with timing; every other layer (segments, dialogue acts,
topics, summaries) attaches to word ranges via `nite:child`/`nite:pointer`
hrefs of the form ``filename.xml#id(x)`` or ``filename.xml#id(x)..id(y)``,
rather than embedding text or times itself.

Module map:

- ``pointers``: parses the href pointer *syntax* (pure string handling).
- ``idseq``: resolves an ``id(x)..id(y)`` range against one parsed file's
  element order (document position, not string parsing of the id).
- ``layout``: corpus-specific directory/filename conventions behind one
  small config object, so ICSI reuse only needs a new ``CorpusLayout``.
- ``models``: the raw (per-file) and resolved (cross-file) record shapes.
- ``parsers``: one function per NXT file kind, each returning the raw model
  for that file only (no cross-file resolution).
- ``corpus``: ``NxtCorpus`` -- discovers which meetings have which layers
  across an annotation root, and maps a bare href filename to its path.
- ``resolver``: ``MeetingResolver`` -- joins the layers for one meeting into
  transcript / minutes / evidence-link / topic structures, recording any
  pointer that fails to resolve as an ``OrphanPointer`` diagnostic instead
  of raising.
"""

from __future__ import annotations
