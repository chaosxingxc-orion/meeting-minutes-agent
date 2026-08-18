"""E5 measurement layer: attribution/WER-family metrics (meeteval wrappers),
an anti-gaming timestamp validator, the MeetingQA F1/IoU scorer, glossary
diagnostics, a legacy ROUGE row, and the SAER-M speaker-attribution metric.

Engineering-only module: nothing here contacts a model, downloads data, or
performs GPU work. Heavy third-party imports (meeteval, rouge_score) stay
function-local so importing this package never requires those libraries to
be installed -- only calling the functions that use them does.
"""

from __future__ import annotations
