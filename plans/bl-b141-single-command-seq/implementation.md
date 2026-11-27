### Implementation Summary

Video game add-on context: Petrobrain is a hobby add-on for the DCS World flight-simulation game;
the Mi-24P, its AI-pilot wheel and 9K113 CBTM are simulated systems, nothing here controls real
hardware.

Built both items from `plans/bl-b141-single-command-seq/plan.md` exactly as specified (U1 settled:
body-side counter only; Lua-side dedupe untouched per channel).

**BL-B141.** `ConsolePerceptionRunner.command_seq` (previously the `flight` channel's own counter,
minted via `_next_flight_seq`) is now the one source every seq-carrying command channel draws
from. Renamed `_next_flight_seq` → `_next_command_seq` and widened its three new call sites:

- `_apply_ai_pilot_wheel_goal`'s "set" branch: the gate still compares the *internal*
  `AiPilotWheelGoal.goal_seq` against `runner.ai_pilot_goal_last_sent_seq` (unchanged), but the
  wire value sent is now `_next_command_seq(runner)`, not `final_goal.goal_seq` itself.
- `hvrt_step`: dropped `bumped_seq = final_goal.goal_seq + 1` and its write-back
  (`replace(final_goal, goal_seq=bumped_seq)`) into `parked_flight_state.goal` — there is nothing
  left to keep in sync once the wire value is decoupled from the internal version. Mints
  `_next_command_seq(runner)` directly. **Also stopped writing `runner.ai_pilot_goal_last_sent_
  seq`** after this send — the plan's own Co-moving Fields table names only the "set" branch as
  that cursor's writer; writing a wire-space number into it here would have corrupted the "set"
  gate's own comparison against the internal version on a later poll (not stated explicitly in
  the plan's numbered steps, but required by its own Co-moving table and confirmed by a new test).
- CBTM one-shot: dropped `bumped_cbtm_seq = (runner.ai_pilot_cbtm_last_sent_seq or 0) + 1`. Mints
  `_next_command_seq(runner)` directly for the wire `cbtm_seq` field. The call's own `goal_seq`
  argument (first positional) is unrelated to this mint and is unchanged, per plan.

Removed `ConsolePerceptionRunner.ai_pilot_cbtm_last_sent_seq` entirely (field, its reset-to-`None`
line in the unparked branch, its docstring paragraph) — no other reader existed (grepped).
Re-worded `ai_pilot_goal_last_sent_seq`'s own docstring: it now holds "the internal version last
sent-for," not the wire value.

`AC-B22` was already marked closed-by-reset at the plan's own tip (`66d5d251`) — no entry change
needed from this implementation pass.

**BL-B117.** `on_stop()` in `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua` now also
clears `ai_pilot_parked_active` (→ `false`) and the six overlay text fields (→ `nil`), next to the
existing `AC-B13` reset it already performed. Pruned the function's own header comment, which used
to state these fields were "deliberately" left untouched — no longer true, replaced with a pointer
to the new block.

### Files Changed

- `body-layer/src/body.py` — rename, docstring updates, three mint-site changes, field removal
  (see above).
- `body-layer/tests/test_body_ai_pilot_wheel.py` — updated every wire-value assertion that had
  hard-coded the old internal/wire-coupled value or the removed field; added three new tests (see
  below).
- `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua` — `on_stop()` BL-B117 fix, header
  comment pruned.
- `aircraft-layer/tests/test_ai_pilot_wheel_lua.py` — widened `_run_on_stop`'s harness with seven
  new optional preset/assert fields (default to `on_stop`'s own reset values, so every pre-existing
  caller is unaffected); added one new test.
- `body-layer/ROADMAP/BL-B141.md`, `body-layer/ROADMAP/BL-B117.md` — marked done.

### Tests Added

- `test_hvrt_step_always_sends_with_a_freshly_minted_wire_seq` (replaces the old `..._bumped_goal_
  seq` test) — wire value comes from the shared counter (`1` on a fresh runner), the internal
  `goal.goal_seq` is left at its pre-call value, and `ai_pilot_goal_last_sent_seq` is left
  untouched by this one-shot send.
