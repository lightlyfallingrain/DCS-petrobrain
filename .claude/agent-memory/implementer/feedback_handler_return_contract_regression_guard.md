---
name: handler-return-contract-regression-guard
description: changing a CrewConsole handler's return-value contract (always-something to sometimes-[]) can silently fail test_dispatched_command_tokens_all_return_something in body-layer -- grep for NO_RETURN_VALUE_COMMAND_TOKENS before assuming the change is test-neutral
metadata:
  type: feedback
---

`body-layer/src/belief/crew_console.py` has a project-wide regression guard,
`test_dispatched_command_tokens_all_return_something` (`test_crew_console.py`), that dispatches
every token in `DISPATCHED_COMMAND_TOKENS` once and asserts: a token in `NO_RETURN_VALUE_COMMAND_
TOKENS` must return exactly `[]`, every other token must return something truthy. This exists
because 20 of 41 recognised voice tokens once went nowhere silently.

**If a plan changes a handler from "always returns a readback" to "returns `[]` on its normal
path" (`[[BL-B119]]`: `_handle_observ_on`/`_handle_observ_off`/`_handle_weapons_armed`/`_handle_
weapons_safe`, whose speech moved to an engine that speaks asynchronously), that token must be
added to `NO_RETURN_VALUE_COMMAND_TOKENS`, and the stale comment next to its entry in `DISPATCHED_
COMMAND_TOKENS` (which likely says "always returns a one-line readback unconditionally, so neither
needs the no-return-value exemption") must be corrected or the regression guard itself goes stale
in the opposite direction.**

**A handler with a conditional non-`[]` path (e.g. `_handle_observ_on`'s "Unable, guidance unit not
ready." refusal when `sight_ready` is False) cannot cleanly join that set unless the regression
test's own setup forces the accepted path** -- the test calls each token exactly once with no
per-token state control, so `console.sight_ready = True` had to be set before the loop so `observ_
on`'s single call lands on the `[]` path, matching the set's binary "always `[]`" semantics.

**How to apply:** before declaring a handler-return-value change test-neutral, `grep -n
"NO_RETURN_VALUE_COMMAND_TOKENS\|DISPATCHED_COMMAND_TOKENS"` in `crew_console.py` and run
`test_dispatched_command_tokens_all_return_something` specifically -- it is not named in most
plans' own test-impact lists (this is exactly the "missing entry" class the role's own process
warns about) but it fails immediately and loudly the moment a handler's contract changes.
