---
name: lua-named-mutations-are-cheap-to-reproduce-directly
description: When a plan names a specific mutation Export.lua's own tests must catch, actually make that edit against the real source and run the suite — it is a two-minute round trip and found nothing wrong here, but is the only way to be sure the test is pinned to the right thing rather than a plausible-looking assertion.
metadata:
  type: feedback
---

BL-B80 v3 Stage 6 (9K113 edge-park fix, `plans/9k113-sight-pointing/plan.md`): the plan named two
specific mutations its own tests must catch (reverting `field_target` to the raw setpoint;
feeding the raw goal rate into feed-forward unconditionally). Rather than trusting the
implementer's claim that these were caught, I copied `Export.lua` aside, applied each mutation
directly to the real file, ran `pytest tests/test_sight_servo_lua.py::TestRunSightServoFieldPark`,
confirmed the predicted tests (and only those) went red with the predicted wrong values, then
restored the file from the backup and confirmed `git status --porcelain` was clean.

**Why this is cheap and worth doing as standard practice for Lua fixes specifically**: these tests
extract and run the actual `local function ... end` body out of `Export.lua` via `luajit`/`lua`
(`_extract_lua_function`), so a real edit to the real file is exactly what the test harness
already exercises — no separate repro script, no mock rebuild. The whole round trip (edit, run,
revert, confirm clean) took under a minute per mutation.

**How to apply**: whenever a plan's "Tests" section names a specific mutation a test must catch
(not just "property X holds"), do this directly against the source rather than reading the test
and the fix separately and reasoning that they must correspond. Always `cp` the file aside first,
and always re-run `git status --porcelain` after restoring to confirm the mutation didn't leave a
stray diff. This generalizes the project's standing "verify by mutation" rule
(`.claude/agents/reviewer.md`) to the specific, low-friction case where the plan has already named
the exact edit for you.
