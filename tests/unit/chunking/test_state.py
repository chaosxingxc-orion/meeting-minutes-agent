"""Tests for :mod:`meeting_minutes_agent.chunking.state`: the episode-local,
append-only, content-hashed inter-chunk state log, and its
correction-supersedes-by-hash discipline."""

from __future__ import annotations

import dataclasses

import pytest

from meeting_minutes_agent.chunking.state import GlossaryStateLog, StateEntry


def test_append_returns_a_new_log_original_unchanged():
    log0 = GlossaryStateLog()
    log1 = log0.append({"term": "alpha"}, chunk_index=0)

    assert log0.entries == ()
    assert len(log1.entries) == 1
    assert log1 is not log0


def test_sequential_appends_form_a_valid_hash_chain():
    log = GlossaryStateLog()
    log = log.append({"term": "alpha"}, chunk_index=0)
    log = log.append({"term": "beta"}, chunk_index=1)
    log = log.append({"term": "gamma"}, chunk_index=2)

    assert [e.seq for e in log.entries] == [0, 1, 2]
    assert log.entries[0].previous_hash is None
    assert log.entries[1].previous_hash == log.entries[0].entry_hash
    assert log.entries[2].previous_hash == log.entries[1].entry_hash
    assert log.verify_chain() is True


def test_two_appends_with_identical_payloads_still_get_distinct_hashes():
    # seq/chunk_index/previous_hash all enter the hash, so even a byte-
    # identical payload never collides across positions in the chain.
    log = GlossaryStateLog()
    log = log.append({"term": "alpha"}, chunk_index=0)
    log = log.append({"term": "alpha"}, chunk_index=0)
    assert log.entries[0].entry_hash != log.entries[1].entry_hash


def test_correction_supersedes_a_known_hash():
    log = GlossaryStateLog()
    log = log.append({"term": "alpha", "spelling": "Alpah"}, chunk_index=0)
    first_hash = log.entries[0].entry_hash

    log = log.append({"term": "alpha", "spelling": "Alpha"}, chunk_index=1, supersedes=first_hash)

    assert log.entries[1].supersedes == first_hash
    active = log.active_entries()
    assert len(active) == 1
    assert active[0].payload["spelling"] == "Alpha"


def test_correction_of_unknown_hash_raises_and_never_mutates_the_log():
    log = GlossaryStateLog()
    log = log.append({"term": "alpha"}, chunk_index=0)
    before = log.entries

    with pytest.raises(ValueError):
        log.append({"term": "beta"}, chunk_index=1, supersedes="not-a-real-hash")

    assert log.entries == before  # the failed append left the log untouched


def test_active_entries_after_a_chain_of_corrections():
    log = GlossaryStateLog()
    log = log.append({"v": 1}, chunk_index=0)
    h1 = log.entries[0].entry_hash
    log = log.append({"v": 2}, chunk_index=1, supersedes=h1)
    h2 = log.entries[1].entry_hash
    log = log.append({"v": 3}, chunk_index=2, supersedes=h2)
    log = log.append({"other": "untouched"}, chunk_index=2)

    active_payloads = [e.payload for e in log.active_entries()]
    assert {"v": 3} in active_payloads
    assert {"other": "untouched"} in active_payloads
    assert {"v": 1} not in active_payloads
    assert {"v": 2} not in active_payloads
    assert len(active_payloads) == 2


def test_entries_tuple_cannot_be_item_assigned():
    log = GlossaryStateLog()
    log = log.append({"term": "alpha"}, chunk_index=0)
    with pytest.raises(TypeError):
        log.entries[0] = log.entries[0]  # type: ignore[index]


def test_log_field_reassignment_is_rejected_frozen_dataclass():
    log = GlossaryStateLog()
    with pytest.raises(dataclasses.FrozenInstanceError):
        log.entries = ()  # type: ignore[misc]


def test_state_entry_is_itself_frozen():
    log = GlossaryStateLog().append({"term": "alpha"}, chunk_index=0)
    entry = log.entries[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.seq = 99  # type: ignore[misc]


def test_verify_chain_detects_a_tampered_previous_hash():
    log = GlossaryStateLog()
    log = log.append({"term": "alpha"}, chunk_index=0)
    log = log.append({"term": "beta"}, chunk_index=1)
    assert log.verify_chain() is True

    tampered_second = dataclasses.replace(log.entries[1], previous_hash="deadbeef")
    tampered_log = GlossaryStateLog(entries=(log.entries[0], tampered_second))
    assert tampered_log.verify_chain() is False


def test_verify_chain_detects_a_recomputed_hash_mismatch():
    log = GlossaryStateLog()
    log = log.append({"term": "alpha"}, chunk_index=0)

    tampered = dataclasses.replace(log.entries[0], payload={"term": "TAMPERED"})
    tampered_log = GlossaryStateLog(entries=(tampered,))
    assert tampered_log.verify_chain() is False


def test_state_entry_to_dict_shape():
    log = GlossaryStateLog().append({"term": "alpha"}, chunk_index=0)
    d = log.entries[0].to_dict()
    assert d["seq"] == 0
    assert d["chunk_index"] == 0
    assert d["payload"] == {"term": "alpha"}
    assert d["previous_hash"] is None
    assert d["supersedes"] is None
    assert d["entry_hash"] == log.entries[0].entry_hash


def test_empty_log_verifies_trivially():
    assert GlossaryStateLog().verify_chain() is True
    assert GlossaryStateLog().active_entries() == ()
