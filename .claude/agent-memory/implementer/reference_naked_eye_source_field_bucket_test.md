---
name: naked_eye_source_field_bucket_test
description: body-layer/tests/test_naked_eye_source.py has a field-coverage test (test_reset_for_new_mission_field_coverage_is_complete) that enumerates every NakedEyePerceptionSource dataclass field into one of three buckets -- a new field added to that class must be added to the matching bucket or this test fails immediately
metadata:
  type: reference
---

`NakedEyePerceptionSource` (`body-layer/src/perception/naked_eye_source.py`) is a dataclass with
three kinds of field: construction-time config preserved across a mission restart
(`_PRESERVED_FIELDS`), per-poll fields the poll loop overwrites every tick
(`_PER_POLL_OVERWRITTEN_FIELDS`, e.g. `optic`, `scan_plan`, `sight_cone`), and internal
dedup/counter state `reset_for_new_mission()` clears (`_RESET_FIELDS`). A test in
`test_naked_eye_source.py` enumerates `dataclasses.fields(NakedEyePerceptionSource)` at test time
and asserts every field name is in exactly one of those three frozensets — a field left out of all
three fails the test immediately instead of silently leaking (or not leaking) across a mission
restart with nobody noticing.

**How to apply:** when adding a new field to `NakedEyePerceptionSource`, decide which of the three
buckets it belongs to (per-poll-assigned fields like a new `light_factor` go in
`_PER_POLL_OVERWRITTEN_FIELDS`) and add it there — this is the test's own designed extension point,
not a test being "modified" in the sense the project's rules caution against; the test's whole
purpose is to force this classification on every new field.
