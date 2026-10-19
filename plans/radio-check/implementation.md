### Implementation Summary

Implemented both backlog items in the decided build order: BL-B82 (no scanning on the ground,
replacing the on-ground silence default) then BL-B81 (radio check / greeting), per
`body-layer/ROADMAP/BL-B82.md` / `BL-B81.md` and `plans/radio-check/plan.md`.

### Files Changed

- `body-layer/src/belief/crew_console.py` —
  - Removed `CrewConsole.maybe_apply_on_ground_default`/`_on_ground_default_applied` (and the
    module docstring paragraph describing it); added `on_ground: bool` field, refreshed every
    poll the same way `enrichment` is.
  - Added `_LOOK_COMMAND_TOKENS` (every scan token + `watch_nearest`/`watch_nearest_air_defence`/
    `follow`) and a `handle_command` branch: `self.on_ground and token in _LOOK_COMMAND_TOKENS` ->
    `render_unable("ON_GROUND")`, placed after the silence-ends-on-any-command reset (so a
    refused-on-the-ground look command still ends silence) and after the world-model refusal
    check (refusal still wins).
  - Added `radio_check`/`greeting` to `DISPATCHED_COMMAND_TOKENS`, dispatch branches in
    `handle_command`, and `_handle_radio_check`/`_handle_greeting` handlers.
  - Added `_RADIO_CHECK_PATTERN`/`_GREETING_PATTERN`/`_GREETING_TIMES_OF_DAY` and
    `_match_radio_check_or_greeting`; `handle_line` now checks it (same position as the existing
    `!inject-urgent`/`!voice` special cases) and routes a match straight to `handle_command`.
  - `reset_for_new_mission`'s docstring updated for the field swap.
- `body-layer/src/belief/speech.py` — `render_radio_check`, `render_greeting`
  (`_GREETING_TEMPLATES`), and `_UNABLE_TEMPLATES["ON_GROUND"] = "Unable, on the ground."`.
- `body-layer/src/logger.py` —
  - `PerceptionLogger.run_once` and `ConsolePerceptionRunner.run_once`: the single
    `[observation for source in self.sources for observation in source.poll(...)]`
    comprehension in each is now gated on `ownship.alt_agl_m > ON_GROUND_AGL_THRESHOLD_M`,
    else `[]`. `ContactStore.tick`/`store.ingest([], ...)` still run unconditionally, so existing
    belief keeps decaying normally — Petrovich just stops adding anything new to it while on the
    ground. This is the "cleanest seam" the plan called for: one gate per poll loop, no change to
    any individual `PerceptionSource`.
  - The old `crew_console.maybe_apply_on_ground_default(runner.last_ownship_state)` call site is
    now `crew_console.on_ground = runner.last_ownship_state.alt_agl_m <=
    ON_GROUND_AGL_THRESHOLD_M`, refreshed every poll (not a one-shot latch) at the same point
    `crew_console.enrichment` is refreshed.
  - `ON_GROUND_AGL_THRESHOLD_M` imported from `belief.crew_console`.
- `body-layer/tests/test_crew_console.py` — removed the `maybe_apply_on_ground_default` test
  block; added look-command/on-ground/radio-check/greeting tests (below).
- `body-layer/tests/test_logger.py` — added on-ground perception-gating tests for both poll
  loops (below).
- `plans/radio-check/plan.md` — the implementation plan (committed before building).

**Not changed:** `body-layer/CLAUDE.md` — grepped first; it never described the on-ground silence
default (no "on-ground"/`maybe_apply`/`silent mode` text anywhere in it), so there was nothing to
update, matching the task's own "if it describes..." condition. `aircraft-layer/` — untouched,
per the F10 decision below.

### Tests Added

- `test_crew_console.py`:
  - `test_look_command_on_ground_answers_unable`, `test_scan_command_on_ground_answers_unable`,
    `test_follow_on_ground_answers_unable` — `_LOOK_COMMAND_TOKENS` members refused on the ground.
  - `test_look_command_airborne_dispatches_normally` — same token, same store, only `on_ground`
    differs.
  - `test_look_command_on_ground_still_ends_silence` — refused-on-the-ground is still a real
    command for silence-ending purposes.
  - `test_non_look_command_on_ground_dispatches_normally` — `observ_on` is unaffected.
  - `test_refusal_mode_wins_over_on_ground_for_a_look_command` — BL-15 refusal takes precedence.
  - `test_radio_check_token_answers_loud_and_clear`, `test_radio_check_works_on_the_ground`,
    `test_radio_check_ends_an_explicit_silence`, `test_radio_check_in_refusal_mode_gets_the_refusal_line`.
  - `test_greeting_token_echoes_the_pilots_own_word` (parametrized, all four times of day),
    `test_greeting_with_missing_slot_degrades_to_say_again`.
  - `test_typed_radio_check_dispatches_through_handle_line`,
    `test_typed_greeting_dispatches_through_handle_line` (parametrized, incl. mixed case and a
    trailing period), `test_typed_radio_check_in_refusal_mode_gets_the_refusal_line`.
