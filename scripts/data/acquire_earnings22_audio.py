#!/usr/bin/env python3
"""Acquire and verify the official Earnings-22 Git LFS audio objects.

Corpus bytes are written only below an explicit data root, never in the checkout.
The upstream repository does not state an audio license as clearly as it states the
CC BY-SA 4.0 terms for associated text, so this command requires an explicit
internal-research-only acknowledgement.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request


SOURCE_REPOSITORY = "revdotcom/speech-datasets"
SOURCE_COMMIT = "c05ab6fd8b4b627d123c922a22a39e993dd37635"
SOURCE_DIRECTORY = "earnings22/media"
LFS_BATCH_URL = (
    "https://github.com/revdotcom/speech-datasets.git/info/lfs/objects/batch"
)
POINTER_RE = re.compile(
    r"\Aversion https://git-lfs.github.com/spec/v1\n"
    r"oid sha256:([0-9a-f]{64})\nsize ([0-9]+)\n?\Z"
)
PRINT_LOCK = threading.Lock()


def _gh_json(*args: str) -> object:
    process = subprocess.run(
        ["gh", "api", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return json.loads(process.stdout)


def build_inventory() -> dict[str, object]:
    owner, name = SOURCE_REPOSITORY.split("/", 1)
    expression = f"{SOURCE_COMMIT}:{SOURCE_DIRECTORY}"
    query = """
