---
name: test-callouts-dwp-docstring-stale
description: test_callouts.py's _observation() docstring wrongly claims dwp_x/dwp_z drive Contact.last_position -- they don't, percept_of strips derived_world_position.
metadata:
  type: project
---

`body-layer/tests/test_callouts.py::_observation`'s own docstring claims
`dwp_x`/`dwp_z` "drive `Contact.last_position`, i.e. spatial-gate matching,
entirely independently" from `ownship_x`/`ownship_z`. **This is false as of
2026-09-25** (and, from reading `belief/percept.py::percept_of`, was
probably never true): `percept_of` structurally strips `Observation.
derived_world_position` before it crosses into `belief/` code (the
no-omniscience boundary) -- `Contact.last_position` actually comes from the
observation's `bearing_deg`/`range_m` (both fixed defaults, `0.0`/`1000.0`,
unless a test overrides them) projected from `ownship_at_observation`.

Existing tests built around this false premise (e.g. `test_watched_contact_
speaks_a_range_crossing`, which sets `dwp_x=4500.0` and comments "silent
seed at km=4") still pass, but only because their assertions check the
*rendered text*, which is identical between `CONTACT_DETECTED` and
`CONTACT_RANGE_CROSSED` on an unenriched contact (`_contact_report_text`
with no affixes) -- the numeric km values the comments describe are never
actually asserted, so the stale docstring went undetected.

**If you write a new `test_callouts.py` test that needs a contact at a
specific position, use `bearing_deg`/`range_m` (or override them), not
`dwp_x`/`dwp_z`** -- verified empirically by printing `Contact.last_position`
after ingest, not by trusting the docstring. Left uncorrected in this
session (out of scope for `plans/scan-is-not-watch/debug.md`) -- worth
fixing if that test file is touched again for an unrelated reason.
