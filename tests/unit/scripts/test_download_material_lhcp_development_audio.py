from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import wave

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "download_material_lhcp_development_audio.py"
SPEC = importlib.util.spec_from_file_location("download_material_lhcp_development_audio", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_frozen_repository_inputs_select_exact_development_surface() -> None:
    cohort = json.loads(
        (ROOT / "configs/probes/material_lhcp_supply/2026-08-26-eligible-cohort.json").read_text()
    )
    admission = json.loads(
        (ROOT / "docs/checks/2026-08-26-material-lhcp-admission/manifest.json").read_text()
    )

    items = MODULE.expected_development_items(cohort)
    files = MODULE.development_source_files(admission)

    assert len(items) == 25
    assert {row["split"] for row in items.values()} == {"dev_2020", "dev_2022"}
    assert len(files) == 6
    assert sum(int(row["size"]) for row in files) == 2_276_036_639
    assert all(str(row["path"]).startswith("longform/dev_") for row in files)


def test_development_selector_rejects_confirmation_item() -> None:
    cohort = {
        "items": [
            {
                "audio_path": f"1c{index}.wav",
                "cohort_role": "development",
                "split": "dev_2020" if index < 25 else "test_2020",
            }
            for index in range(26)
        ]
    }

    with pytest.raises(ValueError, match="expected 25 unique development items"):
        MODULE.expected_development_items(cohort)


def _wav_payload() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 160)
    return output.getvalue()


def test_existing_audio_is_reused_only_after_exact_payload_match(tmp_path: Path) -> None:
    payload = _wav_payload()
    first = MODULE.write_audio(
        payload, audio_path="1c2.wav", split="dev_2020", output_root=tmp_path
    )
    second = MODULE.write_audio(
        payload, audio_path="1c2.wav", split="dev_2020", output_root=tmp_path
    )

    assert first["reused_after_exact_source_match"] is False
    assert second["reused_after_exact_source_match"] is True

    with pytest.raises(ValueError, match="differs from frozen source payload"):
        MODULE.write_audio(
            payload + b"x", audio_path="1c2.wav", split="dev_2020", output_root=tmp_path
        )
