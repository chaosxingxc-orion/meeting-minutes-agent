# E-MATERIAL-LHCP-ELIGIBLE-COHORT preregistration

## Question and claim boundary

Can the 70 talks that passed the frozen pre-model material-supply gate be frozen as
a development/confirmation cohort without using reference text or model outcomes?

This is an eligibility-filtered independent surface, not a reinterpretation of the
failed 72/72 supply result. Any later claim applies only to the 70 material-compatible
talks and must report that two original `test_2020` talks were excluded before model
contact.

## Frozen eligibility and splits

Include a talk if and only if `E-MATERIAL-LHCP-SUPPLY` marked it `passed=true` under
the already frozen parser, 200-character, and eight-candidate rules. Exclude exactly
`856696c36.wav` and `856696c52.wav` because their sole PDFs triggered the registered
parser's `LimitReachedError`. Do not repair, replace, OCR, or reassign either talk in
this cohort.

Preserve the published split identity:

- development: all 14 `dev_2020` plus all 11 `dev_2022` talks, total 25;
- confirmation: 13 eligible `test_2020` plus all 32 `test_2022` talks, total 45.

The freezer must bind the 72-talk admission manifest, the supply verdict, the
`TRACE_COMPLETE` validation, and its own code hash. It passes only with 70 unique
talks, exactly 25 development and 45 confirmation talks, and exactly the two frozen
exclusions.

## Authorization boundary

This registration authorizes only cohort construction and offline validation. It
does not authorize audio acquisition, Pass0, embedding, Omni, reference reading, or
material-parser salvage. A later development Pass0/material-routing experiment must
receive its own prospective registration and explicit model authorization.

