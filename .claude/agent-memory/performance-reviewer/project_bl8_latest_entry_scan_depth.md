---
name: project_bl8_latest_entry_scan_depth
description: BL-8 mission_memory.store.MissionMemory.latest_entry is a per-call reverse scan, not O(1); called once per nameable/air-defence contact every poll to check RESIGHT_MIN_INTERVAL_S, so its cost grows with total entries written by *other* contacts since a "stale" contact's last write. Acceptable at the plan's ~3600-entry/2hr worst case; re-check if RESIGHT_MIN_INTERVAL_S is tuned toward its 5s floor (~43k entries) or sortie length grows well past 2hr.
metadata:
  type: project
---

`MissionMemory.latest_entry` (`body-layer/src/mission_memory/store.py:98-108`) resolves a
contact's newest entry via an O(1) `_latest_live` seq lookup, then a `reversed(self._entries)`
walk to find the `Entry` object with that seq. The store's own docstring already names this as
**not O(1)** and already names the fix (a `seq -> Entry` index) and the condition for needing it.

Why it matters on the hot path: `admission.step` calls `memory.latest_entry(contact.id)` once per
nameable/air-defence contact, every poll, purely to check the `RESIGHT_MIN_INTERVAL_S` gate —
before deciding whether to write anything. A contact that stops changing early and is never
rewritten again gets an increasingly deep reverse scan every poll, for as long as it stays
tracked, as a function of how many *other* contacts' entries get appended after it.

Reviewed 2026-10-17 (`plans/bl8-mission-memory/performance-review.md`) at tip `258ac6c2`:
verdict was MONITOR, not NOW — at the plan's own stated worst case (~30 contacts, ~3600 entries
over a 2-hour sortie), the absolute cost is still small. The gate structure
(`RESIGHT_MIN_INTERVAL_S` checked before any material-change test, per-contact, independent of
jitter frequency) *does* bound entry volume as a linear function of the tuning constant, confirmed
by reading rather than assumed — but `RESIGHT_MIN_INTERVAL_S`'s declared tuning range is [5, 600]s
against a default of 60s, and at the 5s floor the same arithmetic gives ~43,200 entries in a
2-hour sortie, an order of magnitude above the plan's own estimate. That is the condition under
which this should be re-measured rather than monitored: if Sortie A's calibration pushes this
constant down materially, or sortie duration grows well past two hours, re-check actual scan depth
before assuming the "acceptable at current volumes" call still holds.

See also [[project_mission_interpreter_offline_performance]] for this role's other open-question
style finding from the same week, and the general pattern: a store docstring that already names
its own known complexity limit and the condition for revisiting it is doing this role's job in
advance — confirm the condition hasn't been crossed rather than re-deriving the finding from
scratch.
