from __future__ import annotations

import json

from meeting_minutes_agent.runreceipt import (
    build_run_receipt,
    config_hash,
    read_git_state,
    write_run_receipt,
)


def test_config_hash_is_deterministic_regardless_of_key_order():
    a = {"x": 1, "y": 2}
    b = {"y": 2, "x": 1}
    assert config_hash(a) == config_hash(b)


def test_config_hash_changes_with_content():
    assert config_hash({"x": 1}) != config_hash({"x": 2})


def test_build_run_receipt_has_required_fields():
    receipt = build_run_receipt({"a": 1}, repo_root=None, run_id="fixed-id")
    d = receipt.to_dict()
    assert d["run_id"] == "fixed-id"
    assert d["config"] == {"a": 1}
    assert d["config_hash"] == config_hash({"a": 1})
    assert "commit" in d["git"]
    assert "dirty" in d["git"]
    assert d["created_utc"]  # non-empty ISO timestamp


def test_build_run_receipt_generates_run_id_when_not_given():
    r1 = build_run_receipt({"a": 1})
    r2 = build_run_receipt({"a": 1})
    assert r1.run_id != r2.run_id


def test_write_run_receipt_writes_valid_json(tmp_path):
    out = write_run_receipt(tmp_path / "nested" / "receipt.json", {"a": 1}, run_id="fixed-id")
    assert out.exists()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["run_id"] == "fixed-id"
    assert loaded["config"] == {"a": 1}


def test_read_git_state_on_this_repo_is_not_fatal():
    # This repo IS a git repo, so this should normally resolve a commit, but
    # the contract under test is "never raises" -- assert only that it
    # returns a GitState with well-typed fields either way.
    state = read_git_state(repo_root=".")
    assert state.commit is None or isinstance(state.commit, str)
    assert state.dirty is None or isinstance(state.dirty, bool)


def test_read_git_state_outside_a_repo_is_not_fatal(tmp_path):
    state = read_git_state(repo_root=tmp_path)
    assert state.commit is None
    assert state.error is not None
