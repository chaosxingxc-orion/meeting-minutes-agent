"""Root pytest conftest.

This repository is never `pip install -e`'d into the shared program venv
(CLAUDE.md: "never pip install into it from agents; report missing
dependencies instead"). Tests are expected to run with
``PYTHONPATH=<repo>/src`` set by the caller, but this shim makes `pytest`
work unattended too by inserting ``src/`` onto ``sys.path`` if the package
is not already importable. No install, no side effects on the environment.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
