"""``SupplyArmConfig``: prompt-supply arm switches consumed AS DATA.

Backbone design doc SS1 ("Registered experiment arms are switches ... no arm
logic is ever hard-coded into heads or corpora"): :mod:`.render` has exactly
ONE deterministic render function; every arm variant is a different
:class:`SupplyArmConfig` value fed into that SAME function, never a
different code path. This mirrors how :mod:`meeting_minutes_agent.glossary.arms`
registers its REVISE-stage arms -- but where that module's arms are
different PIPELINE CONSTRUCTIONS (each arm skips/perturbs a different
extract/normalise/dedupe/gate stage, so it needs one constructor function
per arm), a supply block has no stages to skip: every registered supply arm
is fully described by which sections are included and how tightly they are
capped. So the mirroring here is a dataclass-of-data, not a family of
constructor functions -- there is nothing left for per-arm logic to do.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupplyArmConfig:
    """One supply-block arm's dose caps and section toggles.

    ``max_glossary_terms`` / ``max_speaker_bindings`` cap each section's own
    item count (``None`` = uncapped). ``max_supply_tokens_estimate`` is a
    whole-block safety-net cap on the rendered text's estimated token count
    (``None`` = uncapped); see :mod:`.render` for the exact, documented
    truncation order applied when this cap forces cuts beyond what the
    per-section caps already did.
    """

    max_glossary_terms: int | None = None
    max_speaker_bindings: int | None = None
    max_supply_tokens_estimate: int | None = None
    include_glossary: bool = True
    include_speaker_map: bool = True
    include_format_instructions: bool = True

    def validate(self) -> "SupplyArmConfig":
        for name in ("max_glossary_terms", "max_speaker_bindings", "max_supply_tokens_estimate"):
            value = getattr(self, name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer or None, got {value!r}")
        return self


__all__ = ["SupplyArmConfig"]
