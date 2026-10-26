---
name: required-field-mirroring-existing-one-ripples-fixtures
description: Adding a new REQUIRED field to a schema that already has one (mirroring stalled's posture) breaks every existing test fixture/literal built from the old shape, even when the plan's own file-list note names only one small test change.
metadata:
  type: feedback
---

BL-B80 v3 Stage 6 (`plans/9k113-sight-pointing/plan.md`): the plan's "Affected Modules/Files" note
for `test_sight_servo_api.py` said only "the one test using `'open'` as an example wire value is
relabelled `'homing'`". Adding `mark_clipped: bool` as a *required* field (same parse-or-reject
posture `stalled` already has, per the plan's own design) actually touched five tests in that
file: the module-level `_LINE` wire fixture every other test reuses, two dict-literal
`to_api_dict`/endpoint-response assertions, and the `SightServoState(...)` constructor call used
to build a sample by hand -- every one of them built from the pre-change field set, and every one
raised `SightServoParseError` or failed an equality assert without the new field(s) added.

**General shape:** when a plan says "add field X, same required-bool posture as field Y", treat
that as an implicit instruction that every existing fixture/literal shaped like "the old record"
needs updating too -- not just whatever the plan's file-list note happened to call out by name.
`grep` the test file for the module-level fixture constant and for every literal construction of
the dataclass before writing the one change the plan named; the untouched ones are where this
bites, because they look unrelated to the one line the plan mentioned.

This is the "test-impact list is a hypothesis, not a checklist" lesson generalized to schema
changes specifically: a plan's own prediction of blast radius is a starting point, especially when
it is phrased as "mirrors an existing field's posture" -- that phrase is a promise about ripple
effects, not just about the new field's own validation rule.
