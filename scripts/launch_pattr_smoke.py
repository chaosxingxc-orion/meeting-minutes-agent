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
import sys
from pathlib import Path

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


def run_arm(
    arm: str,
    manifest: PattrManifest,
    *,
    data_dir: Path,
    transport: LlamaServerTransport,
    receipt: FlightReceipt,
) -> FlightReceipt:
    """Dispatch every one of ``arm``'s built requests through ``transport``
    and record each response onto ``receipt``. ``transport``/``receipt``
    are caller-constructed (never built here) so a test can inject a fake
    transport/budget without this function knowing the difference -- the
    same injection seam :class:`~meeting_minutes_agent.client.transport.
    LlamaServerTransport` itself already offers via its own ``post``
    parameter."""

    for spec in build_arm_requests(manifest, arm):
        kwargs = spec.to_transport_kwargs(data_dir=data_dir)
        response = transport.request(**kwargs)
        receipt.record(response)
    return receipt


def build_transport_and_receipt(
    *,
    base_url: str,
    model_path: str,
    model_sha256: str,
    max_calls: int,
    max_audio_seconds: float,
    slots: int,
) -> tuple[LlamaServerTransport, FlightReceipt]:
    budget = CallBudget(BudgetLimits(max_calls=max_calls, max_audio_seconds=max_audio_seconds))
    server_identity = ServerIdentity(
        base_url=base_url, model_files=(ModelFileRef(path=model_path, sha256=model_sha256),), slots=slots
    )
    transport = LlamaServerTransport(TransportConfig(base_url=base_url, slots=slots), budget)
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
    )
    run_arm(args.arm, manifest, data_dir=Path(args.data_dir), transport=transport, receipt=receipt)
    receipt.write(Path(args.receipt_out), repo_root=Path(__file__).resolve().parent.parent)
    print(f"wrote {args.receipt_out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
