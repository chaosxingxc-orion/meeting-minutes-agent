import json

import pytest

from meeting_minutes_agent.probes.e4_confirmatory import RuntimeTarget
from meeting_minutes_agent.probes.e4_disjoint_direction import (
    DirectionRuntimeBinding,
    build_requests,
    load_runtime_binding,
)
from meeting_minutes_agent.runreceipt import config_hash


def _target(**overrides):
    values = {
        "target_id": "dialogue-t001",
        "uniq_id": "dialogue",
        "turn_index": 1,
        "speaker_id": "speaker_1",
        "start": 1.0,
        "end": 2.0,
        "global_terms": ("Acme",),
        "speaker_terms": ("Acme",),
        "wrong_terms": ("Beta",),
        "source_tar": "/tmp/source.tar",
        "tar_member": "./dialogue.wav",
        "audio_sha256": "a" * 64,
    }
    values.update(overrides)
    return RuntimeTarget(**values)


def test_requests_are_two_arm_and_counterbalanced():
    binding = DirectionRuntimeBinding({"content_hash": "hash"}, (_target(), _target(target_id="dialogue-t002")))

    requests = build_requests(binding)

    assert [request.arm for request in requests] == ["D0-global", "D1-speaker", "D1-speaker", "D0-global"]
    assert requests[0].injected_terms == ("Acme",)
    assert requests[1].injected_terms == ("Acme",)


def test_runtime_loader_rejects_non_disjoint_state(tmp_path):
    document = {
        "schema_version": "e4-disjoint-dir-runtime-binding-v1",
        "experiment_id": "test",
        "targets": [
            {
                "target_id": "dialogue-t001",
                "uniq_id": "dialogue",
                "turn_index": 1,
                "speaker_id": "speaker_1",
                "start": 1.0,
                "end": 2.0,
                "global_terms": ["Acme"],
                "speaker_terms": ["Acme"],
                "wrong_terms": ["acme"],
                "source_tar": "/tmp/source.tar",
                "tar_member": "./dialogue.wav",
                "audio_sha256": "a" * 64,
            }
        ],
    }
    document["content_hash"] = config_hash(document)
    path = tmp_path / "binding.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="non-disjoint"):
        load_runtime_binding(path)
