# Earnings-22 Sortformer full-corpus read

## Verdict

`MAIN-SPEAKER-DIARIZATION-USABLE` on the preregistered 30-meeting target:
calls with more than four reference speakers, sufficient alignment, and Top-2 aligned
speech share at least 60%.

| Population | Meetings | All error | Top-1 error | Top-2 error | Tail error |
|---|---:|---:|---:|---:|---:|
| Primary dominant-speaker target | 30 | 33.18% | **14.30%** | **22.59%** | 72.75% |
| Evaluable, >4 speakers | 76 | 49.32% | 12.72% | 26.99% | 78.88% |
| 5–8 reference speakers | 21 | 20.88% | 2.25% | 13.03% | 59.83% |
| 9–16 reference speakers | 39 | 44.89% | 17.61% | 29.81% | 75.53% |
| >16 reference speakers | 55 scorable | 57.66% | 10.08% | 29.32% | 81.92% |

The primary pooled Top-1 and Top-2 errors pass the registered <=20% and <=25% gates.
The result supports the proposed mechanism: four output slots can retain dominant
presenters even when many rare participants appear. It does not support complete
speaker separation. All 30 target meetings emitted four hypothesis labels, and only
14/30 individually had Top-2 error <=25%; the pooled result is duration-weighted and
performance is heterogeneous.

## Run integrity

All 125 files were converted to mono 16 kHz PCM16 and contacted by the pinned Q8
Sortformer. The flight produced 125 non-empty RTTMs with zero failures in 3.06081 campaign
wall hours. An initial concurrent resume stopped at 112 files because the budget guard
incorrectly summed simultaneous contact durations. Before any score read, the guard was
corrected to enforce actual campaign elapsed time; the four-hour ceiling and every model
parameter remained unchanged. The final 13 contacts completed within the original limit.

## Scoring limits

Earnings-22 supplies force-aligned word timestamps, not human RTTM. The primary measure
therefore scores speaker attribution at aligned words after a global exact one-to-one
mapping. One file has no aligned words and is structurally reported but unscorable.
The reconstructed-turn proxy DER (fixed 1.0 s merge gap) is 42.65% on the primary group
without a collar; it is sensitive to reference sparsity and must not be called official
DER. Gold speaker counts and timestamps were scoring-side only.

No Omni call occurred. This result can justify retaining Sortformer for main-presenter
routing on the dominant-speaker subset, but long-tail speakers need fallback handling or
must be excluded from speaker-specific optimization claims.
