# E-MATERIAL-LHCP-SUPPLY verdict

## Decision

`LHCP_ZERO_MODEL_MATERIAL_SUPPLY_INSUFFICIENT`

Acquisition succeeded for all 77 frozen CERN attachments: 1,648,976,797 bytes,
77 unique Indico MD5 values, and 77 unique local SHA-256 values. No audio or
reference object was downloaded or read.

After the registered Unicode transport amendment, the frozen parser completed all
72 talks. Seventy talks passed the per-talk requirements of at least one readable
document, 200 visible characters, and eight unique deterministic candidates. The
25-talk development cohort passed 25/25. The future confirmation cohort passed
45/47: `test_2020` passed 13/15 and `test_2022` passed 32/32.

The two failures are `856696c36.wav` and `856696c52.wav`. Their sole PDFs opened as
28 and 43 pages, respectively, but `pypdf` raised `LimitReachedError` during text
extraction on pages 2 and 18 because an operator stream exceeded its frozen 64-byte
guard. Both talks therefore produced zero readable characters and zero candidates.
No OCR, fallback parser, attachment substitution, or meeting replacement was used.

Among the 70 passing talks, candidate supply ranged from 16 to 1,205 unique items,
with median 142; visible text ranged from 1,814 to 376,649 characters, with median
14,247. The complete extraction contained 2,255 pages/slides, 1,994,794 visible
characters, and a per-meeting sum of 13,764 unique candidates. Seventy-five of 77
attachments parsed; all three PPTX files parsed.

The machine verdict and external artifact hashes pass offline readback as
`TRACE_COMPLETE`. Under the preregistered 72/72 gate, model contact remains blocked.
A reduced 25-development/45-confirmation eligibility cohort or an all-PDF alternate
parser requires a new prospective registration and a clear evidence-tier decision.

