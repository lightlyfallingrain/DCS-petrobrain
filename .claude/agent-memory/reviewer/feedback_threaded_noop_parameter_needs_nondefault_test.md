---
name: feedback_threaded_noop_parameter_needs_nondefault_test
description: when a stage mechanically threads a new true-no-op parameter (default unchanged) through a long call chain and also fixes a real correctness bug that only matters at a non-default value, check whether any test actually exercises the non-default value -- existing tests passing proves nothing about the fix
metadata:
  type: feedback
---

BL-B124 Stage 3 threaded `light_factor: tuple[float, float, float] = (1.0, 1.0, 1.0)` through
`tier_ranges()`/`_achieved_tier()`/`check_visibility()`/the whole `optic_policy.py`/`attack_run.py`
call chain, correctly as a true no-op everywhere (every existing test keeps passing unchanged by
construction). Inside that same stage, `check_visibility()`'s gate 3 (`size_curve_threshold_m`) was
also fixed to scale by `light_factor[0]`, closing a real desync bug against `_achieved_tier`'s own
`tier_ranges()` call — the implementer's own "Notable Discoveries" section calls this out as the one
genuine correctness trap in the stage. But `grep -rn light_factor body-layer/tests/` outside the new
`test_light_level.py` (which only tests the pure `light_factor()` function, not its *application*)
turns up exactly one hit: a per-poll field-coverage bucket entry confirming the field exists, not
that it's threaded correctly. No test in `test_visibility.py` ever calls `check_visibility()` or
`tier_ranges()` with a non-default `light_factor`. The fix is real and correctly reasoned, but
"proven" only by code inspection — a later edit could reintroduce the exact desync this stage closed
and the full suite would stay green, because every test that exercises this code path uses the
default.

**Why this matters:** "no existing test needed a behaviour change" (the implementer's own correct
claim, since the default is a no-op) is not the same question as "is the non-default path tested at
all." A stage that is *entirely* mechanical threading plus one real fix needs at least one test that
takes the new parameter off its default — otherwise the mechanical-threading-is-safe argument
(which is true) quietly covers for the one spot where real logic changed.

**How to apply:** when a Stage's own notes name a "correctness trap closed" inside an otherwise
pure default-preserving threading change, grep the test suite for the new parameter's name outside
the module that defines it. If every hit is in that defining module's own tests (or a field-coverage
bucket that only checks the field exists), that trap has no regression test — flag it as a required
fix, even though the stage as shipped behaves identically to before.
