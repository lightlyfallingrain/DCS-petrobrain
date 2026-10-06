---
name: guard-widening-check-every-statement
description: When a fix widens an except clause, enumerate the exception types of every statement inside the try - including statements a sibling fix added in the same round.
metadata:
  type: feedback
---

When a round's fix **widens an `except` clause** (`OSError` → `(OSError, ValueError)`),
do not review only the statement the finding named. Enumerate what *every* statement in
the guarded region — and every statement the same round added nearby — can raise, then
check each against the clause.

**Why:** `feature/bl11-tick-cost` round 4 fixed two Security findings in one eight-line
closure. Finding 1's fix moved `per_run_log_path` inside the `try:` and widened the guard
to catch `ValueError` from `Path.with_name`. Finding 2's fix added
`path.expanduser()` — *outside* the `try:* — which raises `RuntimeError` on a `~user`
prefix with no resolvable home. So the round that removed one argv-driven unhandled
exception from the startup path added another of the same class, and the docstring it
wrote (*"a path that cannot be resolved to a writable file degrades..."*) asserted the
opposite. Both fixes passed their own counterfactuals; neither counterfactual could see
the interaction.

**How to apply:** for each statement in the resolve/validate chain, look up what the
stdlib call raises — not what the finding said it raises. `pathlib` is the worked
example and worth remembering by name:

- `Path.with_name` → `ValueError` on an empty final component
- `Path.expanduser` → `RuntimeError` on an unresolvable `~user`
- `Path.mkdir` → `OSError`

Three different exception types across three adjacent `pathlib` calls, none of them
`OSError` except the last. Then reproduce through **the real function**, not through the
stdlib call in isolation — `Path("~x/f").expanduser()` raising is a library fact;
`_per_run_log_paths(...)` raising is the defect, and only the second one tells you the
guard did not cover it.

Related: [[feedback_bounded_magnitude_isnt_optional_severity]] (the reachable-but-narrow
input is still a required fix), [[feedback_regression_test_empirical_check]] (disable the
fix, rerun the test).
