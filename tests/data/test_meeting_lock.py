"""Offline checks on the collaborator-facing data layer under scripts/data/.

No network, no downloads, no model contact -- this only reads
scripts/data/datasets.lock.json and invokes scripts/data/verify.py --help.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOCK_PATH = REPO_ROOT / "scripts" / "data" / "datasets.lock.json"
VERIFY_PATH = REPO_ROOT / "scripts" / "data" / "verify.py"

EXPECTED_DATASET_NAMES = {
    "ami-meeting-corpus",
    "icsi-meeting-corpus",
    "meetingqa",
    "qmsum",
    "m3-slu",
    "meetingbank",
}

REQUIRED_ENTRY_FIELDS = ("source", "license", "expected_layout")


def _load_lock() -> dict:
    with open(LOCK_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_lock_file_exists():
    assert LOCK_PATH.is_file()


def test_lock_file_parses_as_json():
    lock = _load_lock()
    assert isinstance(lock, dict)
    assert "datasets" in lock


def test_lock_has_provenance_pointing_at_the_umbrella_lock():
    lock = _load_lock()
    provenance = lock["provenance"]
    assert "umbrella_commit" in provenance
    assert provenance["umbrella_commit"]
    assert "umbrella" in provenance["generated_from"].lower()


def test_lock_covers_exactly_the_six_meeting_datasets():
    lock = _load_lock()
    names = {entry["name"] for entry in lock["datasets"]}
    assert names == EXPECTED_DATASET_NAMES


def test_every_entry_has_the_required_fields():
    lock = _load_lock()
    for entry in lock["datasets"]:
        for field in REQUIRED_ENTRY_FIELDS:
            assert field in entry, f"{entry['name']} is missing required field {field!r}"
        assert entry["expected_layout"], f"{entry['name']} has an empty expected_layout"
        assert entry["license"], f"{entry['name']} has an empty license"


def test_every_entry_has_a_local_subdir_under_the_data_root():
    lock = _load_lock()
    for entry in lock["datasets"]:
        assert entry.get("local_subdir"), f"{entry['name']} is missing local_subdir"


def test_meetingbank_license_note_documents_the_nc_nd_terms():
    lock = _load_lock()
    meetingbank = next(e for e in lock["datasets"] if e["name"] == "meetingbank")
    assert "nc-nd" in meetingbank["license"].lower()
    assert "noncommercial" in meetingbank["license_note"].lower() or "nc" in meetingbank["license_note"].lower()


def test_verify_help_runs_and_exits_zero():
    result = subprocess.run(
        [sys.executable, str(VERIFY_PATH), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert "datasets.lock.json" in result.stdout


def test_verify_rejects_unknown_dataset_name():
    result = subprocess.run(
        [sys.executable, str(VERIFY_PATH), "--dataset", "not-a-real-dataset", "--data-root", str(REPO_ROOT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode != 0
    assert "unknown dataset" in result.stderr.lower()


def test_verify_reports_missing_for_an_empty_data_root(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(VERIFY_PATH),
            "--dataset",
            "ami-meeting-corpus",
            "--data-root",
            str(tmp_path),
            "--quiet",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 1
    assert "MISSING" in result.stdout
