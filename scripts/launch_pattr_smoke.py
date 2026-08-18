#!/usr/bin/env python3
"""P-ATTR smoke flight launcher -- SKELETON: wiring only.

This engineering mission builds and import-verifies this script; it never
runs it against a live server (zero model contact, CLAUDE.md). The FLIGHT
mission (a separate, later mission) runs it against a real ``llama-server``.

Wires: the frozen manifest (:mod:`meeting_minutes_agent.probes.pattr`) ->
one arm's request specs -> :class:`~meeting_minutes_agent.client.transport.
LlamaServerTransport` -> a :class:`~meeting_minutes_agent.client.receipts.
FlightReceipt`. No policy lives here beyond that wiring: budgets, server
identity, and which arm to fly are all caller-supplied CLI arguments, never
hardcoded, so the flight mission fixes them at call time from its own
pre-registered budget, not from a default this script would otherwise bake
in.

``--summary-only`` is the one mode safe to run right now: it loads the
manifest and prints :func:`~meeting_minutes_agent.probes.pattr.summarize_all_arms`'s
per-arm expected request count and total audio seconds -- no transport
call, no server required.

Reply persistence (``--responses-out``, added by the FLIGHT mission, which
found the skeleton dropped every reply on the floor): a
:class:`ResponseSink` appends ONE json line per completed request --
the spec's own scoring metadata (arm/meeting/slice/turn/known_speaker/
template_id) plus the reply text, usage and full attempt chain -- and
fsyncs it before the next request is sent. That file, never the receipt,
is what the separate SCORING mission reads
(:mod:`meeting_minutes_agent.probes.pattr_scoring` scores "already-collected
records"); the receipt stays operational metadata (identity, ledger,
budget totals). Because each line lands before the next call, a crash
costs at most the in-flight request, and ``--resume`` re-reads the file and
skips every request id already recorded -- no double spend against a
pre-registered ceiling.

Decoding params (``--temperature`` / ``--max-tokens`` / ``--seed``): the
P-ATTR request builders carry none, which leaves generation length capped
only by the server's context -- one degenerate repetition loop could eat a
whole flight's GPU-hour ceiling. These flags merge onto every request's
``decoding_params``; a caller that passes none preserves the skeleton's
original behaviour exactly. Truncation stays visible without a transport
change: a reply whose ``usage.completion_tokens`` equals ``--max-tokens``
hit the cap.

Usage (the FLIGHT mission)::

    python scripts/launch_pattr_smoke.py \\
        --data-dir "$SPEECHRL_DATA_DIR" \\
        --manifest configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json \\
        --arm A-grid \\
        --base-url http://127.0.0.1:8080 \\
        --model-path /home/chao/models/<pinned-gguf> --model-sha256 <sha256> \\
        --max-calls 30 --max-audio-seconds 3600 \\
        --receipt-out docs/checks/<campaign>/<release-id>/pattr-smoke-a-grid-receipt.json

Usage (safe right now -- no server, no model contact)::

    python scripts/launch_pattr_smoke.py \\
        --data-dir "$SPEECHRL_DATA_DIR" \\
        --manifest configs/probes/pattr/2026-08-18-pattr-smoke-manifest.json \\
        --arm A-grid --summary-only
"""

from __future__ import annotations

import argparse
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

from meeting_minutes_agent.client.budgets import BudgetLimits, CallBudget  # noqa: E402
from meeting_minutes_agent.client.receipts import FlightReceipt, ModelFileRef, ServerIdentity  # noqa: E402
from meeting_minutes_agent.client.transport import LlamaServerTransport, TransportConfig  # noqa: E402
from meeting_minutes_agent.probes.pattr import (  # noqa: E402
    ARMS,
    PattrManifest,
    build_arm_requests,
    load_pattr_manifest,
    summarize_all_arms,
)


class ResponseSink:
    """Append-only JSONL sink for a flight's replies (module docstring).

    One line per completed request, written and fsynced BEFORE the next
    request is dispatched, so a crash can cost at most the in-flight
    request. This class never inspects reply text -- it only persists it
    for the separate scoring mission."""

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
    """Every ``request_id`` already carrying an ``ok`` record in a previous
    run's JSONL -- the resume set. A truncated final line (a crash mid-write)
    is skipped rather than fatal; an ``error`` record is NOT counted as done,
    so a failed request is retried on resume."""

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
    manifest: PattrManifest,
    *,
    data_dir: Path,
    transport: LlamaServerTransport,
    receipt: FlightReceipt,
    sink: ResponseSink | None = None,
    skip_request_ids: Iterable[str] = (),
    decoding_params: Mapping[str, object] | None = None,
    progress_every: int = 0,
) -> FlightReceipt:
    """Dispatch every one of ``arm``'s built requests through ``transport``
    and record each response onto ``receipt``. ``transport``/``receipt``
    are caller-constructed (never built here) so a test can inject a fake
    transport/budget without this function knowing the difference -- the
    same injection seam :class:`~meeting_minutes_agent.client.transport.
    LlamaServerTransport` itself already offers via its own ``post``
    parameter.

    ``sink`` (when given) receives one persisted record per request, before
    the next one is dispatched; ``skip_request_ids`` are the already-flown
    ids a resume must not re-spend; ``decoding_params`` merges onto every
    request's own (empty) params. A failing request writes an ``error``
    record to ``sink`` and then propagates -- fail-closed, with everything
    that flew already durable on disk."""

    skip = set(skip_request_ids)
    extra = dict(decoding_params or {})
    specs = build_arm_requests(manifest, arm)
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
        "--manifest", required=True, help="frozen P-ATTR manifest JSON (configs/probes/pattr/*-smoke-manifest.json)"
    )
    parser.add_argument("--arm", required=True, choices=ARMS, help="which arm to fly")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="print the manifest's per-arm request-count/audio-seconds summary and exit -- no transport call",
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
        help="JSONL sink for this arm's replies -- the scoring mission's input (required for a real flight)",
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

    manifest = load_pattr_manifest(args.manifest)

    if args.summary_only:
        summary = {arm: s.to_dict() for arm, s in summarize_all_arms(manifest).items()}
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

    # The receipt is written in a finally block: a flight that dies at
    # request N must still leave the operational ledger for the N-1 that
    # flew, exactly like the reply sink already does per request.
    try:
        with ResponseSink(args.responses_out) as sink:
            run_arm(
                args.arm,
                manifest,
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
