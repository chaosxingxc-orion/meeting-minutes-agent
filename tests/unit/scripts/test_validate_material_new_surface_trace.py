"""Tests for material trace sidecar validation."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import numpy as np


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "validate_material_new_surface_trace.py"
_SPEC = importlib.util.spec_from_file_location("validate_material_new_surface_trace", _SCRIPT)
assert _SPEC and _SPEC.loader
tool = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tool)


def test_vector_sidecar_binds_exact_array(tmp_path: Path) -> None:
    vectors = np.asarray([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)
    path = tmp_path / "vectors.npz"
    np.savez(path, keys=vectors)
    binding = {
        "relative_path": "vectors.npz",
        "sha256": tool.sha256_file(path),
        "bytes": path.stat().st_size,
        "array_key": "keys",
        "vector_sha256": hashlib.sha256(vectors.tobytes(order="C")).hexdigest(),
        "dimension": 2,
    }
    assert tool.validate_vector_artifact(
        tmp_path, binding, "keys", expected_rows=2, expected_dtype="float32"
    ) == []


def test_vector_sidecar_rejects_array_hash_drift(tmp_path: Path) -> None:
    vectors = np.asarray([0.1, 0.2], dtype=np.float32)
    path = tmp_path / "vectors.npz"
    np.savez(path, query=vectors)
    binding = {
        "relative_path": "vectors.npz",
        "sha256": tool.sha256_file(path),
        "bytes": path.stat().st_size,
        "array_key": "query",
        "vector_sha256": "0" * 64,
        "dimension": 2,
    }
    errors = tool.validate_vector_artifact(
        tmp_path, binding, "query", expected_rows=1, expected_dtype="float32"
    )
    assert errors == ["query vector sha256 mismatch"]
