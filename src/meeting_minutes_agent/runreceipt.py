"""Minimal run-receipt helper.

A run receipt is a small JSON provenance record for one engineering or
analysis run: a run id, a hash of the run's config, the git commit the code
was run at, and timestamps. This is deliberately lean -- it does not import
the speech-aware-evidence-acquisition study's exposure-ledger/contract
apparatus (out of scope for this repository; see CLAUDE.md "Fresh start").

Typical use::

    from meeting_minutes_agent.runreceipt import write_run_receipt

    config = {"corpus": "ami", "meeting_id": "ES2002a"}
    write_run_receipt(Path("out/run-receipt.json"), config, repo_root=Path("."))
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def _canonical_json(value: Any) -> str:
    """Deterministic JSON serialization used for hashing: sorted keys, fixed
    separators, ASCII-safe. The same config always hashes the same way
    regardless of dict insertion order."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def config_hash(config: Mapping[str, Any]) -> str:
    """SHA-256 hex digest of the canonical JSON form of ``config``."""

    import hashlib

    return hashlib.sha256(_canonical_json(config).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GitState:
    commit: str | None
    dirty: bool | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"commit": self.commit, "dirty": self.dirty, "error": self.error}


def read_git_state(repo_root: Path | str | None = None) -> GitState:
    """Best-effort git commit + dirty-tree read. Never raises: a receipt must
    still be written in an environment without git or outside a repo, with
    the failure recorded in ``error`` rather than losing the whole receipt."""

    import subprocess

    root = Path(repo_root) if repo_root is not None else Path.cwd()
    try:
        commit_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if commit_proc.returncode != 0:
            return GitState(commit=None, dirty=None, error=commit_proc.stderr.strip() or "git rev-parse failed")
        commit = commit_proc.stdout.strip()

        status_proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        dirty = bool(status_proc.stdout.strip()) if status_proc.returncode == 0 else None
        return GitState(commit=commit, dirty=dirty)
    except OSError as exc:  # git not installed / not runnable
        return GitState(commit=None, dirty=None, error=str(exc))


@dataclass(frozen=True)
class RunReceipt:
    run_id: str
    config: Mapping[str, Any]
    config_hash: str
    git: GitState
    created_utc: str
    extra: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "config": dict(self.config),
            "config_hash": self.config_hash,
            "git": self.git.to_dict(),
            "created_utc": self.created_utc,
            "extra": dict(self.extra),
        }


def build_run_receipt(
    config: Mapping[str, Any],
    *,
    repo_root: Path | str | None = None,
    run_id: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> RunReceipt:
    """Build a :class:`RunReceipt` without writing it. ``run_id`` defaults to
    a fresh UUID4 hex; pass one explicitly for a deterministic/reproduced
    run id (e.g. reusing the id of the run this one repeats)."""

    return RunReceipt(
        run_id=run_id or uuid.uuid4().hex,
        config=dict(config),
        config_hash=config_hash(config),
        git=read_git_state(repo_root),
        created_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        extra=dict(extra or {}),
    )


def write_run_receipt(
    path: Path | str,
    config: Mapping[str, Any],
    *,
    repo_root: Path | str | None = None,
    run_id: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> Path:
    """Build a run receipt and write it as pretty-printed JSON to ``path``,
    creating parent directories as needed. Returns ``path``."""

    receipt = build_run_receipt(config, repo_root=repo_root, run_id=run_id, extra=extra)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out