- `test_logger.py`:
  - `test_run_once_polls_no_source_while_on_the_ground` /
    `test_run_once_resumes_polling_once_above_the_ground_threshold` (`PerceptionLogger`).
  - `test_console_runner_ingests_nothing_while_on_the_ground` /
    `test_console_runner_resumes_ingesting_once_above_the_ground_threshold` /
    `test_console_runner_existing_belief_decays_but_is_not_wiped_on_the_ground`
    (`ConsolePerceptionRunner`) — the last one plants a contact airborne, polls once on the
    ground with an empty source, and asserts the contact is still there (existing belief kept,
    not wiped).

**Counterfactual run (per this role's "show the red" guidance):** since every one of the
perception-gating tests asserts an *absence* ("nothing was ingested"), I broke the
`ConsolePerceptionRunner.run_once` gate (forced the `if` branch to always poll, verified by
`shasum` before/after and restored from a byte-for-byte backup copy, not `git checkout`) and
confirmed `test_console_runner_ingests_nothing_while_on_the_ground` goes red for the stated
reason (an `Observation` that should not exist appears), while the sibling `PerceptionLogger`
test — a different gate, untouched by this edit — stayed green, confirming the two gates are
actually independent rather than one incidentally covering for the other.

### Checks

**body-layer/**
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy --strict` (`cd body-layer && .venv/bin/mypy src`): pass (68 source files)
- `pytest tests -q`: pass (2236 passed, 4 xfailed — same pre-existing xfails as before this
  branch)

**aircraft-layer/**: not touched, no checks run (no F10 item added — see below).

### Notable Discoveries / Decisions

- **`_LOOK_COMMAND_TOKENS` scope is a judgment call, stated in the plan and here rather than
  escalated** (local/reversible per the Escalation Rules): every scan token +
  `watch_nearest`/`watch_nearest_air_defence`/`follow`. The task names `watch` and `scan forward`
  as examples; `follow` is the one other token that shares their job exactly (it immediately
  raises binoculars onto a target — `logger.py`'s "any command lowers binoculars" glue reads
  `CrewConsole.last_command_target_contact_id`, which only `follow` sets). `select_target`/
  `engage`/`step`/`report*` are excluded: they only read existing belief and already degrade
  sensibly ("no such contact") when belief is thin from not having scanned.
- **`ON_GROUND_AGL_THRESHOLD_M` was not newly wired through `tuning.py`.** It is a pre-existing
  constant (not new), now doing more work (gating perception in two poll loops, not just the old
  one-shot silence default) — flagged per the root CLAUDE.md rule rather than silently expanded
  in scope. Still a bare module literal in `crew_console.py`; would want the mechanism if someone
  touches its semantics next.
- **F10 item for radio check/greeting: not added.** Checked the existing pattern first (per "do
  not reinvent the wheel") — every current F10 item is a Hook-side Lua menu entry in
  `aircraft-layer/dcs-export/`, deployed via `WORKFLOW.md`'s opt-in and requiring a DCS-side
  redeploy. That is a cross-subproject change, not a trivial extension of something already in
  place, so per the task's own conditional ("only if trivial") I did not add one. Radio check's
  stated purpose (confirm intercom/Petrobrain are alive during engine start) is already served by
  voice once `audio-adapter` recognises the phrase.
- **Voice wiring for BL-B81 is a no-op on the body-layer side beyond the token dispatch added
  above.** `handle_transcript`/`_act_on_voice_decision`'s "act" path already calls
  `handle_command` generically for whatever token `audio-adapter`'s `command_matcher` resolves
  to — recognising "radio check"/the four greetings as those tokens is an `audio-adapter`
  vocabulary change in a separate subproject, out of scope here and not touched.
- **Existing belief survives a ground poll (kept, not wiped)** — `self.store.tick`/
  `self.store.ingest([], ...)` still run unconditionally every poll regardless of `on_ground`;
  only the observation-gathering comprehension is gated. Verified by
  `test_console_runner_existing_belief_decays_but_is_not_wiped_on_the_ground`.
- One implementation slip caught by running the suite rather than by inspection: a
  `git checkout -- src/logger.py` run mid-session (meant to restore after a counterfactual probe)
  silently discarded all of that file's uncommitted `[[BL-B82]]` edits, since nothing had been
  committed yet. Caught immediately by `git status --short` no longer listing `logger.py` as
  modified; redone from the diff already reviewed above, re-verified with `mypy`/`ruff`/`pytest`
  before the second (correct, backup-copy-based) counterfactual run. No trace of this remains in
  the final diff — noted here only because the role's own guidance is to record what the
  verification scope should include, and "which file a destructive git command touches" is
  exactly that.
