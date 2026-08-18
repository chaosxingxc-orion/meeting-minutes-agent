#!/usr/bin/env python3
"""Verify locally downloaded meeting datasets against scripts/data/datasets.lock.json.

Stdlib-only (Python >= 3.12), offline: this script never downloads anything and never
contacts the network. It only reads the meeting lock and the local filesystem under
``$SPEECHRL_DATA_DIR/datasets/<local_subdir>``.

For each requested dataset it prints one of:

  PASS      the dataset is present and everything this lock can check matches.
  MISSING   the dataset's local_subdir does not exist (or exists but is empty).
  MISMATCH  the dataset is present but fails a size/count/hash check.

Exit code is 0 only if every requested dataset PASSes; 1 otherwise (including when
SPEECHRL_DATA_DIR is unset, since nothing can be verified without a data root).

Usage::

    python scripts/data/verify.py --help
    python scripts/data/verify.py                     # verify all six datasets
    python scripts/data/verify.py --dataset ami-meeting-corpus
    python scripts/data/verify.py --dataset ami-meeting-corpus --dataset qmsum
    python scripts/data/verify.py --quiet              # table only, no per-check detail
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOCK_PATH = Path(__file__).resolve().parent / "datasets.lock.json"

# A real download can legitimately land a few bytes off the lock's recorded total (e.g.
# filesystem block rounding reported by some tools, or an upstream re-serving a file with
# a trivially different byte count). This tolerance only softens the total-size check;
# file-count and hash checks stay exact.
SIZE_TOLERANCE_BYTES = 4096


@dataclass
class CheckResult:
    ok: bool
    detail: str


@dataclass
class DatasetReport:
    name: str
    status: str  # PASS | MISSING | MISMATCH
    checks: list[CheckResult] = field(default_factory=list)


def load_lock(path: Path = LOCK_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _iter_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return [p for p in root.rglob("*") if p.is_file()]


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _md5_of(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_hash(root: Path, rel_path: str, spec: Any) -> CheckResult:
    """spec is either a hex-string SHA-256, or {"algorithm": ..., "value": ...}."""
    target = root / rel_path
    if not target.is_file():
        return CheckResult(False, f"hash target missing: {rel_path}")
    if isinstance(spec, str):
        algorithm, expected = "sha256", spec
    else:
        algorithm, expected = spec.get("algorithm", "sha256"), spec["value"]
    actual = _sha256_of(target) if algorithm == "sha256" else _md5_of(target)
    if actual.lower() != expected.lower():
        return CheckResult(
            False,
            f"{rel_path}: {algorithm} mismatch (expected {expected}, got {actual})",
        )
    return CheckResult(True, f"{rel_path}: {algorithm} OK")


def verify_dataset(entry: dict[str, Any], data_root: Path) -> DatasetReport:
    name = entry["name"]
    root = data_root / entry["local_subdir"]
    checks: list[CheckResult] = []

    files = _iter_files(root)
    if not root.is_dir() or not files:
        return DatasetReport(name=name, status="MISSING", checks=checks)

    verification = entry.get("verification", {})
    ok = True

    # File count (top-level "expected_file_count", or the meetingbank-shaped split fields).
    # Checked as "at least" the expected count/size, not exact equality: a real download
    # may legitimately carry extra local bookkeeping (a setup.sh receipt, VCS metadata for
    # git-sourced datasets, etc.) on top of the payload the lock enumerates. Under-counting
    # still fails, which is what actually indicates an incomplete/partial download.
    expected_count = verification.get("expected_file_count")
    if expected_count is not None:
        actual_count = len(files)
        passed = actual_count >= expected_count
        ok &= passed
        checks.append(
            CheckResult(
                passed,
                f"file count: expected >= {expected_count}, found {actual_count}",
            )
        )

    # Total size (meetingbank splits text-layer vs audio-subset instead of one total).
    expected_size = verification.get("expected_total_size_bytes")
    if expected_size is not None:
        actual_size = sum(p.stat().st_size for p in files)
        passed = actual_size + SIZE_TOLERANCE_BYTES >= expected_size
        ok &= passed
        checks.append(
            CheckResult(
                passed,
                f"total size: expected >= {expected_size}, found {actual_size} "
                f"(tolerance {SIZE_TOLERANCE_BYTES})",
            )
        )

    # meetingbank-shaped: separate text-layer / audio-subset size+count checks (its audio is a
    # deliberately bounded subset, so it is verified as two sub-trees rather than one total).
    expected_text_count = verification.get("expected_text_layer_file_count")
    expected_text_size = verification.get("expected_text_layer_size_bytes")
    if expected_text_count is not None or expected_text_size is not None:
        text_files = _iter_files(root / "text")
        if expected_text_count is not None:
            passed = len(text_files) >= expected_text_count
            ok &= passed
            checks.append(
                CheckResult(passed, f"text layer file count: expected >= {expected_text_count}, found {len(text_files)}")
            )
        if expected_text_size is not None:
            actual = sum(p.stat().st_size for p in text_files)
            passed = actual + SIZE_TOLERANCE_BYTES >= expected_text_size
            ok &= passed
            checks.append(
                CheckResult(passed, f"text layer size: expected >= {expected_text_size}, found {actual}")
            )

    expected_archive_count = verification.get("expected_audio_subset_archives")
    expected_audio_size = verification.get("expected_audio_subset_size_bytes")
    if expected_archive_count is not None or expected_audio_size is not None:
        audio_subset = root / "audio-subset"
        archives = list((audio_subset / "archives").glob("*")) if (audio_subset / "archives").is_dir() else []
        audio_files = _iter_files(audio_subset)
        if expected_archive_count is not None:
            passed = len(archives) >= expected_archive_count
            ok &= passed
            checks.append(
                CheckResult(passed, f"audio subset archive count: expected >= {expected_archive_count}, found {len(archives)}")
            )
        if expected_audio_size is not None:
            actual = sum(p.stat().st_size for p in audio_files)
            passed = actual + SIZE_TOLERANCE_BYTES >= expected_audio_size
            ok &= passed
            checks.append(
                CheckResult(passed, f"audio subset size: expected >= {expected_audio_size}, found {actual}")
            )

    # Per-file hashes, where the meeting lock has them.
    for rel_path, spec in verification.get("hashes", {}).items():
        result = _check_hash(root, rel_path, spec)
        ok &= result.ok
        checks.append(result)

    # git HEAD, for git-sourced datasets (meetingqa, qmsum).
    expected_head = verification.get("expected_git_head")
    if expected_head is not None:
        head_file = root / ".git" / "HEAD"
        actual_head = None
        if head_file.is_file():
            ref = head_file.read_text(encoding="utf-8").strip()
            if ref.startswith("ref:"):
                ref_path = root / ".git" / ref.split(" ", 1)[1]
                if ref_path.is_file():
                    actual_head = ref_path.read_text(encoding="utf-8").strip()
            else:
                actual_head = ref
        passed = actual_head == expected_head
        ok &= passed
        checks.append(
            CheckResult(passed, f"git HEAD: expected {expected_head}, found {actual_head}")
        )

    return DatasetReport(name=name, status="PASS" if ok else "MISMATCH", checks=checks)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify locally downloaded meeting datasets against "
            "scripts/data/datasets.lock.json (offline, stdlib-only)."
        ),
    )
    parser.add_argument(
        "--dataset",
        action="append",
        dest="datasets",
        metavar="NAME",
        help="verify only this dataset (repeatable); default is all six",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="print only the summary table, not per-check detail",
    )
    parser.add_argument(
        "--data-root",
        metavar="PATH",
        help="override the data root instead of reading SPEECHRL_DATA_DIR",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    data_root_str = args.data_root or os.environ.get("SPEECHRL_DATA_DIR")
    if not data_root_str:
        print(
            "verify.py: SPEECHRL_DATA_DIR is not set and --data-root was not given.\n"
            "Set it to your data root, e.g.:\n"
            "  export SPEECHRL_DATA_DIR=/path/to/your/data-root",
            file=sys.stderr,
        )
        return 1
    data_root = Path(data_root_str)

    lock = load_lock()
    entries = {e["name"]: e for e in lock["datasets"]}

    wanted = args.datasets or list(entries.keys())
    unknown = [n for n in wanted if n not in entries]
    if unknown:
        print(f"verify.py: unknown dataset name(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"Known datasets: {', '.join(entries.keys())}", file=sys.stderr)
        return 1

    reports = [verify_dataset(entries[name], data_root) for name in wanted]

    if not args.quiet:
        for report in reports:
            print(f"\n== {report.name} ({report.status}) ==")
            for check in report.checks:
                mark = "ok" if check.ok else "FAIL"
                print(f"  [{mark}] {check.detail}")

    print(f"\n{'NAME':<22} {'STATUS':<10}")
    for report in reports:
        print(f"{report.name:<22} {report.status:<10}")

    return 0 if all(r.status == "PASS" for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
