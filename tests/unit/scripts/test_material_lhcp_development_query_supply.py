"""Offline tests for LHCP development material query supply."""

from __future__ import annotations

import json
from pathlib import Path

import build_material_lhcp_development_query_supply as builder
import read_material_lhcp_development_query_supply as reader


def _candidate(meeting_id: str, index: int) -> dict[str, object]:
    return {
        "audio_path": f"{meeting_id}.wav",
        "canonical": f"Term{index}",
        "category": "acronym_or_alphanumeric",
        "occurrences": [{
            "page": index + 1,
            "relative_path": f"materials/{meeting_id}.pdf",
            "source_span": f"context Term{index}",
        }],
    }


def _fixture() -> tuple[dict[str, object], dict[str, object], dict[str, object], list[dict[str, object]]]:
    config = {
        "experiment_id": "E-MATERIAL-LHCP-DEVELOPMENT-QUERY-SUPPLY",
        "construction": {
            "key_width": 2,
            "key_selection_salt": "test-salt",
            "maximum_prior_keywords": 2,
            "query_instruction": "Find material.\n",
            "length_limited_position": 2,
        },
        "passing_gates": {"development_meetings": 2, "queries": 3},
    }
    cohort = {"items": [
        {"audio_path": "m1.wav", "cohort_role": "development"},
        {"audio_path": "m2.wav", "cohort_role": "development"},
    ]}
    source = {"reference_reads": 0, "candidates": [
        *[_candidate("m1", index) for index in range(3)],
        *[_candidate("m2", index) for index in range(3)],
    ]}
    rows = [
        {"position": 0, "meeting_id": "m1", "slice_index": 0, "turn_id": "m1-slice0000", "audio_sha256": "a", "transcript_text": "alpha particle result", "transcript_sha256": "t0", "speaker_labels": ["speaker_1"]},
        {"position": 1, "meeting_id": "m1", "slice_index": 1, "turn_id": "m1-slice0001", "audio_sha256": "b", "transcript_text": "second result", "transcript_sha256": "t1", "speaker_labels": ["speaker_1"]},
        {"position": 2, "meeting_id": "m2", "slice_index": 0, "turn_id": "m2-slice0000", "audio_sha256": "c", "transcript_text": "new meeting", "transcript_sha256": "t2", "speaker_labels": ["speaker_2"]},
    ]
    return config, cohort, source, rows


def test_supply_is_equal_width_deranged_and_strictly_causal() -> None:
    config, cohort, source, rows = _fixture()
    selected, inventory, mapping, queries = builder.build_supply(config, cohort, source, rows)
    assert len(selected) == 4
    assert [row["selected_candidates"] for row in inventory] == [2, 2]
    assert mapping == {"m1": "m2", "m2": "m1"}
    assert queries[0]["runtime_context"]["prior_turn_id"] is None
    assert queries[1]["runtime_context"]["prior_turn_id"] == "m1-slice0000"
    assert queries[2]["runtime_context"]["prior_turn_id"] is None
    assert queries[2]["potentially_truncated"] is True


def test_reader_reconstructs_and_accepts_frozen_supply(tmp_path: Path) -> None:
    config, cohort, source, rows = _fixture()
    selected, inventory, mapping, queries = builder.build_supply(config, cohort, source, rows)
    root = tmp_path / "supply"
    root.mkdir()
    builder.write_json_exclusive(root / "selected-candidates.json", {
        "schema": "material-lhcp-development-selected-candidates-v1",
        "experiment_id": config["experiment_id"],
        "reference_reads": 0,
        "candidates": selected,
    })
    builder.write_json_exclusive(root / "derangement.json", {
        "schema": "material-lhcp-development-derangement-v1",
        "policy": "ascending_meeting_id_next_cyclic",
        "mapping": mapping,
    })
    builder.write_jsonl_exclusive(root / "queries.jsonl", queries)
    artifacts = {
        name: {"sha256": builder.sha256_file(root / name), "bytes": (root / name).stat().st_size}
        for name in ("selected-candidates.json", "derangement.json", "queries.jsonl")
    }
    builder.write_json_exclusive(root / "receipt.json", {
        "reference_reads": 0, "confirmation_access": 0, "embedding_calls": 0, "omni_calls": 0,
        "totals": {"meetings": 2, "available_candidates": 6, "selected_candidates": 4, "queries": 3,
                   "queries_with_prior_context": 1, "potentially_truncated_queries": 1},
        "meeting_inventory": inventory, "artifacts": artifacts,
    })
    result = reader.read_supply(config, cohort, source, rows, root)
    assert result["verdict"] == "LHCP_DEVELOPMENT_QUERY_SUPPLY_READY"
    assert result["derangement_fixed_points"] == 0


def test_non_contiguous_slice_order_is_rejected() -> None:
    config, cohort, source, rows = _fixture()
    rows[1]["slice_index"] = 2
    try:
        builder.build_supply(config, cohort, source, rows)
    except ValueError as error:
        assert "non-contiguous slice order" in str(error)
    else:
        raise AssertionError("expected non-contiguous order rejection")
