#!/usr/bin/env python3
"""Header-only reachability check for frozen LHCP material URLs."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests


def check_one(item: dict[str, Any]) -> dict[str, Any]:
    result = {
        "audio_path": item["audio_path"],
        "filename": item["filename"],
        "url": item["download_url"],
        "expected_bytes": int(item["size"]),
        "body_bytes_read": 0,
    }
    for attempt in range(1, 4):
        try:
            response = requests.head(item["download_url"], allow_redirects=True, timeout=60)
            probe_method = "HEAD"
            if not 200 <= response.status_code < 400:
                response.close()
                response = requests.get(
                    item["download_url"],
                    headers={"Range": "bytes=0-0"},
                    allow_redirects=True,
                    stream=True,
                    timeout=60,
                )
                probe_method = "GET_RANGE_0_0_HEADERS_ONLY"
            content_range = response.headers.get("content-range")
            total_from_range = None
            if content_range and "/" in content_range and content_range.rsplit("/", 1)[1].isdigit():
                total_from_range = int(content_range.rsplit("/", 1)[1])
            result.update(
                {
                    "attempts": attempt,
                    "probe_method": probe_method,
                    "status_code": response.status_code,
                    "final_url": response.url,
                    "content_length": (
                        int(response.headers["content-length"])
                        if response.headers.get("content-length", "").isdigit()
                        else None
                    ),
                    "content_range": content_range,
                    "total_bytes_from_range": total_from_range,
                    "content_type": response.headers.get("content-type"),
                    "error": None,
                }
            )
            response.close()
            break
        except requests.RequestException as exc:
            result.update(
                {
                    "attempts": attempt,
                    "status_code": None,
                    "final_url": None,
                    "content_length": None,
                    "content_type": None,
                    "error": type(exc).__name__,
                }
            )
    result["reachable"] = result["status_code"] is not None and 200 <= result["status_code"] < 400
    observed_size = result.get("total_bytes_from_range") or result.get("content_length")
    result["size_matches"] = observed_size in (None, result["expected_bytes"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError(f"output exists: {args.out}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    selected = [
        {"audio_path": row["audio_path"], **material}
        for row in manifest["items"]
        for material in row["materials"]
    ]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(check_one, selected))
    reachable = sum(row["reachable"] for row in rows)
    size_matches = sum(row["size_matches"] for row in rows)
    receipt = {
        "schema": "material-lhcp-endpoint-receipt-v1",
        "manifest_sha256": __import__("hashlib").sha256(args.manifest.read_bytes()).hexdigest(),
        "method": "HEAD; on rejection, GET Range bytes=0-0 headers only; response bodies were not read",
        "counts": {
            "endpoints": len(rows),
            "reachable": reachable,
            "size_matches_or_header_absent": size_matches,
            "body_bytes_read": 0,
        },
        "rows": rows,
        "verdict": "ENDPOINTS_REACHABLE" if reachable == len(rows) else "ENDPOINT_CHECK_INCOMPLETE",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"verdict": receipt["verdict"], "counts": receipt["counts"]}, indent=2))
    return 0 if reachable == len(rows) else 3


if __name__ == "__main__":
    raise SystemExit(main())
