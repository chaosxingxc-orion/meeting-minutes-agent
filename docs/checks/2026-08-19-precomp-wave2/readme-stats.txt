## Per-invocation batch table

| inv | meetings | n | encode calls | server start s | runner wall s | wrapper wall s | state | remaining after |
|---|---|---|---|---|---|---|---|---|
| 1 | ES2002a ES2002c ES2002d ES2003a ES2003d ES2005a ES2005c ES2005d ES2006a ES2006b ES2007c ES2007d | 12 | 424 | 10 | 2013 | 2044 | SLICE-DONE | 65 |
| 2 | ES2008a ES2008b ES2008c ES2009a ES2009b ES2009d ES2010a ES2010b ES2010c ES2012b ES2012c ES2012d ES2013a ES2013c ES2013d ES2014a ES2014b ES2014c ES2014d ES2015a ES2015d | 21 | 789 | 16 | 2758 | 2778 | SLICE-DONE | 43 |
| 3 | ES2016a ES2016c ES2016d IS1000a IS1000b IS1000d IS1001a IS1001b IS1001d IS1002b IS1002c IS1002d IS1003b IS1003c IS1004a IS1004d IS1005c IS1006c IS1007a | 19 | 698 | 10 | 2722 | 2781 | SLICE-DONE | 24 |
| 4 | IS1007b IS1007c IS1007d TS3005a TS3005d TS3006b TS3006c TS3006d TS3007a TS3007b TS3007c TS3007d TS3008b TS3008c TS3008d | 15 | 745 | 15 | 2758 | 2826 | SLICE-DONE | 9 |
| 5 | TS3009b TS3009c TS3009d TS3010a TS3010d TS3011a TS3011c TS3012b TS3012d | 9 | 407 | 47 | 2357 | 2421 | WAVE-COMPLETE | 0 |
| 6 | ES2005d | 1 | 36 | 22 | 123 | None | NO-FLY-DONE | ? |

## Wave totals vs registered ceilings

| axis | used | ceiling | headroom |
|---|---|---|---|
| encode calls | 3099 | 4500 | 68.9% used |
| encode GPU-h | 1.322 | 8.0 | 16.5% used |
| diar GPU-h | 0.192 | 2.0 | 9.6% used |
| CPU cutting wall-h | 0.425 | none (wave-2 registers no ceiling on this axis) | n/a |

wall clock: diar 2966.0 s, encode 6978.2 s, cutting 1528.7 s
receipts: 76 (ok 76)

## Descriptive distributions (prereg SS5)

- turns: tool 46727, oracle 39291
- slices: tool 1543, oracle 1556 (sum of per-meeting deltas -13; per-meeting delta min -3.0 / med 0.0 / max 2.0)
- boundary displacement, per-meeting medians: min 0.6 / med 22.1 / max 44.3
- boundary displacement, per-meeting maxima:  min 12.4 / med 46.5 / max 194.0
- feature cache added by wave-2: 37856 entries / 31141846528 bytes (29.00 GiB)
