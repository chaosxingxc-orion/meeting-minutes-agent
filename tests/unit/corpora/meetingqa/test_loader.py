"""Tests for :mod:`meeting_minutes_agent.corpora.meetingqa.loader`: split
discipline (no default that silently reads test), the MultiSpanDataset BIO
decode + flat-fallback pair, speaker extraction, and audio-path
resolution -- on the tiny synthetic fixture built by :mod:`.fixtures`."""

from __future__ import annotations

import pytest

from meeting_minutes_agent.corpora.meetingqa.loader import (
    SPLITS,
    MeetingAudioNotResolvedError,
    MeetingQASplitError,
    load_split,
    resolve_audio_path,
)

from .fixtures import (
    DEV_FALLBACK_ANSWER,
    DEV_FALLBACK_ID,
    DEV_MULTI_SPAN_DECODED,
    DEV_MULTI_SPAN_ID,
    DEV_SINGLE_SPAN_DECODED,
    DEV_SINGLE_SPAN_ID,
    DEV_UNANSWERABLE_ID,
    TRAIN_DECODED,
    TRAIN_ID,
    build_tiny_ami_audio_tree,
    build_tiny_meetingqa_release,
)


@pytest.fixture
def meetingqa_root(tmp_path):
    root = tmp_path / "meetingqa"
    build_tiny_meetingqa_release(root)
    return root


@pytest.fixture
def ami_root(tmp_path):
    root = tmp_path / "ami"
    build_tiny_ami_audio_tree(root)
    return root


def _by_id(examples):
    return {ex.example_id: ex for ex in examples}


# ---------------------------------------------------------------------------
# split discipline
# ---------------------------------------------------------------------------


def test_split_is_required_keyword_no_default(meetingqa_root, ami_root):
    with pytest.raises(TypeError):
        load_split(meetingqa_root=meetingqa_root, ami_root=ami_root)  # type: ignore[call-arg]


def test_invalid_split_name_is_rejected(meetingqa_root, ami_root):
    with pytest.raises(MeetingQASplitError, match="bogus"):
        load_split(meetingqa_root=meetingqa_root, ami_root=ami_root, split="bogus")


def test_all_declared_splits_are_train_dev_test():
    assert SPLITS == ("train", "dev", "test")


def test_valid_but_unfixtured_split_raises_plain_file_not_found(meetingqa_root, ami_root):
    # "test" is a declared-valid split name, but this fixture never wrote a
    # final-AMI-test.json -- the honest, un-wrapped FileNotFoundError must
    # propagate rather than being swallowed or silently substituting dev.
    with pytest.raises(FileNotFoundError):
        load_split(meetingqa_root=meetingqa_root, ami_root=ami_root, split="test")


def test_train_and_dev_never_mix(meetingqa_root, ami_root):
    dev = load_split(meetingqa_root=meetingqa_root, ami_root=ami_root, split="dev")
    train = load_split(meetingqa_root=meetingqa_root, ami_root=ami_root, split="train")

    dev_ids = {ex.example_id for ex in dev}
    train_ids = {ex.example_id for ex in train}
    assert dev_ids.isdisjoint(train_ids)
    assert TRAIN_ID in train_ids
    assert TRAIN_ID not in dev_ids
    assert DEV_SINGLE_SPAN_ID in dev_ids
    assert DEV_SINGLE_SPAN_ID not in train_ids

    assert all(ex.split == "dev" for ex in dev)
    assert all(ex.split == "train" for ex in train)

    train_example = _by_id(train)[TRAIN_ID]
    assert train_example.answer_spans == TRAIN_DECODED


# ---------------------------------------------------------------------------
# per-instance shape: question, meeting id, answer spans, unanswerable,
# speakers
# ---------------------------------------------------------------------------


def test_dev_split_has_exactly_the_four_fixtured_examples(meetingqa_root, ami_root):
    dev = load_split(meetingqa_root=meetingqa_root, ami_root=ami_root, split="dev")
    assert len(dev) == 4
    ids = {ex.example_id for ex in dev}
    assert ids == {DEV_SINGLE_SPAN_ID, DEV_MULTI_SPAN_ID, DEV_UNANSWERABLE_ID, DEV_FALLBACK_ID}


def test_single_span_example_decodes_via_multi_span_file(meetingqa_root, ami_root):
    dev = _by_id(load_split(meetingqa_root=meetingqa_root, ami_root=ami_root, split="dev"))
    ex = dev[DEV_SINGLE_SPAN_ID]
    assert ex.meeting_id == "MEET1"
    assert ex.question == "What did speaker 1 say?"
    assert ex.unanswerable is False
    assert ex.answer_spans == DEV_SINGLE_SPAN_DECODED
    assert ex.span_source == "decoded_multi_span"
    assert ex.speakers == ("0", "1")


