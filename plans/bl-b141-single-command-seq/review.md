### Review Summary

Reviewed commit `26bfa514` (`fix/bl16-flight-epoch-bound`, `plans/bl-b141-single-command-seq/plan.md`)
against the plan and `CLAUDE.md`. This is a video game add-on (Petrobrain, DCS World Mi-24P); the
flight/AI-pilot/9K113 CBTM channels discussed below are simulated systems.

**Scope.** BL-B141 widens `_next_flight_seq`/`_next_command_seq` so the one body-layer counter
mints the wire `seq`/`goal_seq`/`cbtm_seq` for all three channels (`flight`, `ai_pilot_goal`
"set"/`hvrt_step`, CBTM one-shot), per the plan's U1 (body-side counter only, Lua-side per-channel
dedupe untouched). BL-B117 adds the `ai_pilot_parked_active` + six overlay-text-field reset to
`ai_pilot_wheel.lua`'s `on_stop()`.

**All six seq-minting call sites in `body.py` now draw from `_next_command_seq`** — verified by
grep (`_apply_ai_pilot_wheel_goal`'s "set"/dual-write/`hvrt_step`/CBTM, and `_apply_flight_
requests`'s take/release and goal-set sends); no other site mints independently. Both the mode-2
"set" send and the CBTM one-shot remain gated behind `runner.command_reset_confirmed`, unchanged by
this commit, so the reset-epoch interaction the plan describes still holds.

**The implementer's stated departure (not writing `ai_pilot_goal_last_sent_seq` from the
`hvrt_step` branch) is right, and tested.** The plan's numbered Design step 2 only says "drop the
write-back into `parked_flight_state.goal`"; the Co-moving Fields table is what actually settles
that `ai_pilot_goal_last_sent_seq` is written only by the "set" branch. Writing the wire-space
value into that cursor from `hvrt_step` would feed the "set" gate (which compares against the
*internal* version) a wire-space number on the next poll — exactly the bug class this plan exists
to remove, just moved one field over. `test_hvrt_step_always_sends_with_a_freshly_minted_wire_seq`
asserts `runner.ai_pilot_goal_last_sent_seq == 3` (the pre-call value, untouched) and
`new_goal.goal_seq == 3` (internal version never bumped) — confirms the departure and the
reasoning for it.

**Lua-side dedupe is correctly left alone and still works with non-contiguous values.**
`fd_last_seq`'s `<=` ordering check, `ai_pilot_cbtm.seq`'s `~=` inequality check, and `ai_pilot_
goal`'s unconditional-overwrite "set" channel none depend on their per-channel values being
contiguous or starting near 0 — each only compares the incoming value against its own last-seen
local. `test_cbtm_seq_well_after_a_mid_session_reset_is_never_the_lua_floor` and
`test_the_same_poll_goal_send_and_cbtm_send_share_one_counter` are the right regression tests for
this (AC-B22's own worry, and the no-collision case the plan named).

**BL-B117's Lua change matches the plan's fix exactly** — same field list, same placement in
`on_stop()`. The real-Lua harness test presets non-default probe values and asserts `is_parked()`
plus every field reset to `false`/`nil`.

**Checks run** (both touched subprojects, from inside each subproject directory):
- body-layer: `ruff format --check` (234 files), `ruff check`, `mypy src` (95 files) — all clean.
  `pytest tests/test_body_ai_pilot_wheel.py tests/test_body_flight_control.py tests/test_body.py
  tests/test_body_command_reset.py -q` — 325 passed.
- aircraft-layer: `ruff format --check` (90 files), `ruff check`, `mypy src` (29 files) — all
  clean. `pytest tests/test_ai_pilot_wheel_lua.py -q` — 105 passed.

No format/lint/type issues, no leftover debug code or TODOs in the diff, no scope drift — the
change is confined to the two files the plan named plus their tests and the two entry files; no
`world-model/data/` or secret-bearing files touched.

### Required Fixes

1. **Both entries were marked `#status/done` (`[x]`) before Reviewer or DoD ran — this branch's
   own precedent (`BL-B139.md`, `BL-B140.md`) is "built but unreviewed/unflown stays
   `#status/in-progress`/`#needs-flight`, not `done`."** `docs/TAGS.md` defines `#status/done` as
   "Complete as specified," and the established pattern on `feature/bl16-lift-vector-law` (see
   `BL-16.md`'s own entries, e.g. "Mode 1 batch... DoD PASSED, merged `a9b8a7c1`" or "Sortie-1120
   batch... DoD PASSED, tip `bf66cc80`") is that an item is marked done only once it names a
   Reviewer verdict and a DoD pass (merged sha), with `#needs-flight` added for the live-acceptance
   debt that remains even then. `BL-B141.md`/`BL-B117.md` currently read "Implemented per plan"
   with no Reviewer/DoD reference and no `#needs-flight` tag, on an un-merged commit. Change the
   checkbox to `[~]`/`#status/in-progress` (or hold off marking `[x]` at all) until this review and
   DoD both land, then mark done with the DoD sha and add `#needs-flight` — this is a wire-protocol
   numbering change on a safety-relevant channel (AI-pilot goal/CBTM), and the plan's own "no-op
   for the player" claim is exactly the kind of claim this project requires a live sortie to close,
   not unit tests alone.

### Optional Refinements

- `implementation.md`'s "Files Changed" note for the two ROADMAP entries just says "marked done" —
  once Required Fix 1 is addressed, update that line too so the implementation record and the
  entries stay consistent (optional, since it's a record of what was done at the time, not a
  live document).
- The CBTM send's first positional argument (`final_goal.goal_seq if final_goal is not None else
  0`) is unrelated to this plan and already somewhat confusing next to the newly-renamed
  `_next_command_seq` calls around it — the inline comment at `body.py` ~4266-4269 already flags
  this clearly, so no action needed, just noting it reads cleanly as written (optional, no change
  requested).

### Verdict
APPROVED WITH MINOR FIXES

### Review Confidence
Full read — both touched source files' diffs read in full against the plan, both touched test
files read in full, Co-moving Fields table and Design section cross-checked against the actual
code, all six seq-minting call sites grepped and verified, reset-gate interaction re-checked at
both call sites, both subprojects' format/lint/type/test commands run from inside each
subproject directory.
