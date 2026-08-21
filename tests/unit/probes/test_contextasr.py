from __future__ import annotations

import json

import pytest

from meeting_minutes_agent.probes.contextasr import (
    ARMS,
    ContextAsrEntry,
    ContextAsrManifest,
    build_head_request,
    build_requests,
    load_manifest,
)
from meeting_minutes_agent.runreceipt import config_hash


def _entry(uniq_id: str = "X1") -> ContextAsrEntry:
    return ContextAsrEntry(
        uniq_id=uniq_id,
        language="English",
        duration=10.0,
        domain_label="Medicine",
        reference_text="The patient received pembrolizumab.",
        entity_list=("pembrolizumab",),
        deranged_entity_list=("trastuzumab",),
        corrupt_entity_list=("pmebrolizumab",),
        source_tar="source.tar",
        tar_member=f"./{uniq_id}.wav",
        audio_sha256="0" * 64,
    )


def _manifest(*entries: ContextAsrEntry) -> ContextAsrManifest:
    return ContextAsrManifest(raw={"content_hash": "abc"}, entries=entries)


def test_arm_rendering_changes_only_supplied_context():
    bare, bare_terms = build_head_request(_entry(), "C0-bare")
    entity, entity_terms = build_head_request(_entry(), "C2-entity")
    deranged, deranged_terms = build_head_request(_entry(), "C3-deranged")
    assert bare.task_instruction == entity.task_instruction == deranged.task_instruction
    assert bare.template_sha256 == entity.template_sha256 == deranged.template_sha256
    assert bare.supplied_text == ()
    assert entity_terms == ("pembrolizumab",)
    assert deranged_terms == ("trastuzumab",)
    assert "pembrolizumab" in "\n".join(entity.supplied_text)


def test_request_order_is_latin_rotated_and_complete():
    requests = build_requests(_manifest(_entry("X1"), _entry("X2")))
    assert len(requests) == 2 * len(ARMS)
    assert [request.arm for request in requests[:5]] == list(ARMS)
    assert [request.arm for request in requests[5:10]] == list(ARMS[1:] + ARMS[:1])
    assert len({request.request_id for request in requests}) == len(requests)


def test_manifest_hash_is_fail_closed(tmp_path):
    entry = _entry().to_dict()
    document = {"schema_version": "contextasr-smoke-manifest-v1", "entries": [entry]}
    document["content_hash"] = config_hash(document)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    assert load_manifest(path).entries[0].uniq_id == "X1"
    document["entries"][0]["duration"] = 11.0
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_manifest(path)
