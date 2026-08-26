"""Tests for the reference-blind new-surface admission audit."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "audit_material_new_surface_admission.py"
_SPEC = importlib.util.spec_from_file_location("audit_material_new_surface_admission", _SCRIPT)
assert _SPEC and _SPEC.loader
tool = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tool)


def _write(path: Path, value: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, bytes):
        path.write_bytes(value)
    else:
        path.write_text(value, encoding="utf-8", newline="\n")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_admission_projects_no_reference_text(tmp_path: Path) -> None:
    item = "ECV-0002"
    reference = b"reference"
    answer = b"answer"
    metadata = {
        "item_id": item, "call_id": "1641285", "exchange_index": 1,
        "selection_tranche": "human_core_73", "boundary_repaired": False,
        "authentic_audio": True, "same_speaker_within_item": True,
        "human_quality_gates_passed": 9, "source_dataset_license": "Apache-2.0",
        "reference_audio_sha256": hashlib.sha256(reference).hexdigest(),
        "answer_audio_sha256": hashlib.sha256(answer).hexdigest(),
        "reference_duration_s": 1.0, "answer_duration_s": 1.0,
        "reference_text": "sealed reference", "answer_text": "sealed answer",
    }
    _write(tmp_path / "source-metadata/metadata.jsonl", json.dumps(metadata) + "\n")
    _write(tmp_path / "source-metadata/selection_manifest.json", json.dumps({"public_item_mapping": [{"item_id": item, "call_id": "1641285"}]}))
    _write(tmp_path / "source-metadata/MANIFEST.sha256", "manifest\n")
    _write(tmp_path / "source-metadata/QUALITY_REPORT.json", json.dumps({"status": "pass", "human_validation": {"all_core_items_pass_all_gates": True}}))
    _write(tmp_path / f"audio/{item}_reference.wav", reference)
    _write(tmp_path / f"audio/{item}_answer.wav", answer)
    _write(tmp_path / "materials/2019/200.pdf", b"%PDF-test")
    for year in (2019, 2020, 2021):
        rows = {"1641285": {"mp3_id": "100", "ppt_id": "200", "input": "must not be projected"}} if year == 2019 else {}
        _write(tmp_path / f"fincall/transcripts_{year}.json", json.dumps(rows))

    pinned = [
        "source-metadata/metadata.jsonl", "source-metadata/selection_manifest.json",
        "source-metadata/MANIFEST.sha256", "source-metadata/QUALITY_REPORT.json",
        "fincall/transcripts_2019.json", "fincall/transcripts_2020.json", "fincall/transcripts_2021.json",
    ]
    config = {
        "experiment_id": "test", "surface": {"name": "test"},
        "source_pins": {"files": {name: _sha(tmp_path / name) for name in pinned}, "material_archives": {"ppt_2019.zip": {}}},
        "known_exposure_exclusions": [],
        "reference_firewall": {"discovery_allowed_fields": [key for key in metadata if key not in {"reference_text", "answer_text"}]},
        "admission": {"required_human_quality_gates": 9, "required_audio_roles": ["reference_audio", "answer_audio"], "minimum_admitted_items": 1},
        "split": {"salt": "test", "development_items": 1, "confirmation_items": 0},
    }
    cohort, verdict = tool.audit(config, tmp_path)
    encoded = json.dumps(cohort)
    assert verdict["verdict"] == "NEW_SURFACE_COHORT_FROZEN"
    assert verdict["reference_contact"] == 0
    assert "sealed reference" not in encoded
    assert "sealed answer" not in encoded
    assert cohort["items"][0]["split"] == "development"


def test_known_exposure_is_excluded(tmp_path: Path) -> None:
    rows = tool.split_rows([{"item_id": "ECV-0002"}], "salt", 1, 0)
    assert rows[0]["split"] == "development"
