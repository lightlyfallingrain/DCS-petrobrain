### Performance Review

Scope: `fix/guidance-ready-edge` (tip `dc93b5619915891584f67f5131fe615282e8b178`), diff
`6dfece18..dc93b561` in `body-layer/`. Single hot-path-relevant change, per the dispatch:
`CrewConsole.drain_guidance_unit_ready` now runs on every poll of `logger.py`'s crew text
poll loop (`_run_crew_text_poll_loop`), where before it ran only inside
`if is_sight_ready:`.

### Findings

#### `drain_guidance_unit_ready` called unconditionally every poll
- **Location:** `body-layer/src/logger.py`, `_run_crew_text_poll_loop` (around the
  `crew_console.sight_ready = is_sight_ready` call site); `CrewConsole.drain_guidance_unit_ready`
  in `body-layer/src/belief/crew_console.py`.
- **Risk:** The new call does one dataclass-field comparison (`previously_observed is False
  and ready_observed is True`), optionally a `self._print(...)` (only on the rare rising
  edge), and one `dataclasses.replace(runner.guidance_unit_state, ...)` to store the updated
  `guidance_unit_ready_prev_observed` back — every poll instead of only while the sight is
  ready. This loop's own `poll_interval_s` default is one second
  (`body-layer/src/logger.py:1938`, "the default one-second poll interval"), not a per-frame
  or sub-millisecond budget, and the loop already performs 16 other `replace()` calls per
  poll on this same `GuidanceUnitState`/sibling state objects for other fields tracked the
  same way. One more shallow-copy `replace()` of a ~10-field dataclass at ~1 Hz is not
  measurably different from the existing per-poll cost; there is no allocation inside a
  frame-rate loop and no I/O or blocking call added.
- **Action:** MONITOR
- **Mitigation:** None needed now. If `poll_interval_s` is ever lowered by an order of
  magnitude for this loop specifically, or this per-poll `replace()` pattern grows
  significantly denser (many more such fields tracked the same way), it would be worth
  batching the `GuidanceUnitState` fields updated per poll into a single `replace()` call
  rather than one per tracked field — but that is a pattern-wide observation, not something
  this fix introduces or need address.

No full-dataset iteration, no new per-request/per-poll allocation pattern beyond the
existing `replace()`-per-field convention already in this loop, no redundant queries, and no
blocking work was added. This is a one-line condition removal plus a field rename/retype; the
added work is unconditional execution of an already-cheap O(1) check at a ~1 Hz cadence.

### Verdict
APPROVED