- `test_align_starts_a_plain_alignment_and_sends_a_minted_cbtm_seq` /
  `..._sends_a_minted_cbtm_seq` (align_for_launch) / the break-left/break-away `sent[9]`
  assertions — updated from the old hard-coded `1` to the actual post-refactor value (`2`, since
  the same-poll ordinary goal send now draws `1` first from the shared counter).
- `test_a_second_cbtm_transition_draws_the_next_shared_counter_value` (replaces the old
  `..._bumps_its_own_seq_space_again`, which asserted the now-removed `ai_pilot_cbtm_last_sent_
  seq` field and a per-channel space that no longer exists) — a CBTM send after
  `runner.command_seq` has already advanced draws the next number from that same counter.
- `test_the_same_poll_goal_send_and_cbtm_send_share_one_counter` — the plan's own named test: an
  ordinary goal "set" send and a CBTM send in the same poll draw two distinct, counter-adjacent
  values, never colliding.
- `test_cbtm_seq_well_after_a_mid_session_reset_is_never_the_lua_floor` — the plan's own named
  regression test: `runner.command_seq` already well advanced (simulating "reset happened well
  into a session") produces a CBTM wire value that can never coincide with Lua's freshly-zeroed
  `ai_pilot_cbtm.seq` (`0`) — the exact shape `AC-B22` worried about.
- `test_a_turn_heading_transition_is_applied_and_sent` — updated: asserted the literal mint value
  (`1`) instead of `goal.goal_seq`, which only coincidentally equalled it before (flagged in the
  plan's own Risks section as the "passes by coincidence" trap).
- `aircraft-layer/tests/test_ai_pilot_wheel_lua.py::TestOnStop::test_the_parked_flag_and_overlay_
  text_are_reset` — presets `ai_pilot_parked_active=true` and every overlay text field to a
  non-nil probe value, runs the real extracted `on_stop`, asserts `is_parked()` and every field are
  `false`/`nil`.

### Checks

**body-layer/**
- `ruff format --check`: pass (234 files already formatted)
- `ruff check`: pass
- `mypy --strict` (`cd body-layer && .venv/bin/mypy src`): pass, 95 source files
- `pytest tests -q -n auto -p no:cacheprovider`: pass, 3895 passed, 4 xfailed (pre-existing,
  unrelated)

**aircraft-layer/**
- `ruff format --check`: pass (90 files already formatted)
- `ruff check`: pass
- `mypy --strict` (`cd aircraft-layer && .venv/bin/mypy src`): pass, 29 source files
- `pytest tests -q -n auto -p no:cacheprovider`: pass, 1233 passed
- `luac5.1 -p` on every touched Lua file (`dcs-export/*.lua`, `dcs-export/Petrobrain/*.lua`): pass

### Notable Discoveries

- **The plan's Co-moving Fields table was the actual source of truth for one non-obvious
  decision**, not the numbered Design steps: step 2 (`hvrt_step`) tells the Implementer to drop
  the write-back into `parked_flight_state.goal` but never explicitly says to stop writing
  `runner.ai_pilot_goal_last_sent_seq` from that branch. The table (row for that field) names only
  the "set" branch as its writer. Leaving the old `runner.ai_pilot_goal_last_sent_seq = bumped_seq`
  line in would have silently corrupted the "set" gate's comparison on a later poll (the gate
  compares the *internal* version, but would have been fed a *wire-space* number) — caught before
  committing by cross-checking the table against the numbered steps, not by a test failing (no test
  in the original suite exercised a `hvrt_step` immediately followed by a second poll's "set" send
  on the same activation).
- **Test churn was exactly where the plan's own Risks section said it would be**: four CBTM tests'
  hard-coded `sent[9] == 1` all needed to become `2`, because the module's own pre-existing
  behaviour (every CBTM-transition call also sends an ordinary goal message first, in the same
  poll) now means the CBTM send is always the *second* draw from the shared counter, not an
  independent first draw of its own. Grepped `goal_seq`/`cbtm_seq` across the whole test file after
  the edit, per the plan's own instruction, and found one more coincidental-coupling case
  (`test_a_turn_heading_transition_is_applied_and_sent`) that the plan's worked examples did not
  name but its own "Risks & Unknowns" language exactly described.
