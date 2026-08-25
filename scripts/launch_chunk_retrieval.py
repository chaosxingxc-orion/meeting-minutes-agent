#!/usr/bin/env python3
"""Run E-CHUNK-RETRIEVAL phase 1 or the R2 convergence round."""

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
from meeting_minutes_agent.state.chunk_retrieval import (  # noqa: E402
    RetrievalLimits,
    build_index,
    render_candidates,
    retrieve_deranged,
    retrieve_for_arm,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def context_hash(context: str) -> str:
    return hashlib.sha256(context.encode("utf-8")).hexdigest()


def locked(path: Path, expected: str) -> None:
    if sha256_file(path) != expected:
        raise ValueError(f"hash mismatch: {path}")


def load_manifest(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "chunk-retrieval-runtime-v1":
        raise ValueError("manifest schema mismatch")
    expected = config_hash({key: item for key, item in value.items() if key != "content_hash"})
    if value.get("content_hash") != expected:
        raise ValueError("manifest content hash mismatch")
    return value


def rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def complete(rows_value: list[dict[str, object]], meeting: dict[str, object]) -> list[dict[str, object]]:
    expected = {int(turn["index"]) for turn in meeting["turns"]}
    selected = [row for row in rows_value if row.get("outcome") == "ok"]
    if {int(row["turn_index"]) for row in selected} != expected or len(selected) != len(expected):
        raise ValueError(f"incomplete source pass: {meeting['file_id']}")
    return sorted(selected, key=lambda row: int(row["turn_index"]))


def append(handle: object, value: dict[str, object]) -> None:
    handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")  # type: ignore[union-attr]
    handle.flush()  # type: ignore[union-attr]
    os.fsync(handle.fileno())  # type: ignore[union-attr]


def clip(source: Path, destination: Path, start: float, end: float) -> None:
    import soundfile as sf

    with sf.SoundFile(source) as audio:
        rate = audio.samplerate
        audio.seek(round(start * rate))
        samples = audio.read(frames=round((end - start) * rate), dtype="float32", always_2d=True)
    sf.write(destination, samples, rate, subtype="PCM_16")


def done(path: Path) -> dict[str, dict[str, object]]:
    if not path.is_file():
        return {}
    loaded = rows(path)
    output = {str(row["request_id"]): row for row in loaded if row.get("outcome") == "ok"}
    if len(output) != len(loaded):
        raise ValueError("duplicate or failed existing response")
    return output


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
    manifest = load_manifest(args.manifest)
    runtime_lock = manifest["source_runtime"]
    runtime_path = ROOT / runtime_lock["path"]
    locked(runtime_path, str(runtime_lock["sha256"]))
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
    limits = RetrievalLimits(**manifest["retrieval_limits"])
    prompt = manifest["prompt"]
    existing = done(args.responses_out) if args.resume else {}
    budget = CallBudget(BudgetLimits(max_calls=calls, max_audio_seconds=audio_seconds + 1e-6))
    identity = ServerIdentity(
        args.base_url,
        (ModelFileRef(args.model_path, args.model_sha256), ModelFileRef(args.mmproj_path, args.mmproj_sha256)),
        1,
    )
    transport = LlamaServerTransport(TransportConfig(args.base_url, slots=1, max_retries=0), budget)
    receipt = FlightReceipt(identity, budget)
    phase1_rows = rows(args.phase1_responses) if args.phase1_responses else []
    args.responses_out.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.resume else "x"
    completed = 0
    with tempfile.TemporaryDirectory(prefix="chunk-retrieval-") as temporary, args.responses_out.open(
        mode, encoding="utf-8", newline="\n"
    ) as sink:
        directory = Path(temporary)
        for meeting_position, meeting in enumerate(runtime["meetings"]):
            file_id = str(meeting["file_id"])
            if args.phase == "phase1":
                source_lock = manifest["source_passes"][file_id]
                source_path = ROOT / source_lock["path"]
                locked(source_path, str(source_lock["sha256"]))
                source_rows = complete(rows(source_path), meeting)
            else:
                selected = [
                    row for row in phase1_rows
                    if row.get("file_id") == file_id and row.get("arm") == "R2-speaker"
                ]
                source_rows = complete(selected, meeting)
            source_by_turn = {int(row["turn_index"]): row for row in source_rows}
            source_pass_hash = config_hash(source_rows)
            index = build_index(source_rows, limits)
            wav = args.data_dir / str(meeting["wav_relative"])
            if not wav.is_file():
                raise ValueError(f"missing WAV: {wav}")
            for turn in meeting["turns"]:
                turn_index = int(turn["index"])
                clip_path = directory / f"{file_id}-{turn_index:04d}.wav"
                clip(wav, clip_path, float(turn["start"]), float(turn["end"]))
                ordered_arms = arms
                if args.phase == "phase1":
                    offset = (meeting_position + turn_index) % len(arms)
                    ordered_arms = arms[offset:] + arms[:offset]
                query = str(source_by_turn[turn_index].get("text", ""))
                for arm in ordered_arms:
                    retrieval_arm = "R2-round2" if arm == "R2-round2" else arm
                    memory_speaker: str | None = None
                    if arm == "R3-deranged":
                        deranged = retrieve_deranged(str(turn["speaker_id"]), query, index, limits)
                        candidates = deranged.candidates
                        memory_speaker = deranged.source_speaker_id
                    else:
                        candidates = retrieve_for_arm(retrieval_arm, str(turn["speaker_id"]), query, index, limits)
                        if arm in {"R2-speaker", "R2-round2"}:
                            memory_speaker = str(turn["speaker_id"])
                    context = render_candidates(candidates, limits.maximum_context_characters)
                    request_id = f"chunk-{args.phase}-{file_id}-turn{turn_index:04d}-{arm.lower()}"
                    if request_id in existing:
                        continue
                    head = HeadRequest(
                        str(prompt["system_instruction"]), (context,) if context else (), {},
                        str(prompt["template_id"]), str(prompt["template_sha256"]),
                    )
                    kwargs = head.to_transport_kwargs(
                        request_id=request_id, audio_path=clip_path, audio_seconds=float(turn["duration"])
                    )
                    kwargs["decoding_params"] = dict(manifest["decode"])
                    response = transport.request(**kwargs)
                    receipt.record(response)
                    append(sink, {
                        "request_id": request_id,
                        "file_id": file_id,
                        "turn_index": turn_index,
                        "speaker_id": turn["speaker_id"],
                        "arm": arm,
                        "memory_speaker_id": memory_speaker,
                        "source_pass_hash": source_pass_hash,
                        "context_sha256": context_hash(context),
                        "context_characters": len(context),
                        "injected_terms": list(candidates),
                        "outcome": "ok",
                        "text": response.text,
                        "usage": dict(response.usage),
                        "attempts": [attempt.as_json() for attempt in response.attempts],
                        "recorded_utc": datetime.now(timezone.utc).isoformat(),
                    })
                    completed += 1
                    if completed % 100 == 0:
                        print(f"{args.phase}: {completed}/{calls}", file=sys.stderr, flush=True)
                clip_path.unlink(missing_ok=True)
    receipt.write(args.receipt_out, repo_root=ROOT, run_id=f"e-chunk-retrieval-{args.phase}-v1")
    print(json.dumps({"phase": args.phase, "planned": calls, "skipped": len(existing), "flown": completed}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
