#!/usr/bin/env python3
"""Launch one registered E4-DISJOINT-PREV Pass-0 stage."""

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
from meeting_minutes_agent.probes.e4_confirmatory import load_pass0_runtime  # noqa: E402


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
        for record in [json.loads(line)]
        if record.get("outcome") == "ok"
    }


def _clips(entry, directory: Path) -> dict[int, Path]:
    import soundfile as sf

    with tarfile.open(entry.source_tar, "r") as archive:
        source = archive.extractfile(entry.tar_member)
        if source is None:
            raise RuntimeError(f"unreadable {entry.tar_member}")
        data = source.read()
    if hashlib.sha256(data).hexdigest() != entry.audio_sha256:
        raise RuntimeError(f"audio hash mismatch: {entry.uniq_id}")
    whole = directory / f"{entry.uniq_id}.wav"
    whole.write_bytes(data)
    audio, rate = sf.read(whole, dtype="float32", always_2d=True)
    output = {}
    for turn in entry.turns:
        path = directory / f"{entry.uniq_id}-turn{turn.index:03d}.wav"
        sf.write(path, audio[round(turn.start * rate) : round(turn.end * rate)], rate, subtype="PCM_16")
        output[turn.index] = path
    whole.unlink()
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--start-dialogue", type=int, required=True)
    parser.add_argument("--end-dialogue", type=int, required=True)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model-path")
    parser.add_argument("--model-sha256")
    parser.add_argument("--mmproj-path")
    parser.add_argument("--mmproj-sha256")
    parser.add_argument("--responses-out")
    parser.add_argument("--receipt-out")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-calls", type=int, required=True)
    parser.add_argument("--max-audio-seconds", type=float, required=True)
    args = parser.parse_args(argv)
    if (args.start_dialogue, args.end_dialogue) not in {(0, 20), (20, 40), (40, 60)}:
        parser.error("stage must be exactly 0:20, 20:40, or 40:60")
    manifest = load_pass0_runtime(args.manifest)
    entries = manifest.entries[args.start_dialogue : args.end_dialogue]
    all_turns = [(entry, turn) for entry in entries for turn in entry.turns]
    audio_seconds = sum(turn.duration for _, turn in all_turns)
    summary = {
        "manifest_hash": manifest.content_hash,
        "stage": [args.start_dialogue, args.end_dialogue],
        "dialogues": len(entries),
        "calls": len(all_turns),
        "audio_seconds": audio_seconds,
    }
    if len(all_turns) > args.max_calls or audio_seconds > args.max_audio_seconds:
        parser.error(f"frozen stage exceeds budget: {summary}")
    if args.summary_only:
        print(json.dumps(summary, indent=2))
        return 0
    required = (args.model_path, args.model_sha256, args.mmproj_path, args.mmproj_sha256, args.responses_out, args.receipt_out)
    if not all(required):
        parser.error("flight identities and outputs required")
    output = Path(args.responses_out)
    if output.exists() and not args.resume:
        parser.error("responses exist; use --resume with a new receipt path")
    if Path(args.receipt_out).exists():
        parser.error("receipt output exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    done = _done(output) if args.resume else set()
    remaining = [item for item in all_turns if (item[0].uniq_id, item[1].index) not in done]
    budget = CallBudget(BudgetLimits(max_calls=args.max_calls, max_audio_seconds=args.max_audio_seconds))
    identity = ServerIdentity(
        args.base_url,
        (ModelFileRef(args.model_path, args.model_sha256), ModelFileRef(args.mmproj_path, args.mmproj_sha256)),
        1,
    )
    transport = LlamaServerTransport(TransportConfig(base_url=args.base_url, slots=1, max_retries=0, timeout_seconds=300), budget)
    receipt = FlightReceipt(identity, budget)
    head = HeadRequest(SYSTEM_INSTRUCTION, (), {}, TEMPLATE_ID, TEMPLATE_SHA256)
    prefix = f"e4prev-s{args.end_dialogue}"
    with tempfile.TemporaryDirectory(prefix=prefix + "-") as temp, output.open("a", encoding="utf-8") as sink:
        directory = Path(temp)
        current_id = None
        clips: dict[int, Path] = {}
        for index, (entry, turn) in enumerate(remaining, 1):
            if current_id != entry.uniq_id:
                for path in clips.values():
                    path.unlink(missing_ok=True)
                clips = _clips(entry, directory)
                current_id = entry.uniq_id
            request_id = f"{prefix}-{entry.uniq_id}-turn{turn.index:03d}"
            kwargs = head.to_transport_kwargs(request_id=request_id, audio_path=clips[turn.index], audio_seconds=turn.duration)
            kwargs["decoding_params"] = {"temperature": 0, "seed": 0, "max_tokens": 512}
            response = transport.request(**kwargs)
            receipt.record(response)
            _append(sink, {
                "request_id": request_id, "uniq_id": entry.uniq_id, "turn_index": turn.index,
                "speaker_id": turn.speaker_id, "outcome": "ok", "text": response.text,
                "usage": dict(response.usage), "attempts": [item.as_json() for item in response.attempts],
                "recorded_utc": datetime.now(timezone.utc).isoformat(),
            })
            if index % 50 == 0:
                print(f"E4-PREV stage {args.end_dialogue}: {index}/{len(remaining)}", file=sys.stderr, flush=True)
    receipt.write(args.receipt_out, repo_root=Path(__file__).resolve().parent.parent, run_id=f"e4-disjoint-prev-stage-{args.end_dialogue}-v1")
    print(json.dumps({**summary, "skipped": len(done), "flown": len(remaining)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
