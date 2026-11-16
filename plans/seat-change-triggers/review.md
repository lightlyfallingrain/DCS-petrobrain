### Review Summary

Branch `feature/seat-change-triggers`, tip `e2ee3f98` (fast-forwarded cleanly onto this worktree's
`main` tip `a55f7e97`; the branch tip was also checked out in another worktree at
`/home/sg/Code/DCS-petrobrain-seat-triggers`, but `git merge --ff-only` only moves a ref and does
not need to check anything out, so no snapshot fallback was needed).

**No plan doc exists for this feature** — per the dispatch instructions, the commit message and
diff are the spec: *"Add effector sequence triggers for when Player changes to pilot seat /
copilot seat."* I read the commit message by hand as the decisions record (no `U<n>` ids to
ledger, so `accepted-items-ledger.sh` does not apply here).

One commit, seven files, two new `EffectorTrigger` members (`SEAT_PILOT`/`SEAT_COPILOT`), one new
`ParkedFlightState` field (`player_seat`), one new pure function (`seat_change`), the `body.py`
wiring, docs, and tests.

**What I checked, and how (not just by reading the diff):**

- Regenerated `config/sequences/triggers.md` from the generator (`tools/render_triggers.py`) and
  diffed clean against the committed file — the rendered output matches `TRIGGER_INFO`'s
  descriptions verbatim, not just the `#:` source comment (the project's own standing trap for
  this kind of generated file).
- Read `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`'s `ai_pilot_update_seat`/
  `ai_pilot_seat_from_camera` to verify the two assumptions `ai_pilot_wheel.py`'s new code leans
  on against the actual Lua, not just the commit message's account of it: (1) `ai_pilot_seat_from_
  camera` only ever returns `"pilot"`/`"operator"`/`nil`, and a `nil` reading **keeps the previous
  value** rather than overwriting it (`if seat ~= nil then ai_pilot_player_seat = seat end`) — so
  the body-layer comment "An older `Export.lua` sends no `apw_seat`; keep what we had" and the
  "kept when this frame gives no reading" Lua comment describe the same held-value behaviour, and
  a transient off-axis camera position during an actual seat move cannot flicker the value to
  "unknown" mid-transition; (2) `ai_pilot_player_seat = nil` only happens on `LuaExportStop`
  (line 804) — a genuine mission end/restart, matching the suppression story in the commit
  message and `body-layer/CLAUDE.md`.
- Ran `mypy --strict`, `ruff format --check`, `ruff check` from inside `body-layer/` (not from the
  repo root — the CWD-only config-discovery trap this project's own `CLAUDE.md` warns about).
  All clean on the touched files; the one `ruff format` finding in the whole tree
  (`research/2026-10-05-security-audit.md`) predates this commit and is untouched by it.
- Ran the full collect-only smoke (3330 tests collect) plus the targeted test files
  (`test_ai_pilot_wheel.py`, `test_body.py`, `test_render_triggers.py`, `test_effector_sequences.py`,
  `test_effector_engine.py`) — all pass (237 + 57 in the two runs).
- **Mutated, not just read, both new tests that assert an absence:**
  - Removed the `not mission_start_resolving` suppression clause in `body.py` →
    `test_a_seat_read_across_a_mission_restart_fires_nothing` failed with a spurious
    `weapon_safety` write, confirming the suppression test is load-bearing, not decorative.
  - Collapsed `_as_seat`'s `"pilot"`/`"operator"`/`None` branches to always return `"operator"` on
    anything that isn't `"pilot"` → `test_an_unknown_seat_value_reads_none` failed, confirming the
    unknown-value guard is tested, not just asserted.
  Both files restored afterward; `git status --porcelain` is clean.
- Traced every path that reads `previous_seat` by hand: it is captured immediately before
  `advance_parked_flight_state` and read immediately after, inside the same `if runner.
  last_ownship_state is not None:` block, with no branch between capture and read that could skip
  the read while leaving `previous_seat` unassigned. The `AircraftLayerError` path (caught, logged,
  `parked_flight_state` left unchanged) and the "feed sample is `None`" path (handled inside
  `advance_parked_flight_state` itself, state unchanged) both leave `previous_seat == current`,
  so `seat_change` returns `None` either way — no spurious fire on a failed or absent read. A
  fresh process start against an already-running mission also cannot fire: `previous_seat` is
  `ParkedFlightState()`'s default `None`, and `seat_change(None, <anything>)` is `None` by
  construction.
- Checked whether this needed an entry in `plans/flight-control/plan.md`'s "Co-moving Fields"
  table (the BL-16 takeover/align state machine's own write-site ledger, twice found short an
  entry by this role before — see memory below). `player_seat` has exactly one writer
  (`advance_parked_flight_state`, mirroring the feed) and is read only as a trigger-firing input,
  with no internal co-write and no participation in the align/recovery/mode-cycle machinery that
  table exists to keep consistent — the same shape as several existing `ParkedFlightState` fields
  (`ai_mode`, `held_heading`, `raw_arg_852`, …) that are *not* in that table either. I don't think
  this needed a table entry, but flagging the reasoning rather than asserting it silently, per the
  project's own "keep internal unless it changes the decision" default.
- Checked the generic `effector_engine.advance`/`fire_trigger` machinery handles a trigger with no
  shipped sequence file gracefully (the commit says "no sequence files ship for them — the user
  writes those"): confirmed `advance` logs at `debug` and drops the run as a no-op when
  `_sequence_for` returns `None`, the same path every other not-yet-authored trigger already takes.

### Required Fixes

None.

### Optional Refinements

- **The `_as_seat`/held-value correctness depends on an assumption about `Export.lua` that
  body-layer cannot see or test directly** (that a transient off-axis camera reading never
  surfaces as a momentary "unknown" between two real seats, only as a held previous value). I
  verified this by reading the Lua source rather than taking the commit message's word for it, and
  it holds today — but if that Lua function is ever revised (e.g., the gunner/no-seat branch is
  widened), the `None`-breaks-the-chain behaviour in `seat_change` would silently swallow a real
  change rather than fire it. Not a defect in this commit; worth a one-line comment pointer from
  `seat_change`'s docstring to `ai_pilot_seat_from_camera`'s held-value behaviour, so a future
  reader of either side knows the two are coupled. Optional — the existing comment in
  `advance_parked_flight_state` ("keep what we had") already gestures at this from the Python side.
- No sequence files ship for `seat-pilot`/`seat-copilot`, so the trigger is currently a no-op in a
  live sortie beyond logging — expected and stated in the commit message, not a gap, but worth
  naming in the test card/acceptance note so the user doesn't expect audible/switch behaviour from
  this branch alone until they author the `.md` sequence files.

### Verdict
APPROVED

### Review Confidence
Full read. Every changed file read in full (not just the diff hunks shown by `git show`), the
upstream Lua source it depends on read directly rather than taken on the commit message's account,
the generated doc regenerated and diffed rather than eyeballed, and both new absence-asserting
tests verified by mutation rather than by inspection alone.
