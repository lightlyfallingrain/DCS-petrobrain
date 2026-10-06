---
name: every-guard-entry-needs-a-failing-counterfactual
description: Review an `except (A, B, C, D)` tuple by dropping each type in turn and rerunning — an entry no test fails for is unpinned, and `except` resolves its global at runtime so this needs no source edit.
metadata:
  type: feedback
---

When reviewing a guard that catches a **tuple** of exception types, do not stop at
"does anything escape". **Drop each type from the tuple in turn and rerun the suite.**
An entry that nothing fails for is an entry the next tidy-up deletes for free, and the
comment claiming the list is complete is then actively misleading.

**Why:** `BL-11` round 5 (`feature/bl11-tick-cost`, `38d08d2`) widened
`logger._per_run_log_paths.resolve` to one `try:` over every statement, catching
`_RESOLVE_FAILURES = (OSError, OverflowError, RuntimeError, ValueError)` with a comment
enumerating the types per statement. The enumeration was genuinely **complete** — 429
adversarial `(path, when)` combinations through the real function, 0 escapes, every
statement probed individually. Rounds 3 and 4 had each failed by a type *missing* from
the guard, so a completeness check was the obvious review. It passed. The per-type
counterfactual then showed `OverflowError` was held in place by **nothing**: the full
1517-test suite passed with it removed, because the only input that reaches it
(`when` outside `time_t`) is not reachable from `argv` and the author had guarded it on
principle. Three of four types failed a test; the fourth was decoration.

**How to apply:**

- **No source edit is needed, and that matters for a worktree review.** `except <NAME>`
  looks the name up in the module globals **at raise time**, so a pytest plugin of two
  lines (`import logger; logger._RESOLVE_FAILURES = (...)`) passed via `-p` with the
  scratchpad on `PYTHONPATH` narrows the guard for a whole run. Loop it over the
  n-1 subsets. Nothing in `src/` is touched, so there is no restore step to get wrong.
- **Run it on the full suite, not just the obvious test file.** A type may be pinned by a
  test somewhere else; `OverflowError` was not, and only the full run proves that.
- **The companion check is the masking direction**: inject `TypeError`,
  `AttributeError`, `KeyError` and `RecursionError` into the guarded block and confirm
  they escape. `RecursionError` is a **subclass of `RuntimeError`**, so any guard
  catching `RuntimeError` swallows stack exhaustion — worth saying, usually not worth
  fixing. And `pathlib`'s `with_name(None)` raises **`ValueError`**, not `TypeError`, so
  excluding `TypeError` does not exclude every type error.
- A broad guard over a short block of I/O-and-path statements is usually the **right**
  trade over several narrow adjacent handlers, which is what leaves the next statement
  outside all of them. Judge it by what it *masks*, and check whether a deterministic
  defect inside the block would fail an existing happy-path test (here a hardcoded
  `_STAMP` literal pinned the format, so it would).

See [[feedback_regression_test_empirical_check]],
[[feedback_coverage_floor_fixture_check]] and
[[feedback_boundary_only_tested_via_fixture]] — same family: a test or guard that looks
complete until you disable the thing it is supposed to defend.
