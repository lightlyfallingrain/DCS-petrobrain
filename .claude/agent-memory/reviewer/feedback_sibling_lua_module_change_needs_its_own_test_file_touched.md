---
name: sibling-lua-module-change-needs-its-own-test-file-touched
description: flight_control.lua and flight_desired.lua cross-call each other via mocked seams in each other's own test harness -- a change to one that is only verified through the other's test file (or not at all) is a real gap, not a stylistic one; check the changed file's own test file was touched, not just that "a" test file was.
metadata:
  type: feedback
---

BL-16 LV-3 (`plans/flight-lift-vector/plan.md`) touched three production Lua files:
`flight_control.lua`, `flight_desired.lua`, `flight_profile.lua`. The implementer's own
`implementation-lv3.md` file list named test changes only in `test_flight_control_law.py`,
`test_flight_control_estimator.py` and `test_flight_control_lua.py` — never
`test_flight_desired_lua.py`, even though `flight_desired.lua`'s `reseed_from_measured` and
`write_internal` both gained new LV-3 behaviour (a hover take-rule mirror via a new
`flight_control.get_lambda` getter, a `V_m` speed reseed via a new `get_take_speed_kmh` getter, and
a `bank_hold_deg` clear in the heading branch).

Grepping `test_flight_desired_lua.py` for the two new getter names found zero occurrences — its own
`flight_control` mock stub still has no `get_lambda`/`get_take_speed_kmh` entries, so `safe_call`
on the missing field always returns `nil` and both new conditional branches in
`reseed_from_measured` are permanently dead as far as that test file is concerned. Separately,
`test_flight_control_lua.py` carries its *own*, hand-written re-implementation of
`flight_desired.write_internal` as a mock (used when testing `flight_control.lua` in isolation) —
that mock was not updated to clear `bank_hold_deg` either, so even an integration-style check
through *that* harness could not catch a regression in the real module's new behaviour. The plan's
own Tests section explicitly promised a check here ("`test_flight_control_lua.py` checks the
write-back and `desired.bank_hold_deg == nil`") and it was not built in either file.

**How to apply:** `flight_control.lua` and `flight_desired.lua` are a genuine pair in this
subproject — each one's test harness mocks the *other* module as a stand-in table (`flight_control
= { get_phi_bar = ..., get_lambda = ... }` inside `test_flight_desired_lua.py`; `flight_desired =
{ write_internal = ... }` inside `test_flight_control_lua.py`). A new getter or write-back added to
one side has **two** places that can silently go untested: the new field/branch in the *producing*
module's own test file (easy to miss because "a function was added and tested" reads as done), and
the *consuming* module's mock of it (easy to miss because that file was not touched by the diff at
all, so nothing prompts a look). When a plan's Tests section names a cross-module check like this
one by name, grep both test files for the new getter/field name specifically — not just confirm
"some test file changed" — before accepting the implementer's own file list as proof of coverage.
This is the same standing check as
`[[feedback_verify_effector_registry_against_raw_dump]]`/"grep for the new mechanism's own call
site, not the file list" applied to a two-sided Lua mock pair rather than a registry/raw-dump pair.
