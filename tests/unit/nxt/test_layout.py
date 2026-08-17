from __future__ import annotations

from meeting_minutes_agent.corpora.nxt.layout import AMI_LAYOUT


def test_dir_for_filename_words():
    assert AMI_LAYOUT.dir_for_filename("ES2002a.A.words.xml") == "words"


def test_dir_for_filename_segments():
    assert AMI_LAYOUT.dir_for_filename("ES2002a.A.segments.xml") == "segments"


def test_dir_for_filename_dialogue_act():
    assert AMI_LAYOUT.dir_for_filename("ES2002a.A.dialog-act.xml") == "dialogueActs"


def test_dir_for_filename_abssumm():
    assert AMI_LAYOUT.dir_for_filename("ES2002a.abssumm.xml") == "abstractive"


def test_dir_for_filename_extsumm_and_summlink_share_extractive_dir():
    assert AMI_LAYOUT.dir_for_filename("ES2002a.extsumm.xml") == "extractive"
    assert AMI_LAYOUT.dir_for_filename("ES2002a.summlink.xml") == "extractive"


def test_dir_for_filename_topic():
    assert AMI_LAYOUT.dir_for_filename("ES2002a.topic.xml") == "topics"


def test_dir_for_filename_unknown_returns_none():
    assert AMI_LAYOUT.dir_for_filename("da-types.xml") is None
    assert AMI_LAYOUT.dir_for_filename("random-file.txt") is None
