#!/usr/bin/env python3
"""Launch the frozen two-arm E4-DISJOINT-DIR second pass."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget  # noqa: E402
from meeting_minutes_agent.client.receipts import FlightReceipt, ModelFileRef, ServerIdentity  # noqa: E402
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig  # noqa: E402
from meeting_minutes_agent.probes.e4_disjoint_direction import build_requests, load_runtime_binding  # noqa: E402


def _append(handle, record: dict[str, object]) -> None:
    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def _source(target, directory: Path) -> Path:
    with tarfile.open(target.source_tar, "r") as archive:
        stream = archive.extractfile(target.tar_member)
        if stream is None:
            raise RuntimeError(f"unreadable audio: {target.uniq_id}")
        data = stream.read()
    if hashlib.sha256(data).hexdigest() != target.audio_sha256:
        raise RuntimeError(f"audio hash mismatch: {target.uniq_id}")
    path = directory / f"{target.uniq_id}.wav"
    path.write_bytes(data)
    return path


def _clip(source: Path, target: Path, start: float, end: float) -> None:
    import soundfile as sf

    audio, rate = sf.read(source, dtype="float32", always_2d=True)
    sf.write(target, audio[round(start * rate) : round(end * rate)], rate, subtype="PCM_16")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", required=True)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model-path")
    parser.add_argument("--model-sha256")
    parser.add_argument("--mmproj-path")
    parser.add_argument("--mmproj-sha256")
    parser.add_argument("--responses-out")
    parser.add_argument("--receipt-out")
    parser.add_argument("--max-calls", type=int)
    parser.add_argument("--max-audio-seconds", type=float)
    args = parser.parse_args(argv)
    binding = load_runtime_binding(args.binding)
    requests = build_requests(binding)
    calls = len(requests)
    audio_seconds = sum(request.target.duration for request in requests)
    summary = {"binding_hash": binding.content_hash, "targets": len(binding.targets), "calls": calls, "audio_seconds": audio_seconds}
    if args.summary_only:
        print(json.dumps(summary, indent=2))
        return 0
    required = (args.model_path, args.model_sha256, args.mmproj_path, args.mmproj_sha256, args.responses_out, args.receipt_out)
    if not all(required):
        parser.error("flight identities and outputs required")
    if args.max_calls != calls:
        parser.error(f"max-calls must equal frozen request count {calls}")
    if args.max_audio_seconds is None or abs(args.max_audio_seconds - audio_seconds) > 1e-6:
        parser.error(f"max-audio-seconds must equal frozen audio seconds {audio_seconds:.9f}")
    responses_out = Path(args.responses_out)
    receipt_out = Path(args.receipt_out)
    if responses_out.exists() or receipt_out.exists():
        parser.error("flight output exists; refusing overwrite")
    responses_out.parent.mkdir(parents=True, exist_ok=True)
    budget = CallBudget(BudgetLimits(max_calls=calls, max_audio_seconds=audio_seconds))
    identity = ServerIdentity(
        args.base_url,
        (
            ModelFileRef(args.model_path, args.model_sha256),
            ModelFileRef(args.mmproj_path, args.mmproj_sha256),
        ),
        1,
    )
    transport = LlamaServerTransport(
        TransportConfig(base_url=args.base_url, slots=1, max_retries=0, timeout_seconds=300),
        budget,
    )
    receipt = FlightReceipt(identity, budget)
    with tempfile.TemporaryDirectory(prefix="e4dir-") as temp, responses_out.open("x", encoding="utf-8") as sink:
        directory = Path(temp)
        current = None
        source = None
        clips: dict[str, Path] = {}
        for index, request in enumerate(requests, 1):
            target = request.target
            if current != target.uniq_id:
                for path in clips.values():
                    path.unlink(missing_ok=True)
                if source is not None:
                    source.unlink(missing_ok=True)
                source = _source(target, directory)
                clips = {}
                current = target.uniq_id
            if target.target_id not in clips:
                clip = directory / f"{target.target_id}.wav"
                _clip(source, clip, target.start, target.end)
                clips[target.target_id] = clip
            kwargs = request.head_request.to_transport_kwargs(
                request_id=request.request_id,
                audio_path=clips[target.target_id],
                audio_seconds=target.duration,
            )
            kwargs["decoding_params"] = {"temperature": 0, "seed": 0, "max_tokens": 512}
            response = transport.request(**kwargs)
            receipt.record(response)
            _append(
                sink,
                {
                    "request_id": request.request_id,
                    "target_id": target.target_id,
                    "uniq_id": target.uniq_id,
                    "turn_index": target.turn_index,
                    "speaker_id": target.speaker_id,
                    "arm": request.arm,
                    "injected_terms": list(request.injected_terms),
                    "outcome": "ok",
                    "text": response.text,
                    "usage": dict(response.usage),
                    "attempts": [attempt.as_json() for attempt in response.attempts],
                    "recorded_utc": datetime.now(timezone.utc).isoformat(),
                },
            )
            if index % 25 == 0:
                print(f"E4-DISJOINT-DIR {index}/{calls}", file=sys.stderr, flush=True)
    receipt.write(receipt_out, repo_root=Path(__file__).resolve().parent.parent, run_id="e4-disjoint-dir-v1")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
