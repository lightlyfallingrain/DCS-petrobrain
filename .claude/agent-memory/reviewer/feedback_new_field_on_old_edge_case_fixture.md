---
name: new-field-on-old-edge-case-fixture
description: when a plan adds a new per-call output field to an engine, check whether a pre-existing documented edge-case test (same-poll re-fire, retry, etc.) exercises it too -- its own fixture may happen to leave the new field at an empty/default value by construction, silently not exercising the new interaction
metadata:
  type: feedback
---

Reviewed `[[BL-B119]]` (`feature/effector-says`, `plans/effector-says/plan.md`) -- effector-sequence
rows speak their own `petrovich-says` line when a row completes, via a new `EffectorRunState.
spoken: tuple[str, ...]` field appended to at the engine's two row-completion points (R12 self-check
match, successful write).

**The gap found (not a defect, APPROVED anyway):** `belief/effector_engine.py`'s own module
docstring documents that a same-poll pending re-fire (D1) "may write once for the run that just
finished and once more for the one that restarts" -- and under BL-B119, the restarted run's
self-check-skip completion now *also* speaks. The one existing test for this exact shape,
`test_pending_restart_may_execute_the_same_poll` (pre-existing, untouched by this diff), uses
`_SEQUENCES`' shared fixture rows -- and every one of those rows carries `petrovich_says=""` by
construction (the fixture predates BL-B119). So the test exercises the *write* side of the
documented dual-completion but says nothing about whether the *new* speech field would double-fire
in the same interaction.

**Why this did not block approval**: traced every speaking trigger's own fire path in `body.py` and
confirmed none of the four (`observ-on/off`, `weapons-arm/safe`) can currently double-fire within
one poll -- each is a one-shot `CrewConsole` field consumed exactly once per poll, and all four
sequence files are single-row with no `WaitRow`, so the restart-collapse path that would exercise
this never triggers for a speaking row today. Still flagged as an optional refinement (a one-line
docstring note or a dedicated test) because the project's own "step by step" framing for this
feature means a future sequence gaining more rows or a `WaitRow` is exactly the change that would
make this latent interaction live.

**Pattern for future review**: when a plan adds a new per-call output to a pure engine with
existing edge-case coverage (same-poll re-fire, retry-then-succeed, fire-order), check whether that
edge case's own fixture happens to leave the new field inert by construction (empty string, `None`,
zero) rather than assuming "there's already a test for this shape" covers the new field too. Grep
the fixture the edge-case test actually uses, not just the test's name.
