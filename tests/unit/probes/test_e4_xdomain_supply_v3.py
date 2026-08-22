import hashlib
import json
from pathlib import Path

import pytest

from meeting_minutes_agent.probes.e4_xdomain_supply_v2 import (
    EXPECTED_SOURCE_COMMIT,
    EntityMention,
    Earnings22AuditError,
)
from meeting_minutes_agent.probes.e4_xdomain_supply_v3 import (
    EXPECTED_PARENT_CONTENT_HASH,
    NarrowMeetingCounts,
    analyse_narrow_mentions,
    build_reserve_manifest,
    reserve_inputs,
    summarise_reserve,
)


def test_narrow_analysis_filters_classes_and_separates_carry():
    mentions = (
        EntityMention("A", 1.0, "api", "ABBREVIATION"),
        EntityMention("A", 91.0, "api", "ABBREVIATION"),
        EntityMention("B", 181.0, "api", "ABBREVIATION"),
        EntityMention("A", 271.0, "api", "ABBREVIATION"),
        EntityMention("A", 1.0, "q3", "ALPHANUMERIC"),
        EntityMention("A", 91.0, "q3", "ALPHANUMERIC"),
        EntityMention("A", 1.0, "we're", "CONTRACTION"),
        EntityMention("A", None, "5g", "ALPHANUMERIC"),
    )
    result = analyse_narrow_mentions(mentions)
    assert result.admitted_mentions == 7
    assert result.excluded_unaligned_mentions == 1
    assert result.candidate_units == 6
    assert result.exclusive_by_surface == {"api": 1, "q3": 1}
    assert result.shared_carry == 1
    assert result.global_only_carry == 1


def _meeting(index: int, exclusive: int) -> NarrowMeetingCounts:
    return NarrowMeetingCounts(
        candidate_units=exclusive + 1,
        admitted_mentions=exclusive + 1,
        excluded_unaligned_mentions=0,
        same_speaker_carry=exclusive,
        shared_carry=0,
        global_only_carry=0,
        exclusive_by_surface={f"term-{index}-{value}": 1 for value in range(exclusive)},
        candidate_units_by_class={"ABBREVIATION": exclusive + 1},
        exclusive_units_by_class={"ABBREVIATION": exclusive},
    )


def test_frozen_gates_pass_and_fail_at_meeting_level():
    passing = summarise_reserve([_meeting(index, 5) for index in range(45)])
    failing = summarise_reserve([_meeting(index, 1) for index in range(45)])
    assert passing["passes"] is True
    assert failing["passes"] is False
    assert failing["gates"]["eligible_meetings"] is False


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parent_manifest(root: Path) -> dict:
    rows = []
    for index in range(125):
        split = "discovery" if index < 80 else "reserve"
        relative = f"transcripts/force_aligned_nlp_references/f{index}.aligned.nlp"
        if split == "reserve":
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"reserve-{index}", encoding="utf-8")
            size = path.stat().st_size
            digest = _hash(path)
        else:
            size = 999
            digest = "0" * 64
        rows.append(
            {"file_id": f"f{index}", "split": split, "path": relative, "bytes": size, "sha256": digest}
        )
    parent = {
        "schema_version": "e4-xdomain-supply-v2-input-v1",
        "source_commit": EXPECTED_SOURCE_COMMIT,
        "split_salt": "e4-xdomain-supply-v2-2026-08-21",
        "license_sha256": "license",
        "readme_sha256": "readme",
        "inputs": rows,
    }
    canonical = json.dumps(parent, sort_keys=True, separators=(",", ":")).encode()
    parent["content_hash"] = hashlib.sha256(canonical).hexdigest()
    return parent


def test_manifest_builder_never_requires_discovery_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    parent = _parent_manifest(tmp_path)
    monkeypatch.setattr(
        "meeting_minutes_agent.probes.e4_xdomain_supply_v3.EXPECTED_PARENT_CONTENT_HASH",
        parent["content_hash"],
    )
    manifest = build_reserve_manifest(parent, tmp_path)
    assert len(manifest["inputs"]) == 45
    assert all("discovery" not in row and "split" not in row for row in manifest["inputs"])
    assert all(item.path.is_file() for item in reserve_inputs(manifest, tmp_path))

    contaminated = json.loads(json.dumps(manifest))
    contaminated["inputs"][0]["split"] = "discovery"
    canonical = {key: value for key, value in contaminated.items() if key != "content_hash"}
    contaminated["content_hash"] = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with pytest.raises(Earnings22AuditError, match="reserve-only row schema drift"):
        reserve_inputs(contaminated, tmp_path)


def test_manifest_refuses_parent_hash_change(tmp_path: Path):
    parent = _parent_manifest(tmp_path)
    assert parent["content_hash"] != EXPECTED_PARENT_CONTENT_HASH
    with pytest.raises(Earnings22AuditError, match="parent content hash mismatch"):
        build_reserve_manifest(parent, tmp_path)
