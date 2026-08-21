#!/usr/bin/env python3
"""Execute exactly one preregistered missing E4-DISJOINT-DIR cell."""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from launch_e4_direction import _append, _clip, _source

from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget
from meeting_minutes_agent.client.receipts import FlightReceipt, ModelFileRef, ServerIdentity
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig
from meeting_minutes_agent.probes.e4_disjoint_direction import build_requests, load_runtime_binding


def _load_primary(path: Path, expected: dict[str, object]) -> set[str]:
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            record = json.loads(line)
            request_id = record.get("request_id")
            if request_id not in expected:
                raise ValueError(f"unexpected request at primary line {line_number}: {request_id!r}")
            if request_id in seen:
                raise ValueError(f"duplicate primary request: {request_id}")
            request = expected[request_id]
            if record.get("outcome") != "ok" or record.get("target_id") != request.target.target_id or record.get("arm") != request.arm:
                raise ValueError(f"primary metadata mismatch: {request_id}")
            seen.add(request_id)
    return seen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", required=True)
    parser.add_argument("--primary-responses", required=True)
    parser.add_argument("--expected-missing-request-id", required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model-path")
    parser.add_argument("--model-sha256")
    parser.add_argument("--mmproj-path")
    parser.add_argument("--mmproj-sha256")
    parser.add_argument("--response-out")
    parser.add_argument("--receipt-out")
    args = parser.parse_args(argv)

    requests = build_requests(load_runtime_binding(args.binding))
    expected = {request.request_id: request for request in requests}
    seen = _load_primary(Path(args.primary_responses), expected)
    missing = set(expected) - seen
    if len(seen) != len(expected) - 1 or missing != {args.expected_missing_request_id}:
        parser.error(f"primary flight must have exactly the declared missing cell; seen={len(seen)}, missing={sorted(missing)}")
    request = expected[args.expected_missing_request_id]
    if args.validate_only:
        print(json.dumps({"seen": len(seen), "missing": request.request_id, "audio_seconds": request.target.duration}))
        return 0
    required = (args.model_path, args.model_sha256, args.mmproj_path, args.mmproj_sha256, args.response_out, args.receipt_out)
    if not all(required):
        parser.error("flight identities and output paths required unless --validate-only is used")
    response_out = Path(args.response_out)
    receipt_out = Path(args.receipt_out)
    if response_out.exists() or receipt_out.exists():
        parser.error("supplement output exists; refusing overwrite")
    response_out.parent.mkdir(parents=True, exist_ok=True)

    duration = request.target.duration
    budget = CallBudget(BudgetLimits(max_calls=1, max_audio_seconds=duration))
    identity = ServerIdentity(
        args.base_url,
        (ModelFileRef(args.model_path, args.model_sha256), ModelFileRef(args.mmproj_path, args.mmproj_sha256)),
        1,
    )
    transport = LlamaServerTransport(
        TransportConfig(base_url=args.base_url, slots=1, max_retries=0, timeout_seconds=300), budget
    )
    receipt = FlightReceipt(identity, budget)
    with tempfile.TemporaryDirectory(prefix="e4dir-supplement-") as temp:
        directory = Path(temp)
        source = _source(request.target, directory)
        clip = directory / f"{request.target.target_id}.wav"
        _clip(source, clip, request.target.start, request.target.end)
        kwargs = request.head_request.to_transport_kwargs(
            request_id=request.request_id, audio_path=clip, audio_seconds=duration
        )
        kwargs["decoding_params"] = {"temperature": 0, "seed": 0, "max_tokens": 512}
        response = transport.request(**kwargs)
        receipt.record(response)
        with response_out.open("x", encoding="utf-8") as sink:
            _append(sink, {
                "request_id": request.request_id,
                "target_id": request.target.target_id,
                "uniq_id": request.target.uniq_id,
                "turn_index": request.target.turn_index,
                "speaker_id": request.target.speaker_id,
                "arm": request.arm,
                "injected_terms": list(request.injected_terms),
                "outcome": "ok",
                "text": response.text,
                "usage": dict(response.usage),
                "attempts": [attempt.as_json() for attempt in response.attempts],
                "recorded_utc": datetime.now(timezone.utc).isoformat(),
            })
    receipt.write(receipt_out, repo_root=Path(__file__).resolve().parent.parent, run_id="e4-disjoint-dir-v1-supplement")
    print(json.dumps({"request_id": request.request_id, "calls": 1, "audio_seconds": duration}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
