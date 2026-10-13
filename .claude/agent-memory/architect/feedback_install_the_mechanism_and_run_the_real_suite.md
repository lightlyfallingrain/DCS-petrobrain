---
name: install-the-mechanism-and-run-the-real-suite
description: A proposed mechanism can be installed into the real code for a whole test-suite run via a pytest plugin that monkeypatches it — the cheapest possible answer to "which pinned tests does this move", and it found the design's one real edge case.
metadata:
  type: feedback
---

**Before finalising a plan that changes behaviour in a module with a large pinned suite, install
the proposed mechanism via a `-p <plugin>` pytest plugin and run the whole suite against it.**
Nothing in `src/` is touched; the plugin monkeypatches at `pytest_configure`, and an env var
selects the calibration or disables it for a control run.

**Why:** on `BL-B58` option 2 (2026-10-13) this turned "which invariants might this break?" from
an argument into a one-line answer — control **1697 passed / 4 xfailed**, with the bound **1696
passed / 1 failed** at two different calibrations. The single failure was the *design finding of
the whole pass*: the bound was `plausible_speed × elapsed`, and the failing test's fold happens
entirely at `t_sim=0.0`, so elapsed is 0, so the bound is 0, so **a same-tick ambiguous fold could
never move a position at all** — a real consequence that forbids same-tick triangulation
refinement and belonged in the plan as a decision for the user. No amount of reading would have
surfaced it; a probe on one incident geometry did not either, because that geometry has a 20 s
gap. It also let the plan assert *measured* rather than *argued* safety for the two tests that
must not move (Stage 0b's pinned eager-cap chaining test and `BL-B50`'s 2C fixture).

**How to apply:** write the plugin into the plan's own `scratchpad/`, run the control first (the
control is what makes the result evidence rather than a number), and quote both lines in the plan.
Keep the probe clamping wherever is convenient — but **say in the plan that the probe's seam is
not the merged seam** if it violates an invariant the real code must keep. Here the probes
assigned `contact.position` directly, which `Contact.position`'s own docstring forbids
(`record`/`from_percept` are its only writers), so the plan picked a different seam than the
probes used and said why.

Related: [[project_body_layer_test_fixture_position_axes]] on this fixture's own traps.
