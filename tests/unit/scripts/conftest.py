"""Local conftest for testing the standalone ``scripts/*.py`` modules.

``scripts/`` is not an installed package (mirrors every existing script's
own sys.path bootstrap, e.g. ``scripts/build_ami_role_registry.py``), so
importing one of its modules from a test needs the same ``sys.path``
treatment the root ``conftest.py`` already gives ``src/``."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
