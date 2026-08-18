"""Capability-smoke probes: small, pre-registered arm comparisons that test
a single load-bearing capability ASSUMPTION before it is designed on, per
the owner ruling recorded in
``docs/readiness/2026-08-18-g1-preregistration-draft.md`` SS0 ("never
design on an assumed capability").

:mod:`.pattr` -- the P-ATTR capability smoke: does the frozen core respect a
DECLARED per-slice turn/speaker grid when attributing multi-speaker
transcript text (the LISTEN design's core assumption), and if not, what does
the zero-attribution-risk per-turn fallback (A-turn) cost in call count and
WER? Three arms (A-grid / A-free / A-turn), one frozen manifest, deterministic
request builders -- this package builds the machinery only; a flight (real
model contact) is a separate, later mission.
:mod:`.pattr_scoring` -- the offline scoring path consuming a flight's parsed
replies: per-speaker hypothesis streams, cpWER/confusion-cost metrics against
the AMI gold streams, and the A-grid boundary-respect diagnostic.
"""

from __future__ import annotations
