#!/usr/bin/env python3
"""Launch the registered E3 Pass-0 transcription flight."""

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
from meeting_minutes_agent.heads.request import HeadRequest  # noqa: E402
from meeting_minutes_agent.probes.contextasr import SYSTEM_INSTRUCTION, TEMPLATE_ID, TEMPLATE_SHA256  # noqa: E402
from meeting_minutes_agent.probes.state_audit import load_manifest  # noqa: E402


def _append(handle, record: dict[str, object]) -> None:
    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


def _done(path: Path) -> set[tuple[str, int]]:
    if not path.is_file():
        return set()
    return {
        (str(record["uniq_id"]), int(record["turn_index"]))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for record in [json.loads(line)]
        if record.get("outcome") == "ok"
    }


def _extract_dialogue(entry, directory: Path) -> Path:
    with tarfile.open(entry.source_tar, "r") as archive:
        source = archive.extractfile(entry.tar_member)
        if source is None:
            raise RuntimeError(f"unreadable tar member: {entry.tar_member}")
        data = source.read()
    actual = hashlib.sha256(data).hexdigest()
    if actual != entry.audio_sha256:
        raise RuntimeError(f"audio hash mismatch for {entry.uniq_id}: {actual}")
    path = directory / f"{entry.uniq_id}.wav"
    path.write_bytes(data)
    return path


def _slice_turn(source: Path, target: Path, start: float, end: float) -> None:
    import soundfile as sf

    audio, rate = sf.read(source, dtype="float32", always_2d=True)
    begin = max(0, round(start * rate))
    finish = min(len(audio), round(end * rate))
    sf.write(target, audio[begin:finish], rate, subtype="PCM_16")


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
    parser.add_argument("--max-calls", type=int, default=151)
    parser.add_argument("--max-audio-seconds", type=float, default=1800.0)
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest)
    turns = [(entry, turn) for entry in manifest.entries for turn in entry.turns]
    summary = {
        "manifest_hash": manifest.content_hash,
        "dialogues": len(manifest.entries),
        "calls": len(turns),
        "audio_seconds": sum(turn.duration for _, turn in turns),
    }
    if args.summary_only:
        print(json.dumps(summary, indent=2))
        return 0
    required = (args.model_path, args.model_sha256, args.mmproj_path, args.mmproj_sha256, args.responses_out, args.receipt_out)
    if not all(required):
        parser.error("flight mode requires model/mmproj paths+hashes and response/receipt outputs")
    response_path = Path(args.responses_out)
    if response_path.exists() and not args.resume:
        parser.error(f"responses file exists: {response_path}")
    response_path.parent.mkdir(parents=True, exist_ok=True)
    done = _done(response_path) if args.resume else set()
    remaining = [(entry, turn) for entry, turn in turns if (entry.uniq_id, turn.index) not in done]
    budget = CallBudget(BudgetLimits(max_calls=args.max_calls, max_audio_seconds=args.max_audio_seconds))
    identity = ServerIdentity(
        base_url=args.base_url,
        model_files=(ModelFileRef(args.model_path, args.model_sha256), ModelFileRef(args.mmproj_path, args.mmproj_sha256)),
        slots=1,
    )
    transport = LlamaServerTransport(TransportConfig(base_url=args.base_url, slots=1, max_retries=0, timeout_seconds=300), budget)
    receipt = FlightReceipt(identity, budget)
    head = HeadRequest(SYSTEM_INSTRUCTION, (), {}, TEMPLATE_ID, TEMPLATE_SHA256)
    with tempfile.TemporaryDirectory(prefix="e3-state-") as temp, response_path.open("a", encoding="utf-8") as sink:
        temp_dir = Path(temp)
        extracted: dict[str, Path] = {}
        for count, (entry, turn) in enumerate(remaining, 1):
            source = extracted.setdefault(entry.uniq_id, _extract_dialogue(entry, temp_dir)) if entry.uniq_id not in extracted else extracted[entry.uniq_id]
            clip = temp_dir / f"{entry.uniq_id}-turn{turn.index:03d}.wav"
            _slice_turn(source, clip, turn.start, turn.end)
            request_id = f"e3-{entry.uniq_id}-turn{turn.index:03d}"
            kwargs = head.to_transport_kwargs(request_id=request_id, audio_path=clip, audio_seconds=turn.duration)
            kwargs["decoding_params"] = {"temperature": 0, "seed": 0, "max_tokens": 512}
            response = transport.request(**kwargs)
            receipt.record(response)
            _append(
                sink,
                {
                    "request_id": request_id,
                    "uniq_id": entry.uniq_id,
                    "turn_index": turn.index,
                    "speaker_id": turn.speaker_id,
                    "outcome": "ok",
                    "text": response.text,
                    "usage": dict(response.usage),
                    "attempts": [attempt.as_json() for attempt in response.attempts],
                    "recorded_utc": datetime.now(timezone.utc).isoformat(),
                },
            )
            if count % 10 == 0:
                print(f"E3 Pass-0 {count}/{len(remaining)}", file=sys.stderr, flush=True)
    receipt.write(args.receipt_out, repo_root=Path(__file__).resolve().parent.parent, run_id="e3-state-audit-12-v1")
    print(json.dumps({**summary, "skipped": len(done), "flown": len(remaining)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
