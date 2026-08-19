#!/usr/bin/env python3
"""DIAR-SMOKE Arm A wrapper: NeMo fp32 Sortformer v2 -> RTTM.

Runs inside the isolated reference venv (/home/chao/.venvs/diar; nemo_toolkit
3.0.0, torch 2.9.1+cu128 -- acquisition receipt, umbrella
docs/checks/meeting-minutes-agent/2026-08-18-diar-acquisition/README.md).
Card-default inference: SortformerEncLabelModel.restore_from(<pinned .nemo>)
followed by the one-click .diarize() runner with default post-processing --
no threshold, geometry, or post-processing override anywhere. The model's own
shipped configuration (including its streaming/offline geometry) IS the pin.

Output: standard RTTM SPEAKER lines (NIST 10-field shape), one per segment,
exactly what meeting_minutes_agent.chunking.rttm.parse_rttm_file consumes.
This wrapper never reads gold annotations and never scores anything -- it
maps audio bytes to a speaker-turn table, nothing else.
"""

from __future__ import annotations

import argparse
import os
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="pinned .nemo checkpoint path")
    parser.add_argument("--audio", required=True, help="input WAV path")
    parser.add_argument("--rttm", required=True, help="output RTTM path")
    parser.add_argument("--recording-id", required=True, help="RTTM field-2 recording id")
    args = parser.parse_args()

    # Belt-and-braces offline discipline: the pinned checkpoint is a local
    # file; no hub lookup is ever needed or allowed.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    import torch  # noqa: PLC0415 -- venv-local heavy import kept in main
    from nemo.collections.asr.models import SortformerEncLabelModel  # noqa: PLC0415

    print(
        f"arm-a-wrapper: torch {torch.__version__} cuda_available={torch.cuda.is_available()}",
        flush=True,
    )

    t_load = time.monotonic()
    model = SortformerEncLabelModel.restore_from(args.model, map_location="cpu")
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    print(
        f"arm-a-wrapper: model restored ({time.monotonic() - t_load:.1f}s) on {device}; "
        f"streaming_mode={getattr(model, 'streaming_mode', None)}",
        flush=True,
    )

    t_diar = time.monotonic()
    segments = model.diarize(audio=[args.audio], batch_size=1, verbose=False)
    diar_wall = time.monotonic() - t_diar
    print(f"arm-a-wrapper: diarize wall {diar_wall:.1f}s", flush=True)

    lines = segments[0]
    rttm_lines: list[str] = []
    n_skipped = 0
    for raw in lines:
        parts = str(raw).split()
        if len(parts) != 3:
            print(f"arm-a-wrapper: WARNING unparseable segment skipped: {raw!r}", file=sys.stderr)
            n_skipped += 1
            continue
        start, end, speaker = float(parts[0]), float(parts[1]), parts[2]
        duration = end - start
        if duration <= 0:
            print(f"arm-a-wrapper: WARNING non-positive-duration segment skipped: {raw!r}", file=sys.stderr)
            n_skipped += 1
            continue
        rttm_lines.append(
            f"SPEAKER {args.recording_id} 1 {start:.3f} {duration:.3f} <NA> <NA> {speaker} <NA> <NA>"
        )

    with open(args.rttm, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(rttm_lines) + ("\n" if rttm_lines else ""))
    print(
        f"arm-a-wrapper: RTTM written {args.rttm} ({len(rttm_lines)} SPEAKER lines, {n_skipped} skipped)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
