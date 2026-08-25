#!/usr/bin/env python3
"""Synthetic-only health check for the frozen encode-only embedding runtime."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import tempfile

from audit_meeting_material_semantic_signal import embed_batch, sha256_file, wait_for_server


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--server-binary", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18762)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if sha256_file(args.model) != str(config["model_sha256"]):
        parser.error("model hash mismatch")
    if sha256_file(args.server_binary) != str(config["server_binary_sha256"]):
        parser.error("server binary hash mismatch")
    with tempfile.TemporaryDirectory(prefix="embedding-runtime-check-") as temporary:
        log_path = Path(temporary) / "server.log"
        with log_path.open("wb") as log:
            process = subprocess.Popen(
                [
                    str(args.server_binary), "--model", str(args.model), "--embedding",
                    "--pooling", "last", "--n-gpu-layers", "99", "--ctx-size", "8192",
                    "--host", "127.0.0.1", "--port", str(args.port),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                url = f"http://127.0.0.1:{args.port}"
                wait_for_server(url, process)
                vectors = embed_batch(url, ["synthetic alpha", "synthetic beta"])
            finally:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    result = {
        "rows": len(vectors),
        "dimensions": [len(vector) for vector in vectors],
        "norms": [math.sqrt(sum(value * value for value in vector)) for vector in vectors],
    }
    if result["rows"] != 2 or result["dimensions"] != [1024, 1024] or any(not value for value in result["norms"]):
        raise RuntimeError(f"unexpected embedding runtime response: {result}")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
