# EARNINGS22-SORTFORMER-SMOKE verdict

The full 125-meeting pinned-tool flight completed with zero failures in 3.06081 wall
hours. The sole scoring read produced `MAIN-SPEAKER-DIARIZATION-USABLE`.

On the frozen 30-meeting `>4 speakers + Top-2 share >=60%` population, pooled aligned-word
speaker-attribution error is 14.30% for Top-1 and 22.59% for Top-2, clearing the registered
20%/25% limits. Tail error is 72.75%, so the result proves conditional main-speaker utility,
not full diarization of rare participants. Across all 76 evaluable >4-speaker meetings,
Top-2 error rises to 26.99%.

The operational budget-guard correction at 112/125 changed only concurrent wall-time
accounting and was committed before reference scoring. It did not change the roster,
audio, model, parameters, outputs already produced, metric definitions, or thresholds.

This verdict allows a future Omni pilot only if its claim and routing population are
explicitly limited to dominant presenters under a separately registered design. It does
not authorize model contact, long-tail speaker claims, diarizer optimization, or an agent
loop.
