# E4-DISJOINT-POWER formal verdict

Date: 2026-08-21. Formal machine decision: **`INSUFFICIENT-CARRY-SUPPLY`**.

## Result

The registered one-shot zero-model census excluded all 299 previously seen dialogues and retained 4,974 untouched dialogues. They contain 6,423 carry mentions overall, but the frozen roster rule admits only dialogues with at least two carry mentions. That eligible pool contains 1,634 dialogues and 4,782 carry mentions.

The primary 3 pp MDE / 40% predicate-prevalence scenario requires 1,963 analyzable predicate carry mentions, or 5,774 raw carry mentions after the frozen prevalence and 85% usable-state adjustment. The eligible pool is short by 992 carry mentions (17.2% of the requirement), so no primary candidate roster was emitted.

## Scenario interpretation

The 3 pp scenario is arithmetically feasible at assumed prevalence 50% or the E4-CF descriptive 54.01%, but those plans require respectively 1,577/1,457 dialogues, 31,749/29,536 deduplicated calls, and 101.55/94.51 repeated audio-hours. Unseen prevalence cannot be measured without new Pass-0 outputs, so neither assumption is confirmation evidence or a safe basis for silently launching a flight.

The 4 pp / 40% scenario requires 1,102 dialogues, 22,013 calls, and 70.37 hours. Relaxing the MDE to 4 pp after observing a 3.79 pp exploratory contrast would make the confirmation target less aligned with the generated hypothesis. The 5 pp scenarios are cheaper but no longer test the small-effect mechanism that motivated this experiment.

## Decision

Do not launch E4-DISJOINT under the registered primary design. Do not lower the MDE, raise assumed prevalence, or drop the dialogue eligibility rule post hoc. The fixed policy remains an unconfirmed hypothesis rather than a disproven one, and the training-free agent loop remains unauthorized.

A future experiment requires a materially new source of independent carry-dense dialogues or an owner-approved staged Pass-0 design with a preregistered predicate attrition gate and explicit budget. Such a design is a new registration and cannot reuse this verdict as authorization.

- Registration: `docs/readiness/2026-08-21-e4-disjoint-power-registration.md`
- Evidence: `docs/checks/2026-08-21-e4-disjoint-power/`
- Prior mechanism verdict: `docs/readiness/2026-08-21-e4-cf-mechanism-verdict.md`