def test_multi_span_example_decodes_two_disjoint_spans(meetingqa_root, ami_root):
    dev = _by_id(load_split(meetingqa_root=meetingqa_root, ami_root=ami_root, split="dev"))
    ex = dev[DEV_MULTI_SPAN_ID]
    assert ex.unanswerable is False
    assert ex.answer_spans == DEV_MULTI_SPAN_DECODED
    assert len(ex.answer_spans) == 2
    assert ex.span_source == "decoded_multi_span"
    # a third speaker id, only present in this example, must still surface
    assert ex.speakers == ("0", "1", "2")


def test_unanswerable_example_has_empty_spans(meetingqa_root, ami_root):
    dev = _by_id(load_split(meetingqa_root=meetingqa_root, ami_root=ami_root, split="dev"))
    ex = dev[DEV_UNANSWERABLE_ID]
    assert ex.unanswerable is True
    assert ex.answer_spans == ()
    assert ex.span_source == "unanswerable"


def test_example_absent_from_multi_span_file_falls_back_to_flat_answers(meetingqa_root, ami_root):
    dev = _by_id(load_split(meetingqa_root=meetingqa_root, ami_root=ami_root, split="dev"))
    ex = dev[DEV_FALLBACK_ID]
    assert ex.meeting_id == "MEET2"
    assert ex.unanswerable is False
    assert ex.answer_spans == DEV_FALLBACK_ANSWER
    assert ex.span_source == "flat_fallback"


def test_to_dict_shape(meetingqa_root, ami_root):
    dev = _by_id(load_split(meetingqa_root=meetingqa_root, ami_root=ami_root, split="dev"))
    d = dev[DEV_SINGLE_SPAN_ID].to_dict()
    assert d["example_id"] == DEV_SINGLE_SPAN_ID
    assert d["meeting_id"] == "MEET1"
    assert d["answer_spans"] == list(DEV_SINGLE_SPAN_DECODED)
    assert d["unanswerable"] is False
    assert d["speakers"] == ["0", "1"]
    assert isinstance(d["audio_path"], str)


# ---------------------------------------------------------------------------
# audio-path resolution (reference only -- never bytes)
# ---------------------------------------------------------------------------


def test_audio_path_resolves_under_the_ami_layout(meetingqa_root, ami_root):
    dev = _by_id(load_split(meetingqa_root=meetingqa_root, ami_root=ami_root, split="dev"))
    ex = dev[DEV_SINGLE_SPAN_ID]
    assert ex.audio_path == ami_root / "amicorpus" / "MEET1" / "audio" / "MEET1.Mix-Headset.wav"
    assert ex.audio_path.is_file()


def test_examples_sharing_a_meeting_id_resolve_to_the_same_audio_path(meetingqa_root, ami_root):
    dev = _by_id(load_split(meetingqa_root=meetingqa_root, ami_root=ami_root, split="dev"))
    assert dev[DEV_SINGLE_SPAN_ID].audio_path == dev[DEV_MULTI_SPAN_ID].audio_path == dev[DEV_UNANSWERABLE_ID].audio_path


def test_resolve_audio_path_direct_success(ami_root):
    path = resolve_audio_path(ami_root, "MEET1")
    assert path == ami_root / "amicorpus" / "MEET1" / "audio" / "MEET1.Mix-Headset.wav"
    assert path.is_file()


def test_resolve_audio_path_missing_meeting_raises_by_default(ami_root):
    with pytest.raises(MeetingAudioNotResolvedError, match="MEET9"):
        resolve_audio_path(ami_root, "MEET9")


def test_resolve_audio_path_require_exists_false_returns_templated_path(ami_root):
    path = resolve_audio_path(ami_root, "MEET9", require_exists=False)
    assert path == ami_root / "amicorpus" / "MEET9" / "audio" / "MEET9.Mix-Headset.wav"
    assert not path.exists()


def test_load_split_require_audio_true_raises_for_unresolvable_meeting(meetingqa_root, tmp_path):
    empty_ami_root = tmp_path / "ami_empty"
    empty_ami_root.mkdir()
    with pytest.raises(MeetingAudioNotResolvedError):
        load_split(meetingqa_root=meetingqa_root, ami_root=empty_ami_root, split="dev")


def test_load_split_require_audio_false_never_touches_the_filesystem_for_audio(meetingqa_root, tmp_path):
    empty_ami_root = tmp_path / "ami_empty"
    empty_ami_root.mkdir()
    dev = load_split(meetingqa_root=meetingqa_root, ami_root=empty_ami_root, split="dev", require_audio=False)
    assert len(dev) == 4
    assert all(not ex.audio_path.exists() for ex in dev)
