#!/usr/bin/env python3
"""P-PROMPT sweep flight launcher -- mirrors ``scripts/launch_pattr_smoke.py``
almost exactly (module docstring there for the shared discipline: fsynced
JSONL response sink, ``--resume`` support, a generation cap via
``decoding_params``, per-request receipts, hard budget enforcement). This
engineering mission builds and import-verifies this script; it never runs it
against a live server (zero model contact, CLAUDE.md). The FLIGHT mission (a
separate, later mission) runs it against a real ``llama-server``.

Wires: the frozen P-ATTR 24-slice manifest (audio identity, reused verbatim)
+ the frozen P-PROMPT binding manifest (the label derangement for X1, the
donor-meeting assignment + hash pins for X2) -> one arm's 24 request specs
(:mod:`meeting_minutes_agent.probes.pprompt`) -> :class:`~meeting_minutes_agent.
client.transport.LlamaServerTransport` -> a :class:`~meeting_minutes_agent.
client.receipts.FlightReceipt`.

X2's own real-I/O step lives HERE, not in :mod:`~meeting_minutes_agent.probes.
pprompt` (a request builder stays I/O-free, that module's own docstring):
:func:`load_x2_tail_segments` re-reads the P-ATTR smoke's archived A-turn
reply JSONL fresh from ``--data-dir``, and verifies every donor entry's text
against the sha256 the binding manifest pinned at build time -- fail-closed
on any mismatch, never a silent substitution.

Usage (safe right now -- no server, no model contact)::

    python scripts/launch_pprompt_sweep.py \\
        --data-dir "$SPEECHRL_DATA_DIR" \\
        --pattr-manifest configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json \\
        --binding configs/probes/pprompt/2026-08-18-pprompt-binding.json \\
        --arm T2-A1 --summary-only

Usage (the FLIGHT mission)::

    python scripts/launch_pprompt_sweep.py \\
        --data-dir "$SPEECHRL_DATA_DIR" \\
        --pattr-manifest configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json \\
        --binding configs/probes/pprompt/2026-08-18-pprompt-binding.json \\
        --arm T2-A1 \\
        --base-url http://127.0.0.1:8080 \\
        --model-path /home/chao/models/<pinned-gguf> --model-sha256 <sha256> \\
        --max-calls 30 --max-audio-seconds 3600 \\
        --receipt-out docs/checks/<campaign>/<release-id>/pprompt-T2-A1-receipt.json \\
        --responses-out "$SPEECHRL_DATA_DIR/derived/meeting-minutes/pprompt-sweep/runs/<run-id>/T2-A1-responses.jsonl"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from meeting_minutes_agent.chunking.models import Segment  # noqa: E402
from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget  # noqa: E402
from meeting_minutes_agent.client.receipts import FlightReceipt, ModelFileRef, ServerIdentity  # noqa: E402
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig  # noqa: E402
from meeting_minutes_agent.probes.pattr import PattrManifest, load_pattr_manifest  # noqa: E402
from meeting_minutes_agent.probes.pprompt import (  # noqa: E402
    ARM_X1,
    ARM_X2,
    ARMS,
    build_arm_requests,
    summarize_all_requests,
)


class PpromptBindingError(ValueError):
    """The binding manifest JSON failed a fail-closed load/lookup check."""


def load_pprompt_binding(path: Path | str) -> dict:
    """Load the frozen P-PROMPT binding manifest. Minimal, fail-closed:
    schema_version + the two corrupt-arm blocks must be present."""

    resolved = Path(path)
    document = json.loads(resolved.read_text(encoding="utf-8"))
    for field in ("schema_version", "seed", "corrupt_arms"):
        if field not in document:
            raise PpromptBindingError(f"P-PROMPT binding manifest {resolved} is missing top-level field {field!r}")
    for arm in ("X1", "X2"):
        if arm not in document["corrupt_arms"]:
            raise PpromptBindingError(f"P-PROMPT binding manifest {resolved} is missing corrupt_arms[{arm!r}]")
    return document


def load_x2_tail_segments(binding: Mapping, data_dir: Path | str) -> dict[str, tuple[Segment, ...]]:
    """X2's real-I/O step (module docstring): re-read the P-ATTR smoke's
    archived A-turn reply JSONL, look up every donor entry the binding
    manifest named (by its own ``donor_request_id``), and verify its text's
    sha256 against the pin -- raising on the first mismatch rather than
    building a request over unverified/substituted text."""

    x2 = binding["corrupt_arms"]["X2"]
    source_path = Path(data_dir) / x2["donor_source_relpath"]
    if not source_path.is_file():
        raise PpromptBindingError(f"X2 donor source not found: {source_path}")

    by_request_id: dict[str, dict] = {}
    for line in source_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        by_request_id[record["request_id"]] = record

    result: dict[str, tuple[Segment, ...]] = {}
    for target_meeting, entries in x2["tail_entries"].items():
        segments: list[Segment] = []
        for entry in entries:
            donor_id = entry["donor_request_id"]
            record = by_request_id.get(donor_id)
            if record is None:
                raise PpromptBindingError(
                    f"X2 donor request {donor_id!r} (for target meeting {target_meeting!r}) not found "
                    f"in {source_path}"
                )
            text = record["text"]
            actual_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if actual_sha256 != entry["text_sha256"]:
                raise PpromptBindingError(
                    f"X2 donor text hash mismatch for {donor_id!r}: pinned {entry['text_sha256']}, "
                    f"actual {actual_sha256} -- refusing to build a request over unverified text"
                )
            segments.append(Segment(id=donor_id, speaker=str(entry["speaker"]), start=0.0, end=0.0, text=text))
        result[target_meeting] = tuple(segments)
    return result


class ResponseSink:
    """Append-only JSONL sink for a flight's replies -- identical shape to
    ``scripts/launch_pattr_smoke.py::ResponseSink`` (module docstring: one
    line per completed request, fsynced before the next request is sent)."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")
        self.n_written = 0

    def write(self, record: Mapping[str, object]) -> None:
        self._handle.write(json.dumps(record, sort_keys=True) + "\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self.n_written += 1

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> "ResponseSink":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def load_recorded_request_ids(path: Path | str) -> set[str]:
    """Same resume-set rule as the P-ATTR launcher's own helper."""

    resolved = Path(path)
    done: set[str] = set()
    if not resolved.is_file():
        return done
    for line in resolved.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if record.get("outcome") == "ok" and isinstance(record.get("request_id"), str):
            done.add(record["request_id"])
    return done


def run_arm(
    arm: str,
    pattr_manifest: PattrManifest,
    binding: Mapping,
    *,
    data_dir: Path,
    transport: LlamaServerTransport,
    receipt: FlightReceipt,
    sink: ResponseSink | None = None,
    skip_request_ids: Iterable[str] = (),
    decoding_params: Mapping[str, object] | None = None,
    progress_every: int = 0,
) -> FlightReceipt:
    """Dispatch every one of ``arm``'s 24 built requests through
    ``transport`` and record each response onto ``receipt`` -- identical
    control flow to ``scripts/launch_pattr_smoke.py::run_arm``, the one
    difference being how the request specs are built (X1 needs the binding
    manifest's label derangement; X2 needs freshly-resolved, hash-verified
    donor tail text)."""

    derangement = binding["corrupt_arms"]["X1"]["label_derangement"] if arm == ARM_X1 else None
    tail_segments_by_meeting = load_x2_tail_segments(binding, data_dir) if arm == ARM_X2 else None

    specs = build_arm_requests(
        pattr_manifest, arm, derangement=derangement, tail_segments_by_meeting=tail_segments_by_meeting
    )

    skip = set(skip_request_ids)
    extra = dict(decoding_params or {})
    started = time.monotonic()
    n_flown = 0
    for index, spec in enumerate(specs, start=1):
        if spec.request_id in skip:
            continue
        kwargs = spec.to_transport_kwargs(data_dir=data_dir)
        if extra:
            kwargs["decoding_params"] = {**dict(kwargs.get("decoding_params") or {}), **extra}
        try:
            response = transport.request(**kwargs)
        except Exception as error:  # noqa: BLE001 -- persisted, then re-raised
            if sink is not None:
                sink.write(
                    {
                        **spec.to_dict(),
                        "outcome": "error",
                        "error_type": type(error).__name__,
                        "error": str(error),
                        "recorded_utc": datetime.now(timezone.utc).isoformat(),
                    }
                )
            raise
        receipt.record(response)
        n_flown += 1
        if sink is not None:
            sink.write(
                {
                    **spec.to_dict(),
                    "outcome": "ok",
                    "response_request_id": response.request_id,
                    "text": response.text,
                    "usage": dict(response.usage),
                    "attempts": [a.as_json() for a in response.attempts],
                    "recorded_utc": datetime.now(timezone.utc).isoformat(),
                }
            )
        if progress_every and n_flown % progress_every == 0:
            elapsed = time.monotonic() - started
            print(
                f"[{arm}] {index}/{len(specs)} specs seen, {n_flown} flown this process, "
                f"{elapsed:.1f}s elapsed, {elapsed / n_flown:.2f}s/request",
                file=sys.stderr,
                flush=True,
            )
    return receipt


def build_transport_and_receipt(
    *,
    base_url: str,
    model_path: str,
    model_sha256: str,
    max_calls: int,
    max_audio_seconds: float,
    slots: int,
    timeout_seconds: float = 300.0,
) -> tuple[LlamaServerTransport, FlightReceipt]:
    budget = CallBudget(BudgetLimits(max_calls=max_calls, max_audio_seconds=max_audio_seconds))
    server_identity = ServerIdentity(
        base_url=base_url, model_files=(ModelFileRef(path=model_path, sha256=model_sha256),), slots=slots
    )
    transport = LlamaServerTransport(
        TransportConfig(base_url=base_url, slots=slots, timeout_seconds=timeout_seconds), budget
    )
    receipt = FlightReceipt(server_identity, budget)
    return transport, receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True, help="SPEECHRL_DATA_DIR root")
    parser.add_argument(
        "--pattr-manifest", required=True, help="frozen P-ATTR manifest JSON (audio identity, reused verbatim)"
    )
    parser.add_argument("--binding", required=True, help="frozen P-PROMPT binding manifest JSON")
    parser.add_argument("--arm", required=True, choices=ARMS, help="which of the 14 arms to fly")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="print the arm's request-count/audio-seconds summary and exit -- no transport call",
    )
    parser.add_argument("--base-url", default=None, help="llama-server base URL, e.g. http://127.0.0.1:8080")
    parser.add_argument("--model-path", default=None, help="GGUF path as configured (receipt identity only)")
    parser.add_argument("--model-sha256", default=None, help="GGUF sha256 as configured (receipt identity only)")
    parser.add_argument("--slots", type=int, default=4)
    parser.add_argument("--max-calls", type=int, default=None, help="hard call-count budget for this arm")
    parser.add_argument(
        "--max-audio-seconds", type=float, default=None, help="hard audio-seconds budget for this arm"
    )
    parser.add_argument("--receipt-out", default=None, help="where to write the flight receipt JSON")
    parser.add_argument(
        "--responses-out",
        default=None,
        help="JSONL sink for this arm's replies -- the read mission's input (required for a real flight)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="skip every request id already recorded ok in --responses-out (no double spend)",
    )
    parser.add_argument("--temperature", type=float, default=None, help="decoding_params.temperature")
    parser.add_argument("--max-tokens", type=int, default=None, help="decoding_params.max_tokens (generation cap)")
    parser.add_argument("--seed", type=int, default=None, help="decoding_params.seed")
    parser.add_argument("--timeout-seconds", type=float, default=300.0, help="per-request HTTP timeout")
    parser.add_argument("--progress-every", type=int, default=0, help="log a progress line every N flown requests")
    args = parser.parse_args(argv)

    pattr_manifest = load_pattr_manifest(args.pattr_manifest)
    binding = load_pprompt_binding(args.binding)

    if args.summary_only:
        derangement = binding["corrupt_arms"]["X1"]["label_derangement"] if args.arm == ARM_X1 else None
        tail_segments_by_meeting = (
            load_x2_tail_segments(binding, args.data_dir) if args.arm == ARM_X2 else None
        )
        specs = build_arm_requests(
            pattr_manifest, args.arm, derangement=derangement, tail_segments_by_meeting=tail_segments_by_meeting
        )
        summary = {arm: s.to_dict() for arm, s in summarize_all_requests(specs).items()}
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    missing = [
        name
        for name, value in (
            ("--base-url", args.base_url),
            ("--model-path", args.model_path),
            ("--model-sha256", args.model_sha256),
            ("--max-calls", args.max_calls),
            ("--max-audio-seconds", args.max_audio_seconds),
            ("--receipt-out", args.receipt_out),
            ("--responses-out", args.responses_out),
        )
        if value is None
    ]
    if missing:
        parser.error(f"the following arguments are required for a real flight (omit only with --summary-only): {missing}")

    transport, receipt = build_transport_and_receipt(
        base_url=args.base_url,
        model_path=args.model_path,
        model_sha256=args.model_sha256,
        max_calls=args.max_calls,
        max_audio_seconds=args.max_audio_seconds,
        slots=args.slots,
        timeout_seconds=args.timeout_seconds,
    )
    decoding_params = {
        key: value
        for key, value in (
            ("temperature", args.temperature),
            ("max_tokens", args.max_tokens),
            ("seed", args.seed),
        )
        if value is not None
    }
    already = load_recorded_request_ids(args.responses_out) if args.resume else set()
    if already:
        print(f"resume: skipping {len(already)} already-recorded request(s)", file=sys.stderr)

    try:
        with ResponseSink(args.responses_out) as sink:
            run_arm(
                args.arm,
                pattr_manifest,
                binding,
                data_dir=Path(args.data_dir),
                transport=transport,
                receipt=receipt,
                sink=sink,
                skip_request_ids=already,
                decoding_params=decoding_params,
                progress_every=args.progress_every,
            )
    finally:
        receipt.write(Path(args.receipt_out), repo_root=Path(__file__).resolve().parent.parent)
        print(
            f"wrote {args.receipt_out} (ledger entries: {len(receipt.entries)}, "
            f"budget: {receipt.budget.totals})",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
