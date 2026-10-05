---
name: spu8-intercom-cross-machine-handoff-approved
description: feature/spu8-intercom (audio-adapter Slice 2), built on another machine with zero prior gate, reviewed APPROVED clean after one real pre-existing defect was fixed by the main loop.
metadata:
  type: project
---

`feature/spu8-intercom` (tip `d3444ff`) was architected and implemented entirely on another
machine/session, handed over with **no reviewer, no DoD, no check run at all** until this pass —
the implementer never created a venv, so pytest had never executed. The main loop ran the mechanical
pass itself first and fixed one real defect before dispatching review: a second module-level
`_ownship(alt_agl_m)` helper in `body-layer/tests/test_crew_console.py` shadowed an existing
`_ownship(x, z)` 1200 lines above, breaking 80 pre-existing tests with "unexpected keyword argument
'x'". Renamed to `_ownship_at_agl`.

**Why this is worth remembering**: a branch arriving with zero prior gate is not automatically
suspect — code quality here was genuinely high (doc comments matched the code everywhere checked,
decisions were implemented exactly where the plan said), but it is exactly the scenario where
"has this actually been run" has to be verified rather than assumed, because nobody upstream could
have caught a shadowing bug like this (it's invisible at the definition site, only a `pytest -q`
surfaces it). Re-running the full suite myself from a clean snapshot (not trusting the prior
session's or the fixer's reported numbers) is the right default whenever a branch's provenance says
"never gated," not just when something smells wrong.

Also confirms [[feedback_regression_test_empirical_check]]'s pattern held across four separate
mechanisms in one review (gate check, volume scaling, on-ground silent branch, ptt gate
conjunction) — disable-and-rerun is cheap per mechanism and caught nothing wrong here, which is
itself useful signal (not every disable-test check finds a defect; APPROVED-clean is a valid
outcome of doing it).

See `plans/spu8-intercom/review.md` for the full verdict (APPROVED, no required fixes, three minor
optional notes).