query($owner: String!, $name: String!, $expression: String!) {
  repository(owner: $owner, name: $name) {
    object(expression: $expression) {
      ... on Tree {
        entries {
          name
          oid
          object { ... on Blob { text byteSize } }
        }
      }
    }
  }
}
"""
    response = _gh_json(
        "graphql",
        "-f",
        f"query={query}",
        "-F",
        f"owner={owner}",
        "-F",
        f"name={name}",
        "-F",
        f"expression={expression}",
    )
    entries = response["data"]["repository"]["object"]["entries"]  # type: ignore[index]
    objects: list[dict[str, object]] = []
    for entry in entries:
        match = POINTER_RE.fullmatch(entry["object"]["text"])
        if match is None:
            raise RuntimeError(f"not a canonical Git LFS pointer: {entry['name']}")
        objects.append(
            {
                "path": f"{SOURCE_DIRECTORY}/{entry['name']}",
                "blob_oid": entry["oid"],
                "lfs_oid_sha256": match.group(1),
                "size_bytes": int(match.group(2)),
            }
        )
    objects.sort(key=lambda item: str(item["path"]))
    return {
        "schema": "earnings22-audio-inventory-v1",
        "source_repository": SOURCE_REPOSITORY,
        "source_commit": SOURCE_COMMIT,
        "source_directory": SOURCE_DIRECTORY,
        "object_count": len(objects),
        "total_size_bytes": sum(int(item["size_bytes"]) for item in objects),
        "license_handling": (
            "Internal research only; do not redistribute audio. Upstream text license "
            "does not unambiguously establish the audio license."
        ),
        "objects": objects,
    }


def _post_lfs_batch(objects: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    payload = {
        "operation": "download",
        "transfers": ["basic"],
        "objects": [
            {"oid": item["lfs_oid_sha256"], "size": item["size_bytes"]}
            for item in objects
        ],
    }
    request = urllib.request.Request(
        LFS_BATCH_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/vnd.git-lfs+json",
            "Content-Type": "application/vnd.git-lfs+json",
            "User-Agent": "meeting-minutes-agent-earnings22-acquirer/1",
        },
        method="POST",
    )
    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                result = json.load(response)
            break
        except (OSError, TimeoutError, urllib.error.URLError):
            if attempt == 5:
                raise
            time.sleep(2 ** (attempt - 1))
    return {item["oid"]: item for item in result["objects"]}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download_one(
    item: dict[str, object], action: dict[str, object], media_dir: Path
) -> tuple[str, str]:
    name = Path(str(item["path"])).name
    destination = media_dir / name
    partial = destination.with_suffix(destination.suffix + ".part")
    expected_size = int(item["size_bytes"])
    expected_hash = str(item["lfs_oid_sha256"])

    if destination.exists():
        if destination.stat().st_size == expected_size and _sha256(destination) == expected_hash:
            return name, "verified-existing"
        raise RuntimeError(f"existing destination does not match inventory: {destination}")

    if partial.exists() and partial.stat().st_size == expected_size:
        if _sha256(partial) == expected_hash:
            partial.replace(destination)
            return name, "recovered-and-verified"
        partial.unlink()

    for attempt in range(1, 6):
        try:
            offset = partial.stat().st_size if partial.exists() else 0
            if offset > expected_size:
                raise RuntimeError(f"partial file is larger than expected: {partial}")
            headers = dict(action.get("header", {}))
            if offset:
                headers["Range"] = f"bytes={offset}-"
            request = urllib.request.Request(str(action["href"]), headers=headers)
            with urllib.request.urlopen(request, timeout=120) as response:
                append = offset > 0 and response.status == 206
                mode = "ab" if append else "wb"
                with partial.open(mode) as handle:
                    while True:
                        block = response.read(8 * 1024 * 1024)
                        if not block:
                            break
                        handle.write(block)
            if partial.stat().st_size == expected_size:
                break
        except (OSError, TimeoutError, urllib.error.URLError):
            if attempt == 5:
                raise
        if attempt == 5:
            break
        time.sleep(2 ** (attempt - 1))

    if partial.stat().st_size != expected_size:
        raise RuntimeError(
            f"size mismatch for {name}: {partial.stat().st_size} != {expected_size}"
        )
    actual_hash = _sha256(partial)
    if actual_hash != expected_hash:
        raise RuntimeError(f"SHA-256 mismatch for {name}: {actual_hash} != {expected_hash}")
    partial.replace(destination)
    return name, "downloaded-and-verified"


def acquire(inventory: dict[str, object], media_dir: Path, jobs: int) -> None:
    media_dir.mkdir(parents=True, exist_ok=True)
    objects = list(inventory["objects"])  # type: ignore[arg-type]
    for start in range(0, len(objects), 20):
        chunk = objects[start : start + 20]
        actions = _post_lfs_batch(chunk)
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
            futures = {}
            for item in chunk:
                oid = str(item["lfs_oid_sha256"])
                remote = actions.get(oid)
                if remote is None or "error" in remote or "download" not in remote.get("actions", {}):
                    raise RuntimeError(f"LFS server did not supply object {oid}: {remote}")
                action = remote["actions"]["download"]  # type: ignore[index]
                future = executor.submit(_download_one, item, action, media_dir)
                futures[future] = item
            for future in concurrent.futures.as_completed(futures):
                name, status = future.result()
                with PRINT_LOCK:
                    print(f"[{start + 1:03d}-{start + len(chunk):03d}] {status}: {name}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(os.environ["SPEECHRL_DATA_DIR"])
        if "SPEECHRL_DATA_DIR" in os.environ
        else None,
        help="External data root; defaults to SPEECHRL_DATA_DIR.",
    )
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument(
        "--acknowledge-internal-research-only",
        action="store_true",
        help="Required because the upstream audio license is not explicit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.data_root is None:
        raise SystemExit("--data-root or SPEECHRL_DATA_DIR is required")
    if not args.acknowledge_internal_research_only:
        raise SystemExit("pass --acknowledge-internal-research-only")
    if not 1 <= args.jobs <= 8:
        raise SystemExit("--jobs must be between 1 and 8")

    dataset_dir = args.data_root.resolve() / "datasets" / "earnings22"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = dataset_dir / ".upstream-audio-manifest.json"
    inventory = build_inventory()
    inventory_path.write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"inventory: {inventory['object_count']} objects, "
        f"{inventory['total_size_bytes']} bytes -> {inventory_path}",
        flush=True,
    )
    if not args.inventory_only:
        acquire(inventory, dataset_dir / "media", args.jobs)
        print("all audio objects downloaded and SHA-256 verified", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
