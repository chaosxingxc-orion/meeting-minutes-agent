from __future__ import annotations

from meeting_minutes_agent.corpora.nxt.corpus import NxtCorpus, layer_counts

from .fixtures import build_tiny_corpus


def test_discover_meetings_finds_all_three(tmp_path):
    root = build_tiny_corpus(tmp_path / "ami")
    corpus = NxtCorpus(root)
    meetings = corpus.discover_meetings()
    assert set(meetings) == {"MEET1", "MEET2", "MEET3"}


def test_discover_meetings_layer_flags_meet1_full_stack(tmp_path):
    root = build_tiny_corpus(tmp_path / "ami")
    corpus = NxtCorpus(root)
    m1 = corpus.discover_meetings()["MEET1"]
    assert m1.agents == {"A", "B"}
    assert m1.has_words
    assert m1.has_segments
    assert m1.has_dialogue_acts
    assert m1.has_abstractive
    assert m1.has_extractive
    assert m1.has_summlink
    assert m1.has_topics


def test_discover_meetings_layer_flags_meet2_partial(tmp_path):
    root = build_tiny_corpus(tmp_path / "ami")
    corpus = NxtCorpus(root)
    m2 = corpus.discover_meetings()["MEET2"]
    assert m2.has_words
    assert m2.has_segments
    assert m2.has_dialogue_acts
    assert not m2.has_abstractive
    assert not m2.has_extractive
    assert not m2.has_summlink
    assert not m2.has_topics


def test_layer_counts_matches_expected_shape(tmp_path):
    root = build_tiny_corpus(tmp_path / "ami")
    corpus = NxtCorpus(root)
    counts = layer_counts(corpus.discover_meetings())
    assert counts == {
        "words_and_segments": 3,  # MEET1, MEET2, MEET3
        "abstractive": 2,  # MEET1, MEET3
        "extractive_and_summlink": 2,  # MEET1, MEET3 (both have extsumm+summlink files)
        "topics_and_dialogue_acts": 1,  # MEET1 only (AND of both layers)
        "topics": 1,  # MEET1 only
        "dialogue_acts": 3,  # MEET1, MEET2, MEET3
    }


def test_discover_meetings_is_cached_until_refresh(tmp_path):
    root = build_tiny_corpus(tmp_path / "ami")
    corpus = NxtCorpus(root)
    first = corpus.discover_meetings()
    # Add a fourth meeting's words file directly on disk.
    (root / "words" / "MEET4.A.words.xml").write_text(
        '<?xml version="1.0"?><nite:root nite:id="MEET4.A.words" xmlns:nite="http://nite.sourceforge.net/"/>',
        encoding="utf-8",
    )
    cached = corpus.discover_meetings()
    assert cached is first  # unchanged without refresh
    refreshed = corpus.discover_meetings(refresh=True)
    assert "MEET4" in refreshed


def test_path_for_dispatches_to_correct_subdir(tmp_path):
    root = build_tiny_corpus(tmp_path / "ami")
    corpus = NxtCorpus(root)
    assert corpus.path_for("MEET1.A.words.xml") == root / "words" / "MEET1.A.words.xml"
    assert corpus.path_for("MEET1.summlink.xml") == root / "extractive" / "MEET1.summlink.xml"
    assert corpus.path_for("da-types.xml") == root / "ontologies" / "da-types.xml"
