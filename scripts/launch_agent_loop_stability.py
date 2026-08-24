#!/usr/bin/env python3
"""Run E-LOOP-STABILITY phase 1 or the L3 convergence round."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
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
from meeting_minutes_agent.runreceipt import config_hash  # noqa: E402
from meeting_minutes_agent.state.sliding_memory import (  # noqa: E402
    MemoryLimits,
    build_meeting_memory,
    context_hash,
    render_context,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _locked(path: Path, expected: str) -> None:
    if sha256_file(path) != expected:
        raise ValueError(f"hash mismatch: {path}")


def _load_manifest(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "agent-loop-stability-runtime-v1":
        raise ValueError("manifest schema mismatch")
    expected = config_hash({key: item for key, item in value.items() if key != "content_hash"})
    if value.get("content_hash") != expected:
        raise ValueError("manifest content hash mismatch")
    return value


def _load_rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _complete_source(path: Path, meeting: dict[str, object]) -> list[dict[str, object]]:
    rows = [row for row in _load_rows(path) if row.get("outcome") == "ok"]
    expected = {int(turn["index"]) for turn in meeting["turns"]}
    if {int(row["turn_index"]) for row in rows} != expected or len(rows) != len(expected):
        raise ValueError(f"incomplete source pass: {meeting['file_id']}")
    return rows


def _append(handle: object, value: dict[str, object]) -> None:
    handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")  # type: ignore[union-attr]
    handle.flush()  # type: ignore[union-attr]
    os.fsync(handle.fileno())  # type: ignore[union-attr]


def _clip(source: Path, destination: Path, start: float, end: float) -> None:
    import soundfile as sf

    with sf.SoundFile(source) as audio:
        rate = audio.samplerate
        audio.seek(round(start * rate))
        samples = audio.read(frames=round((end - start) * rate), dtype="float32", always_2d=True)
    sf.write(destination, samples, rate, subtype="PCM_16")


def _done(path: Path) -> dict[str, dict[str, object]]:
    if not path.is_file():
        return {}
    rows = _load_rows(path)
    output = {str(row["request_id"]): row for row in rows if row.get("outcome") == "ok"}
    if len(output) != len(rows):
        raise ValueError("duplicate or failed existing response")
    return output


def _limits(manifest: dict[str, object]) -> MemoryLimits:
    return MemoryLimits(**{key: int(value) for key, value in manifest["memory_limits"].items()})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--phase", choices=("phase1", "round2"), required=True)
    parser.add_argument("--phase1-responses", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--mmproj-path", required=True)
    parser.add_argument("--mmproj-sha256", required=True)
    parser.add_argument("--responses-out", required=True, type=Path)
    parser.add_argument("--receipt-out", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    manifest = _load_manifest(args.manifest)
    runtime_lock = manifest["source_runtime"]
    runtime_path = ROOT / runtime_lock["path"]
    _locked(runtime_path, str(runtime_lock["sha256"]))
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    arms = list(manifest["arms"]) if args.phase == "phase1" else [str(manifest["round2_arm"])]
    calls = sum(len(meeting["turns"]) for meeting in runtime["meetings"]) * len(arms)
    audio_seconds = sum(float(turn["duration"]) for meeting in runtime["meetings"] for turn in meeting["turns"]) * len(arms)
    if args.summary_only:
        print(json.dumps({"phase": args.phase, "arms": arms, "calls": calls, "audio_seconds": audio_seconds}, indent=2))
        return 0
    if args.receipt_out.exists():
        parser.error("receipt exists")
    if args.responses_out.exists() and not args.resume:
        parser.error("responses exist; use --resume")
    if args.phase == "round2" and not args.phase1_responses:
        parser.error("round2 requires --phase1-responses")
    limits = _limits(manifest)
    prompt = manifest["prompt"]
    head_template = lambda context: HeadRequest(  # noqa: E731
        str(prompt["system_instruction"]), (context,) if context else (), {},
        str(prompt["template_id"]), str(prompt["template_sha256"]),
    )
    existing = _done(args.responses_out) if args.resume else {}
    budget = CallBudget(BudgetLimits(max_calls=calls, max_audio_seconds=audio_seconds + 1e-6))
    identity = ServerIdentity(
        args.base_url,
        (ModelFileRef(args.model_path, args.model_sha256), ModelFileRef(args.mmproj_path, args.mmproj_sha256)),
        1,
    )
    transport = LlamaServerTransport(TransportConfig(args.base_url, slots=1, max_retries=0), budget)
    receipt = FlightReceipt(identity, budget)
    args.responses_out.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.resume else "x"
    completed = 0
    with tempfile.TemporaryDirectory(prefix="loop-stability-") as temporary, args.responses_out.open(
        mode, encoding="utf-8", newline="\n"
    ) as sink:
        directory = Path(temporary)
        for meeting_position, meeting in enumerate(runtime["meetings"]):
            file_id = str(meeting["file_id"])
            if args.phase == "phase1":
                source_lock = manifest["source_passes"][file_id]
                source_path = ROOT / source_lock["path"]
                _locked(source_path, str(source_lock["sha256"]))
                source_rows = _complete_source(source_path, meeting)
            else:
                all_phase1 = _load_rows(args.phase1_responses)
                source_rows = [
                    row for row in all_phase1
                    if row.get("file_id") == file_id and row.get("arm") == "L3-speaker" and row.get("outcome") == "ok"
                ]
                expected = {int(turn["index"]) for turn in meeting["turns"]}
                if {int(row["turn_index"]) for row in source_rows} != expected or len(source_rows) != len(expected):
                    raise ValueError(f"incomplete L3 source: {file_id}")
            memory = build_meeting_memory(source_rows, limits)
            histories: dict[str, list[dict[str, object]]] = {arm: [] for arm in arms}
            wav = args.data_dir / str(meeting["wav_relative"])
            if not wav.is_file():
                raise ValueError(f"missing WAV: {wav}")
            for turn in meeting["turns"]:
                clip = directory / f"{file_id}-{int(turn['index']):04d}.wav"
                _clip(wav, clip, float(turn["start"]), float(turn["end"]))
                ordered_arms = arms
                if args.phase == "phase1":
                    offset = (meeting_position + int(turn["index"])) % len(arms)
                    ordered_arms = arms[offset:] + arms[:offset]
                for arm in ordered_arms:
                    render_arm = "L3-speaker" if arm == "L3-round2" else arm
                    context = render_context(render_arm, str(turn["speaker_id"]), memory, histories[arm], limits)
                    request_id = f"loop-{args.phase}-{file_id}-turn{int(turn['index']):04d}-{arm.lower()}"
                    if request_id in existing:
                        histories[arm].append(existing[request_id])
                        continue
                    kwargs = head_template(context).to_transport_kwargs(
                        request_id=request_id, audio_path=clip, audio_seconds=float(turn["duration"])
                    )
                    kwargs["decoding_params"] = dict(manifest["decode"])
                    response = transport.request(**kwargs)
                    receipt.record(response)
                    routed = str(turn["speaker_id"])
                    if arm == "L4-deranged":
                        routed = memory.deranged_speaker[routed]
                    injected = []
                    if arm in {"L2-global", "L3-speaker", "L4-deranged", "L3-round2"}:
                        injected.extend(memory.global_keywords)
                    if arm in {"L3-speaker", "L4-deranged", "L3-round2"}:
                        injected.extend(memory.speaker_keywords.get(routed, ()))
                    record = {
                        "request_id": request_id,
                        "file_id": file_id,
                        "turn_index": turn["index"],
                        "speaker_id": turn["speaker_id"],
                        "arm": arm,
                        "memory_speaker_id": routed if arm in {"L3-speaker", "L4-deranged", "L3-round2"} else None,
                        "source_pass_hash": memory.source_pass_hash,
                        "context_sha256": context_hash(context),
                        "context_characters": len(context),
                        "injected_terms": sorted(set(injected)),
                        "outcome": "ok",
                        "text": response.text,
                        "usage": dict(response.usage),
                        "attempts": [attempt.as_json() for attempt in response.attempts],
                        "recorded_utc": datetime.now(timezone.utc).isoformat(),
                    }
                    _append(sink, record)
                    histories[arm].append(record)
                    completed += 1
                    if completed % 100 == 0:
                        print(f"{args.phase}: {completed}/{calls}", file=sys.stderr, flush=True)
                clip.unlink(missing_ok=True)
    receipt.write(args.receipt_out, repo_root=ROOT, run_id=f"e-loop-stability-{args.phase}-v1")
    print(json.dumps({"phase": args.phase, "planned": calls, "skipped": len(existing), "flown": completed}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
