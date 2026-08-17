"""meeting-minutes-agent: an AI meeting-notes agent on a frozen speech-capable
omni core (engineering scaffold).

Package top-level imports stay light by design (program convention): no
torch/transformers/librosa/xml-heavy imports here. Submodules that need such
dependencies import them locally, inside the functions that use them.
"""

from __future__ import annotations

__version__ = "0.1.0"
