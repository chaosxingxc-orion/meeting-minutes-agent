# E-STABLE-ERROR-SUPPLY Pass-0 flight

All four registered meetings completed: 1,429/1,429 successful calls, zero retries,
zero failures, and 15,077.153 audio seconds. The campaign itself ran for 24.92 minutes,
excluding server load time. Each meeting has an independent response JSONL and receipt;
the aggregate identities are frozen in `flight-summary.json`.

The registered runtime manifest contains no reference transcript, entity surface, or
ticker. Every frozen RTTM turn was processed once; only turns above the repository's
120-second transport bound were mechanically split before registration.

Post-hoc flight diagnostic: 127/1,429 replies contained non-ASCII characters and no
ASCII letters. Of those, 125 came from meeting `4430051` (27.78% of that meeting).
This is a concentrated output-language drift signal, not a registered decision metric.
