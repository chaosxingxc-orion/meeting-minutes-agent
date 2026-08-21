# E4-DISJOINT fixed-policy confirmation — preregistration draft

Date: 2026-08-21. Status: **DRAFT RETIRED UNDER THE REGISTERED PRIMARY POWER DESIGN; no model contact authorized**.

The subsequent E4-DISJOINT-POWER census returned `INSUFFICIENT-CARRY-SUPPLY`. This draft must not be promoted by relaxing its MDE or prevalence assumptions post hoc. A materially new data source or staged design requires a new preregistration.

## Fixed policy hypothesis

For each target, normalize the legal Pass-0-derived correct-speaker and wrong-speaker inventories. If both sets are disjoint, inject the correct-speaker inventory; otherwise inject the equal-width global inventory. The policy uses no reference text, entity labels, ASR error signal, or model self-evaluation.

The E4-CF-MECH screen selected this predicate post hoc. That result is hypothesis generation only. All 287 E4-CF dialogues and the earlier 12 discovery dialogues must be excluded from the next surface.

## Proposed arms

- `D0-global`: always inject the equal-width global inventory.
- `D1-speaker`: always inject the correct-speaker inventory.
- `D2-disjoint-policy`: speaker when speaker/wrong inventories are disjoint, otherwise global.
- `D3-wrong`: equal-width wrong-speaker negative control on targets where the policy selects speaker.

All arms reuse byte-identical target audio and frozen decode settings. Every eligible target runs; there is no error-based target selector and no selective re-listening.

## Outcomes and safety

The primary contrast is carry exact hit rate `D2-D0`, clustered by dialogue. Secondary contrasts are carry NE-WER and `D2-D1`. Safety endpoints are overall WER non-inferiority, false-hint target rate, truncation, and calls/audio budget. Numeric MDE, sample size, non-inferiority margins, attrition rules, and decision order remain unset until a zero-model census of an untouched roster is completed.

## Required work before registration

1. Census untouched ContextASR dialogues after excluding all 299 previously viewed dialogues.
2. Estimate dialogue clustering, predicate prevalence, carry supply, MDE, calls, and repeated audio hours.
3. Freeze runtime/score separation, renderer hash, failure handling, one-shot read, and all numeric gates.
4. Obtain explicit owner authorization for the resulting budget.

This draft authorizes none of those model calls and cannot be cited as confirmation of the disjoint policy.
