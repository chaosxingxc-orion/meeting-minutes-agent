"""Offline tests for the Earnings-22 audio acquirer."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


_SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "data"
    / "acquire_earnings22_audio.py"
)
_SPEC = importlib.util.spec_from_file_location("acquire_earnings22_audio", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
tool = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tool)


def test_pointer_pattern_accepts_canonical_pointer() -> None:
    digest = "a" * 64
    pointer = (
        "version https://git-lfs.github.com/spec/v1\n"
        f"oid sha256:{digest}\n"
        "size 42\n"
    )

    match = tool.POINTER_RE.fullmatch(pointer)

    assert match is not None
    assert match.groups() == (digest, "42")


def test_download_one_reuses_verified_destination(tmp_path: Path) -> None:
    payload = b"official-audio-object"
    digest = hashlib.sha256(payload).hexdigest()
    destination = tmp_path / "meeting.mp3"
    destination.write_bytes(payload)
    item = {
        "path": "earnings22/media/meeting.mp3",
        "lfs_oid_sha256": digest,
        "size_bytes": len(payload),
    }

    name, status = tool._download_one(item, {}, tmp_path)

    assert name == "meeting.mp3"
    assert status == "verified-existing"


def test_download_one_rejects_wrong_existing_object(tmp_path: Path) -> None:
    import pytest

    destination = tmp_path / "meeting.mp3"
    destination.write_bytes(b"wrong")
    item = {
        "path": "earnings22/media/meeting.mp3",
        "lfs_oid_sha256": hashlib.sha256(b"expected").hexdigest(),
        "size_bytes": len(b"expected"),
    }

    with pytest.raises(RuntimeError, match="does not match inventory"):
        tool._download_one(item, {}, tmp_path)
