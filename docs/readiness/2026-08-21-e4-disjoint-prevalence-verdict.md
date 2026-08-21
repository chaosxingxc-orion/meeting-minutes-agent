# E4-DISJOINT-PREV formal verdict

Date: 2026-08-21. Formal screening decision: **`PREVALENCE-SCREEN-PASS`**.

## Result

The registered staged Pass-0 pilot ran60 untouched dialogues in three20-dialogue increments. All795 requests succeeded with no retry, error, or skip, consuming9,231.897 audio-seconds (2.564 hours). No second-pass request was made.

Stage20 estimated prevalence at62.96% and continued. Stage40 estimated54.81% and continued. At the frozen stage60 endpoint, 163 of164 natural carry targets had usable equal-width state; 86 were `speaker_wrong_disjoint`, yielding52.76% prevalence. The dialogue-cluster bootstrap80% interval was46.71%–59.01%, the90% interval was44.91%–60.78%, and usable carry fraction was99.43%.

The final point estimate exceeds the48.2938% break-even threshold, the80% lower bound exceeds the40% screening floor, and usable carry exceeds85%. All registered screen-pass conditions therefore hold.

## Limitations

This is an engineering prevalence screen, not an effect experiment. It contains no global/speaker second-pass contrast and says nothing new about carry repair, WER, or false hints. The server binary differed from the historical E4-CF record and was amended before model contact; results describe the current pinned stack and cannot isolate a data-only prevalence difference.

Three of795 responses reached the512-token cap. They affect at most eight natural targets. A conservative deletion bound leaves prevalence at50.32%, still above break-even, although the formal result remains the preregistered all-response read.

## Consequence

The earlier assumption that prevalence might be near50% is plausible enough for resource planning, so the power failure cannot be summarized simply as “prevalence is probably too low.” The remaining obstacle is cost: the prior 3 pp / 50% scenario still projects1,577 dialogues,31,749 calls, and101.55 repeated audio-hours.

This screen does not authorize that flight. A low-cost next step, if explicitly authorized and newly preregistered, is an exploratory paired D0-global versus D1-speaker second pass restricted to this pilot's predicate-positive targets. It would estimate direction with roughly172 calls, but would remain underpowered and non-confirmatory.

- Registration: `docs/readiness/2026-08-21-e4-disjoint-prevalence-preregistration.md`.
- Server amendment: `docs/readiness/2026-08-21-e4-disjoint-prevalence-server-amendment.md`.
- Flight evidence: `docs/checks/2026-08-21-e4-disjoint-prev-flight/`.
- Read evidence: `docs/checks/2026-08-21-e4-disjoint-prev-read/`.
