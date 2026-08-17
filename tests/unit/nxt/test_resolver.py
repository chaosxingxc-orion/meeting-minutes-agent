from __future__ import annotations

from meeting_minutes_agent.corpora.nxt.corpus import NxtCorpus
from meeting_minutes_agent.corpora.nxt.resolver import MeetingResolver, resolve_meeting

from .fixtures import build_tiny_corpus


def _corpus(tmp_path):
    root = build_tiny_corpus(tmp_path / "ami")
    return NxtCorpus(root)


# ---------------------------------------------------------------------------
# MEET1: full stack, everything should resolve cleanly
# ---------------------------------------------------------------------------


def test_resolve_meet1_transcript_reconstructs_text_with_punctuation_and_speakers(tmp_path):
    result = resolve_meeting(_corpus(tmp_path), "MEET1")
    by_speaker = {u.speaker: u for u in result.transcript}
    assert by_speaker["A"].text == "Hello, team welcome"
    assert by_speaker["B"].text == "Thanks. Let's begin"
    # sorted by start time: A starts at 0.0, B at 2.0
    assert [u.speaker for u in result.transcript] == ["A", "B"]
    assert by_speaker["A"].start == 0.0 and by_speaker["A"].end == 1.6


def test_resolve_meet1_dialogue_acts_match_transcript_content(tmp_path):
    result = resolve_meeting(_corpus(tmp_path), "MEET1")
    assert len(result.dialogue_acts) == 2
    texts = {da.speaker: da.text for da in result.dialogue_acts}
    assert texts["A"] == "Hello, team welcome"
    assert texts["B"] == "Thanks. Let's begin"


def test_resolve_meet1_minutes_sections(tmp_path):
    result = resolve_meeting(_corpus(tmp_path), "MEET1")
    assert result.minutes is not None
    assert [s.text for s in result.minutes.sections["abstract"]] == [
        "The team greeted each other and began the meeting."
    ]
    assert [s.text for s in result.minutes.sections["decisions"]] == [
        "The team decided to start immediately."
    ]


def test_resolve_meet1_evidence_links(tmp_path):
    result = resolve_meeting(_corpus(tmp_path), "MEET1")
    assert len(result.evidence_links) == 2
    by_section = {link.section: link for link in result.evidence_links}
    abstract_link = by_section["abstract"]
    assert abstract_link.sentence_text == "The team greeted each other and began the meeting."
    assert abstract_link.speaker == "A"
    assert abstract_link.text == "Hello, team welcome"
    assert abstract_link.da_ids == ("MEET1.A.dialog-act.1",)

    decisions_link = by_section["decisions"]
    assert decisions_link.sentence_text == "The team decided to start immediately."
    assert decisions_link.speaker == "B"
    assert decisions_link.text == "Thanks. Let's begin"


def test_resolve_meet1_topics_recursive(tmp_path):
    result = resolve_meeting(_corpus(tmp_path), "MEET1")
    assert len(result.topics) == 1
    top = result.topics[0]
    assert top.description == "opening"
    assert top.text == "Hello, team welcome"
    assert len(top.children) == 1
    assert top.children[0].description == "greeting"
    assert top.children[0].text == "Thanks. Let's begin"


def test_resolve_meet1_has_zero_orphans(tmp_path):
    result = resolve_meeting(_corpus(tmp_path), "MEET1")
    assert result.orphans == ()


# ---------------------------------------------------------------------------
# MEET2: partial layer coverage
# ---------------------------------------------------------------------------


def test_resolve_meet2_partial_layers(tmp_path):
    result = resolve_meeting(_corpus(tmp_path), "MEET2")
    assert len(result.transcript) == 1
    assert result.transcript[0].text == "Okay next"
    assert result.minutes is None
    assert result.evidence_links == ()
    assert result.topics == ()
    assert result.orphans == ()


# ---------------------------------------------------------------------------
# MEET3: deliberately broken summlink -> orphan pointer expected
# ---------------------------------------------------------------------------


def test_resolve_meet3_reports_orphan_for_missing_dialogue_act_id(tmp_path):
    result = resolve_meeting(_corpus(tmp_path), "MEET3")
    assert len(result.orphans) == 1
    orphan = result.orphans[0]
    assert "MEET3.A.dialog-act.DOES_NOT_EXIST" in orphan.reason
    assert orphan.source_file == "MEET3.summlink.xml"
    # the broken link must not silently produce a bogus evidence link
    assert result.evidence_links == ()


def test_resolve_meet3_transcript_still_resolves_despite_broken_summlink(tmp_path):
    result = resolve_meeting(_corpus(tmp_path), "MEET3")
    assert len(result.transcript) == 1
    assert result.transcript[0].text == "Right so"


# ---------------------------------------------------------------------------
# MeetingResolver caching / repeated calls
# ---------------------------------------------------------------------------


def test_resolve_dialogue_acts_is_idempotent(tmp_path):
    resolver = MeetingResolver(_corpus(tmp_path), "MEET1")
    first = resolver.resolve_dialogue_acts()
    second = resolver.resolve_dialogue_acts()
    assert first == second


def test_full_resolve_matches_calling_layers_individually(tmp_path):
    corpus = _corpus(tmp_path)
    resolver = MeetingResolver(corpus, "MEET1")
    combined = resolver.resolve()

    fresh = MeetingResolver(corpus, "MEET1")
    transcript = fresh.resolve_segments()
    dialogue_acts = fresh.resolve_dialogue_acts()
    minutes = fresh.resolve_minutes()
    evidence_links = fresh.resolve_evidence_links()
    topics = fresh.resolve_topics()

    assert combined.transcript == transcript
    assert combined.dialogue_acts == dialogue_acts
    assert combined.minutes == minutes
    assert combined.evidence_links == evidence_links
    assert combined.topics == topics
