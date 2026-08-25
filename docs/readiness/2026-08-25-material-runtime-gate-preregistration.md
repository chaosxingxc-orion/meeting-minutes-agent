# E-MATERIAL-RUNTIME-GATE preregistration

## Question

On an independently admitted six-meeting cohort, can a deployable
within-meeting semantic top-1/top-2 gap select useful official-material evidence
without consulting a wrong-meeting score at runtime?

## Prerequisite and frozen split

`E-MATERIAL-SEMANTIC-ADMISSION` must pass first. Its first three frozen meetings
form development and its other three form one-shot confirmation. A failed
admission yields `NOT_RUN_PREREQUISITE_FAILED`; no substitute cohort is allowed.

Before any reference read, freeze official source bytes and hashes, material
keys and values, audio/chunks, the Pass0 prompt, and Pass0 outputs. For each
chunk, query only that meeting's key index with Pass0 text, predicted speaker
ID, and bounded prior topic keywords. Dispatch uses only the within-meeting
top-1 minus top-2 cosine gap. Wrong-meeting material is an equal-width
experimental control and never a deployment feature.

## Development and confirmation rule

On development only, choose from the frozen gap grid
`[0.00, 0.01, 0.02, 0.03, 0.04, 0.05]` the lowest threshold attaining at least
70% correct-material attribution precision and 20% coverage, with every
development meeting represented. Freeze that threshold before confirmation.
Confirmation passes only if precision remains at least 70%, coverage at least
20%, at least two of three meetings reach 60% precision, and median
correct-minus-deranged cosine is at least 0.01.

This experiment is zero-model and establishes only structural routing. It does
not establish term correctness, WER benefit, or authority to run Omni arms.
