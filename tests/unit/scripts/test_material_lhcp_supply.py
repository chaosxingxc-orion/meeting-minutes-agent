"""Tests for LHCP material acquisition and extraction helpers."""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path


def _load(name: str):
    script = Path(__file__).resolve().parents[3] / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


download = _load("download_material_lhcp.py")
supply = _load("audit_material_lhcp_supply.py")


def test_safe_filename_removes_path_and_unsafe_characters() -> None:
    assert download.safe_filename("../A talk (final).pdf") == "A_talk_final_.pdf"


def test_material_rows_are_deterministic() -> None:
    manifest = {
        "items": [
            {"audio_path": "2c2.wav", "split": "test", "event_id": 2, "contribution_friendly_id": 2, "materials": [{"id": 9}]},
            {"audio_path": "1c1.wav", "split": "dev", "event_id": 1, "contribution_friendly_id": 1, "materials": [{"id": 8}]},
        ]
    }
    assert [row["audio_path"] for row in download.material_rows(manifest)] == ["1c1.wav", "2c2.wav"]


def test_extract_pptx_reads_slide_text(tmp_path: Path) -> None:
    path = tmp_path / "talk.pptx"
    xml = b'<p:sld xmlns:p="p" xmlns:a="a"><p:cSld><a:t>QCD</a:t><a:t>Run 3</a:t></p:cSld></p:sld>'
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ppt/slides/slide1.xml", xml)
    assert supply.extract_pptx(path) == [(1, "QCD Run 3")]


def test_replace_lone_surrogates_preserves_legal_unicode() -> None:
    assert supply.replace_lone_surrogates("QCD\ud835 Run 3") == "QCD\ufffd Run 3"
    assert supply.replace_lone_surrogates("Higgs μ") == "Higgs μ"
