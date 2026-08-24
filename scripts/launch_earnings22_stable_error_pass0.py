#!/usr/bin/env python3
"""Launch one frozen meeting of E-STABLE-ERROR-SUPPLY Pass-0."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget  # noqa: E402
from meeting_minutes_agent.client.receipts import FlightReceipt, ModelFileRef, ServerIdentity  # noqa: E402
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig  # noqa: E402
from meeting_minutes_agent.heads.request import HeadRequest  # noqa: E402
from meeting_minutes_agent.probes.contextasr import SYSTEM_INSTRUCTION, TEMPLATE_ID, TEMPLATE_SHA256  # noqa: E402
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402


def load_runtime(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema") != "earnings22-stable-error-runtime-v1":
        raise ValueError("runtime schema mismatch")
    expected = config_hash({key: value for key, value in document.items() if key != "content_hash"})
    if document.get("content_hash") != expected:
        raise ValueError("runtime content hash mismatch")
    return document


def _append(handle: object, value: dict[str, object]) -> None:
    handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")  # type: ignore[union-attr]
    handle.flush()  # type: ignore[union-attr]
    os.fsync(handle.fileno())  # type: ignore[union-attr]


def _clip(source: Path, destination: Path, start: float, end: float) -> None:
    import soundfile as sf

    with sf.SoundFile(source) as audio:
        rate = audio.samplerate
        audio.seek(round(start * rate))
        frames = round((end - start) * rate)
        samples = audio.read(frames=frames, dtype="float32", always_2d=True)
    sf.write(destination, samples, rate, subtype="PCM_16")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--meeting-index", required=True, type=int)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--mmproj-path", required=True)
    parser.add_argument("--mmproj-sha256", required=True)
    parser.add_argument("--responses-out", required=True, type=Path)
    parser.add_argument("--receipt-out", required=True, type=Path)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    manifest = load_runtime(args.manifest)
    meetings = manifest["meetings"]
    if args.meeting_index < 0 or args.meeting_index >= len(meetings):  # type: ignore[arg-type]
        parser.error("meeting-index outside frozen roster")
    meeting = meetings[args.meeting_index]  # type: ignore[index]
    turns = meeting["turns"]
    calls = len(turns)
    audio_seconds = sum(float(turn["duration"]) for turn in turns)
    summary = {"file_id": meeting["file_id"], "calls": calls, "audio_seconds": audio_seconds}
    if args.summary_only:
        print(json.dumps(summary, indent=2))
        return 0
    if args.responses_out.exists() or args.receipt_out.exists():
        parser.error("output exists; refusing overwrite")
    source = args.data_dir / str(meeting["wav_relative"])
    if not source.is_file():
        parser.error(f"missing source WAV: {source}")
    budget = CallBudget(BudgetLimits(max_calls=calls, max_audio_seconds=audio_seconds + 1e-6))
    identity = ServerIdentity(
        args.base_url,
        (ModelFileRef(args.model_path, args.model_sha256), ModelFileRef(args.mmproj_path, args.mmproj_sha256)),
        1,
    )
    transport = LlamaServerTransport(
        TransportConfig(base_url=args.base_url, slots=1, max_retries=0, timeout_seconds=300), budget
    )
    receipt = FlightReceipt(identity, budget)
    head = HeadRequest(SYSTEM_INSTRUCTION, (), {}, TEMPLATE_ID, TEMPLATE_SHA256)
    args.responses_out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="stable-error-") as temporary, args.responses_out.open(
        "x", encoding="utf-8", newline="\n"
    ) as sink:
        directory = Path(temporary)
        for position, turn in enumerate(turns, start=1):
            clip = directory / f"turn{int(turn['index']):04d}.wav"
            _clip(source, clip, float(turn["start"]), float(turn["end"]))
            request_id = f"estable-{meeting['file_id']}-turn{int(turn['index']):04d}"
            kwargs = head.to_transport_kwargs(
                request_id=request_id, audio_path=clip, audio_seconds=float(turn["duration"])
            )
            kwargs["decoding_params"] = {"temperature": 0, "seed": 0, "max_tokens": 512}
            response = transport.request(**kwargs)
            receipt.record(response)
            _append(
                sink,
                {
                    "request_id": request_id,
                    "file_id": meeting["file_id"],
                    "turn_index": turn["index"],
                    "speaker_id": turn["speaker_id"],
                    "outcome": "ok",
                    "text": response.text,
                    "usage": dict(response.usage),
                    "attempts": [attempt.as_json() for attempt in response.attempts],
                    "recorded_utc": datetime.now(timezone.utc).isoformat(),
                },
            )
            if position % 50 == 0:
                print(f"{meeting['file_id']}: {position}/{calls}", file=sys.stderr, flush=True)
    receipt.write(args.receipt_out, repo_root=ROOT, run_id=f"e-stable-error-{meeting['file_id']}-pass0-v1")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
