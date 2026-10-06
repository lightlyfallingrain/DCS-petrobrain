---
name: benchmarks-must-be-able-to-fail
description: Every measurement harness carries a probe that proves it can fail, before any number from it is reported.
metadata:
  type: feedback
---

Build a **"can this harness fail" probe** into every measurement script and assert it before
reporting a single number.

**Why:** on `feature/bl11-tick-cost` (2026-10-06) three separate tests passed for the wrong
reason in one night — one shared code with what it pinned, one perturbed a constant the test
imports, one asserted a guard whose effect had already happened. A benchmark that cannot fail is
the same defect wearing different clothes, and it is worse than a bad test because its output is
a number someone will quote. The specific trap this role has already hit: patching a function at
its *defining* module when the caller did `from x import y` measures nothing and reports zeros,
which reads exactly like "this is cheap".

**How to apply:** the probe shape depends on what is being measured.
- **Equivalence benchmark:** mutate a shipped constant and assert the equality check *breaks*,
  then restore it. (`bench_salience.py` — tripling `GROUP_COHESION_GAP_UNIT_WIDTHS` must make
  shipped ≠ reference.)
- **Policy benchmark:** compute the rejected alternative and assert the measurement distinguishes
  it. (`bench_tick.py` — the re-based deadline must be measurably far from the queueing one.)
- **Instrumented harness:** assert each counter is non-zero before reading it, and assert the
  system under test actually did the work (contacts founded, cache consulted).

Related: [[feedback_stale_worktree_check_first]].
