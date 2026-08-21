#!/usr/bin/env python3
"""Launch the registered C-CTX five-arm capability smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget  # noqa: E402
from meeting_minutes_agent.client.receipts import FlightReceipt, ModelFileRef, ServerIdentity  # noqa: E402
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig  # noqa: E402
from meeting_minutes_agent.probes.contextasr import build_requests, load_manifest  # noqa: E402


def _load_done(path: Path) -> set[str]:
    done: set[str] = set()
    if not path.is_file():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if record.get("outcome") == "ok" and isinstance(record.get("request_id"), str):
            done.add(record["request_id"])
    return done


def _append(handle, record: dict[str, object]) -> None:
    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def _materialize_audio(manifest, directory: Path) -> dict[str, Path]:
    by_tar: dict[str, list] = {}
    for entry in manifest.entries:
        by_tar.setdefault(entry.source_tar, []).append(entry)
    paths: dict[str, Path] = {}
    for tar_path, entries in by_tar.items():
        with tarfile.open(tar_path, "r") as archive:
            for entry in entries:
                source = archive.extractfile(entry.tar_member)
                if source is None:
                    raise RuntimeError(f"unreadable tar member: {entry.tar_member}")
                data = source.read()
                actual = hashlib.sha256(data).hexdigest()
                if actual != entry.audio_sha256:
                    raise RuntimeError(
                        f"audio hash mismatch for {entry.uniq_id}: expected {entry.audio_sha256}, got {actual}"
                    )
                target = directory / f"{entry.uniq_id}.wav"
                target.write_bytes(data)
                paths[entry.uniq_id] = target
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model-path")
    parser.add_argument("--model-sha256")
    parser.add_argument("--mmproj-path")
    parser.add_argument("--mmproj-sha256")
    parser.add_argument("--responses-out")
    parser.add_argument("--receipt-out")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--slots", type=int, default=1)
    parser.add_argument("--max-calls", type=int, default=160)
    parser.add_argument("--max-audio-seconds", type=float, default=7200.0)
    parser.add_argument("--progress-every", type=int, default=10)
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest)
    requests = build_requests(manifest)
    summary = {
        "manifest_hash": manifest.content_hash,
        "samples": len(manifest.entries),
        "requests": len(requests),
        "audio_seconds": sum(request.entry.duration for request in requests),
        "per_arm": {arm: sum(request.arm == arm for request in requests) for arm in sorted({r.arm for r in requests})},
    }
    if args.summary_only:
        print(json.dumps(summary, indent=2))
        return 0

    required = {
        "model_path": args.model_path,
        "model_sha256": args.model_sha256,
        "mmproj_path": args.mmproj_path,
        "mmproj_sha256": args.mmproj_sha256,
        "responses_out": args.responses_out,
        "receipt_out": args.receipt_out,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        parser.error("flight mode requires: " + ", ".join("--" + name.replace("_", "-") for name in missing))

    response_path = Path(args.responses_out)
    if response_path.exists() and not args.resume:
        parser.error(f"responses file already exists; pass --resume or choose another path: {response_path}")
    response_path.parent.mkdir(parents=True, exist_ok=True)
    done = _load_done(response_path) if args.resume else set()
    remaining = [request for request in requests if request.request_id not in done]
    budget = CallBudget(BudgetLimits(max_calls=args.max_calls, max_audio_seconds=args.max_audio_seconds))
    identity = ServerIdentity(
        base_url=args.base_url,
        model_files=(
            ModelFileRef(path=args.model_path, sha256=args.model_sha256),
            ModelFileRef(path=args.mmproj_path, sha256=args.mmproj_sha256),
        ),
        slots=args.slots,
    )
    transport = LlamaServerTransport(
        TransportConfig(base_url=args.base_url, slots=args.slots, max_retries=0, timeout_seconds=300), budget
    )
    receipt = FlightReceipt(identity, budget)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="cctx-") as temp, response_path.open("a", encoding="utf-8") as sink:
        audio_paths = _materialize_audio(manifest, Path(temp))
        for index, request in enumerate(remaining, start=1):
            kwargs = request.head_request.to_transport_kwargs(
                request_id=request.request_id,
                audio_path=audio_paths[request.entry.uniq_id],
                audio_seconds=request.entry.duration,
            )
            kwargs["decoding_params"] = {"temperature": 0, "seed": 0, "max_tokens": 1024}
            try:
                response = transport.request(**kwargs)
            except Exception as error:  # noqa: BLE001
                _append(
                    sink,
                    {
                        **request.to_dict(),
                        "outcome": "error",
                        "error_type": type(error).__name__,
                        "error": str(error),
                        "recorded_utc": datetime.now(timezone.utc).isoformat(),
                    },
                )
                raise
            receipt.record(response)
            _append(
                sink,
                {
                    **request.to_dict(),
                    "outcome": "ok",
                    "text": response.text,
                    "usage": dict(response.usage),
                    "attempts": [attempt.as_json() for attempt in response.attempts],
                    "recorded_utc": datetime.now(timezone.utc).isoformat(),
                },
            )
            if args.progress_every and index % args.progress_every == 0:
                elapsed = time.monotonic() - started
                print(f"C-CTX {index}/{len(remaining)} new requests; {elapsed:.1f}s", file=sys.stderr, flush=True)
    receipt.write(args.receipt_out, repo_root=Path(__file__).resolve().parent.parent, run_id="cctx-32-v1")
    print(json.dumps({**summary, "skipped": len(done), "flown": len(remaining), "receipt": args.receipt_out}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
