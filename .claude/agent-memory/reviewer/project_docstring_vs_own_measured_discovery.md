---
name: docstring-vs-own-measured-discovery
description: When an implementer's own "Notable Discoveries" section in implementation.md measures a behaviour, check that no docstring written in the *same* commit still asserts the old, unmeasured claim — especially one justified by citing a sortie-feedback acceptance line.
metadata:
  type: project
---

On `9k113-scan-procedure`'s Stage 1 review (`plans/9k113-scan-procedure/review.md`, Required Fix
1), `implementation.md`'s own "Notable Discoveries" section stated plainly that
`_start_glance_away` already nulls the sight's aim before `_enter_binocular_search` (a function
written fresh in this same stage) ever runs, so the resume aim is always dead-ahead `(0.0, 0.0)`,
never "last position." The new tests assert exactly that. But the docstring the implementer wrote
for `_enter_binocular_search` in the same commit still said *"leaving them exactly as they were is
'the sight stays at its last position' ... for free"* — citing the F4/F5 sortie-feedback
acceptance line as justification for a design that, by the implementer's own measurement two
sections later in the same document, does not deliver that criterion on this code's only call
path. A pre-existing docstring (`_back_to_home`'s) had the identical, older version of the same
false claim, undiscovered until this stage's tests happened to be the first to check the *resumed*
aim rather than the aim *during* the interruption.

**Why:** an implementer who ran a mutation/measurement and wrote it up honestly in
`implementation.md` can still leave the stale, falsified claim standing in the docstring attached
to the code they just wrote, because the two are different artifacts written at different points
in the same pass and nothing forces them to agree. Reading the code's docstring alone (as a
reviewer skimming the diff) reads as correct and well-justified — it cites real acceptance
feedback — and only cross-referencing it against the implementer's own "Discoveries" section (or
driving the test) surfaces the contradiction.

**How to apply:** whenever `implementation.md` has a "Notable Discoveries"/"Deviations" section
measuring something that differs from what the plan or an existing docstring assumed, grep every
docstring the diff touches or newly writes for the same claim, and treat a match as a required
fix — not optional polish — because it is new prose in this commit actively misstating a fact the
same commit's own tests prove. If the falsified claim also lives in a docstring the diff does
*not* touch (pre-existing, newly exposed rather than newly introduced), flag it too, but as a
secondary note / backlog candidate rather than blocking this stage's own commit.
