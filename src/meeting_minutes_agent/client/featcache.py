"""Per-dataset feature-cache directory routing for the llama.cpp mtmd
feature-cache patch.

Lineage: reimplements, small, the per-dataset naming convention documented
in the SAEA study's ``docs/featcache-directories.md`` (studies/speech-aware-
evidence-acquisition, umbrella commit range including ``12590d4``): a
persistent, on-disk cache of audio-chunk encoder embeddings, keyed off the
environment variable ``LLAMA_MTMD_FEAT_CACHE_DIR`` read by the spawned
``llama-server`` process itself (that variable name is fixed by the C++
patch, not by either repository, and is therefore reused verbatim here).
Cache entries are mmproj-encoder-specific: a cached embedding was produced
by one specific encoder and is only ever valid for a server running that
same encoder, so the directory convention is ``<root>/<dataset>-<encoder>/``
-- one directory per (dataset, encoder) pair, never shared across datasets.

Divergence from the SAEA original (deliberate, not an oversight): SAEA
carries one legacy exception, the already-warm ``q4km`` directory with no
dataset segment, and its resolver silently defaults to it when unset. This
repository has no warm cache of its own to default to, and reusing that
exact literal path (or writing underneath it) would mix a fresh campaign's
embeddings into -- and risk corrupting -- another study's 26GB, already-
scored cache. There is therefore no default fallback here: resolution is
per-dataset and mandatory (:func:`campaign_cache_dir` requires both
``dataset`` and ``encoder``), and the SAEA legacy path is a hard refusal,
never a valid target, however a caller's dataset/encoder/root arguments
combine to reach it.
"""

from __future__ import annotations

import os
from pathlib import Path

# Read by the spawned llama-server process itself (the llama.cpp mtmd
# feature-cache patch) -- this name is fixed by that patch, not by this
# repository, and must be reused verbatim for the cache to take effect.
SERVER_ENV_VAR = "LLAMA_MTMD_FEAT_CACHE_DIR"

# This repository's own override knob for the cache root (mirrors SAEA's
# SAEA_FEAT_CACHE_DIR, renamed to this repository's own prefix): unset means
# the default root below.
ROOT_ENV_VAR = "MMA_FEAT_CACHE_ROOT"
DEFAULT_ROOT = "/home/chao/feat-cache"

# The SAEA study's legacy, dataset-segment-less directory -- a hard refusal
# here (module docstring): this repository must never write to, or under,
# another study's already-warm cache.
LEGACY_Q4KM_DIRNAME = "q4km"
LEGACY_Q4KM_PATH = Path(f"{DEFAULT_ROOT}/{LEGACY_Q4KM_DIRNAME}")


class FeatCacheError(RuntimeError):
    """Fail-closed refusal: an invalid dataset/encoder, or a resolved
    directory that is, or is nested under, the legacy SAEA q4km cache."""


def _root(root: str | Path | None) -> Path:
    if root is not None:
        return Path(root)
    override = os.environ.get(ROOT_ENV_VAR)
    return Path(override) if override else Path(DEFAULT_ROOT)


def _assert_not_legacy(directory: Path, dataset: str) -> None:
    if dataset.strip().lower() == LEGACY_Q4KM_DIRNAME:
        raise FeatCacheError(
            f"dataset {dataset!r} refused: {LEGACY_Q4KM_DIRNAME!r} names the SAEA study's "
            "legacy, already-warm cache directory, never a new campaign's dataset segment"
        )
    resolved = directory.resolve() if directory.is_absolute() else directory
    legacy = LEGACY_Q4KM_PATH.resolve() if LEGACY_Q4KM_PATH.is_absolute() else LEGACY_Q4KM_PATH
    if resolved == legacy or legacy in resolved.parents:
        raise FeatCacheError(
            f"refused: {directory} is, or is nested under, the SAEA study's legacy feature-cache "
            f"directory {LEGACY_Q4KM_PATH}; this repository must never write there"
        )


def campaign_cache_dir(
    dataset: str, encoder: str, *, root: str | Path | None = None, create: bool = True
) -> Path:
    """Resolve (and by default create) this campaign's feature-cache
    directory: ``<root>/<dataset>-<encoder>/``.

    ``root`` defaults to ``ROOT_ENV_VAR`` if set, else :data:`DEFAULT_ROOT`.
    Refuses (fail-closed, :class:`FeatCacheError`) a ``dataset`` literally
    named ``"q4km"`` and any resolution that lands on or under the legacy
    SAEA path, regardless of how ``dataset``/``encoder``/``root`` combine to
    reach it.
    """

    if not isinstance(dataset, str) or not dataset.strip():
        raise FeatCacheError(f"dataset must be a non-empty string, got {dataset!r}")
    if not isinstance(encoder, str) or not encoder.strip():
        raise FeatCacheError(f"encoder must be a non-empty string, got {encoder!r}")
    resolved_root = _root(root)
    directory = resolved_root / f"{dataset}-{encoder}"
    _assert_not_legacy(directory, dataset)
    if create:
        directory.mkdir(parents=True, exist_ok=True)
    return directory


def server_env(
    dataset: str, encoder: str, *, root: str | Path | None = None, create: bool = True
) -> dict[str, str]:
    """The ``server_env`` fragment a caller merges into a spawned
    ``llama-server`` process's environment: ``{SERVER_ENV_VAR: <resolved
    directory>}``. Thin wrapper over :func:`campaign_cache_dir` -- the single
    place that names the environment variable the llama.cpp patch actually
    reads."""

    directory = campaign_cache_dir(dataset, encoder, root=root, create=create)
    return {SERVER_ENV_VAR: str(directory)}
