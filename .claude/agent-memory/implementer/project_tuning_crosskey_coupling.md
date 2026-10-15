---
name: tuning-crosskey-coupling
description: body-layer's import-time asserts between gaze/decay constants are a hazard when those same constants become independently tunable (X-T26)
metadata:
  type: project
---

`body-layer/src/belief/decay.py` asserts `OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S` at **module
import time** (`OBSERVED_WINDOW_S` = `perception.gaze.SCAN_CYCLE_PERIOD_S` =
`len(SCAN_PLAN) * FOCUS_DWELL_S`). X-T26 Stages 1-2 (`plans/configurable-constants/plan.md`) made
`POSITION_HALF_LIFE_S`, `FOCUS_DWELL_S`, and `SCAN_PLAN` all independently tunable via
`tuning.real`/`tuning.sequence`. Each accessor only validates its own key against its own declared
`lo`/`hi` bounds — nothing validates the *combination*. Chosen bounds
(`POSITION_HALF_LIFE_S` lo=20.0, `FOCUS_DWELL_S` hi=5.0) keep any *single*-key override safe
relative to the others' defaults, but tuning more than one of the three at once can still trip the
assertion and crash the process at import — a disguised "refuse to start" in a feature whose whole
point (Decision 4 REVISED) was never to do that.

**Why:** this is a project-specific hazard of the tuning mechanism, not a generic one — it only
shows up where a module-level `assert` already encoded a cross-constant invariant before any of
the constants it mentions became independently overridable. `belief/decay.py` has exactly two such
asserts; only the second one (`OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S`) is at risk, because the
other's lower bound is structurally guaranteed by `FOCUS_DWELL_S > 0`.

**How to apply:** before converting a constant to `tuning.*`, grep its defining module for
`assert` statements that reference it (or a constant derived from it) at module scope — not just
inside functions. If found, either (a) choose bounds generous enough that no single-key tuning can
trip the assert (the X-T26 approach — accepted as a documented residual, not fully closed), or
(b) escalate to Architect if full closure matters (a cross-key validator is a real design decision,
out of scope for a "mechanism only" stage). Documented for pilots in `body-layer/CLAUDE.md`'s
"Tuning" section rather than in `tuning.py` itself, since the coupling is specific to these three
constants, not a property of the loader.

See also [[tuning-generator-comment-extraction]] for the sibling lesson from the same feature
about generating descriptions from hand-wrapped `#:` prose.
