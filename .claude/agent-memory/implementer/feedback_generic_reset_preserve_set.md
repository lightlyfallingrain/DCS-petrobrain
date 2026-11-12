---
name: generic-reset-preserve-set
description: body-layer's generic per-field reset tests (test_mission_start_reset.py) have a hand-maintained preserve-set per dataclass -- a new field passed through reset_for_new_mission's __init__ call must be added to that set or the generic test's sentinel-poisoning breaks loudly (or, worse, silently matches a None default).
type: feedback
---

`body-layer/tests/test_mission_start_reset.py` enumerates each reset-bearing class's actual
dataclass fields at test time, poisons every field *not* named in a hand-written
`_<Class>_PRESERVE` set with a sentinel `object()`, calls `reset_for_new_mission()`, then asserts
every poisoned field reset to its fresh-constructor default and every preserved field kept the
sentinel by identity.

**Why this matters for any change that edits a `reset_for_new_mission` pass-through list (BL-15's
own pattern, used by `CrewConsole`/`ConsolePerceptionRunner`/etc.):** adding a new field to the
pass-through `self.__init__(..., new_field=self.new_field, ...)` call without also adding it to
the matching `_<Class>_PRESERVE` set in this test file has two different failure shapes depending
on what the reset code *does* with that field:

1. **If the reset method only passes the field through** (no other use of it), the test's generic
   "resets to default" check on the un-poisoned field won't catch anything wrong (a field that was
   never poisoned still equals its own default by coincidence) -- a silent miss, not a loud one.
2. **If the reset method also calls a method on that field** (e.g. `[[BL-B106]]`'s
   `self.speech_worker.interrupt()`, added in the same edit as the pass-through), the generic
   test's sentinel (a bare `object()`, poisoned onto every field *not* in the preserve set) has no
   such method, and the test fails with `AttributeError` -- loud, but only because of the *second*
   change, not the pass-through edit itself.

So: whenever a `reset_for_new_mission` pass-through list gains a field, grep
`test_mission_start_reset.py` for that class's own `_PRESERVE` set and add the field there in the
same commit, even if the change "looks like" it only touches `crew_console.py`/`body.py`. This is
exactly the step-1b "test the plan's test-impact list as a hypothesis" lesson in concrete form:
`plans/async-speech/plan.md`'s own Stage 4 list never named this file, and the gap was found only
by running the full suite, not by reading the diff.

See also [[step-1b-test-impact-hypothesis]] (if that memory exists yet) for the general rule this
is one instance of.
