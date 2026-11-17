---
name: removing-an-actions-own-precondition-check-breaks-tests-that-call-it-directly
description: deleting a CrewConsole action's own "NOT_READY"-shaped guard because a new gate upstream now owns it breaks every unit test that calls the action/dispatches the command directly (bypassing the gate by construction) -- grep the whole test suite for the removed reason string before declaring the change test-neutral, not just the file the plan names
metadata:
  type: feedback
---

On BL-17 Stage 3b, D16 explicitly instructed removing `CrewConsole.increment_ai_heading`'s own
`current is None -> {"ok": False, "reason": "NOT_READY"}` branch: a new category gate
(`rules.gates`) now refuses the command *before* the action ever runs, so the old branch was
genuinely dead code once the gate was wired ahead of it. The plan named one test file
(`test_rules_flight_actions.py`, via the "differential tests before deletion" precedent from an
earlier stage) as needing attention. Running the fast-tests full-suite check after everything else
was green found a **second** test, in a different file
(`test_crew_console_ai_pilot_wheel.py::TestIncrementAiHeading::
test_unable_without_a_known_current_heading`), not named anywhere in the plan, that called
`console.increment_ai_heading(-20)` directly with no held heading and asserted the now-deleted
branch's exact return value.

**Why this is structural, not a one-off miss**: a unit test that calls an action method or
dispatches a command token *directly* (not through the real `handle_command`/gate path) is, by
construction, a test that bypasses whatever upstream precondition a later refactor adds — it was
written before the gate existed, to pin the action's own behaviour in isolation, which is exactly
the kind of test a "the precondition moved upstream" change invalidates without touching the gate
at all. The plan's own test-impact list can name the file it was thinking of and still miss a
sibling test in a different file that does the same direct-call thing for a different reason
(there, pinning the pre-rules handler extraction; here, pinning the action in isolation).

**How to apply**: before removing an action/handler's own `if <precondition> is None/False: return
{"ok": False, "reason": "<REASON>"}`-shaped branch because a gate now owns it, `grep -rn
"<REASON>"` (the exact reason string, e.g. `"NOT_READY"`) across the *whole* test suite, not just
the file(s) the plan names — every hit that constructs the triggering state and calls the
method/token directly (no gate in the call path) is a test that will need replacing, not just the
one the plan already flagged. Replace with either (a) a test through the real dispatch path
proving the gate now produces the user-facing refusal, or (b) if the method is genuinely
unreachable with that precondition false, `pytest.raises(AssertionError)` pinning the new
contract explicitly — never leave the old assertion in place hoping it still holds.
