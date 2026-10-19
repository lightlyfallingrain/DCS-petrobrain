### Review Summary

Reviewed `feature/radio-check` at `49c24eb1` (body-layer `01a69ec7`, audio-adapter `49c24eb1`)
against `body-layer/ROADMAP/BL-B82.md`, `BL-B81.md`, `plans/radio-check/plan.md` and
`implementation.md`. Scope matches the plan exactly: BL-B82's on-ground scan gate (replacing
`maybe_apply_on_ground_default`) and BL-B81's radio-check/greeting commands, wired through both
body-layer and audio-adapter.

Checked, with code read (not just the implementation report) and mutation-verified where the
guidance calls for it:

- **Decided behaviour matches the entry files.** Every poll re-evaluates `on_ground` (not a
  one-shot latch); perception is gated in both `PerceptionLogger.run_once` and
  `ConsolePerceptionRunner.run_once`; a look command (`_LOOK_COMMAND_TOKENS`) on the ground answers
  `"Unable, on the ground."`; every other command, including `radio_check`/`greeting`, is heard and
  answered normally, ends an explicit `silence`, and takes the fixed refusal line in refusal mode.
  Greeting echoes the pilot's own word (`time_of_day` slot), not the sim clock. All confirmed by
  direct test read (`test_crew_console.py` lines ~1356-1451, ~1656-1700) and by running the
  existing suite — see mutation checks below.
- **Removal of `maybe_apply_on_ground_default`/`_on_ground_default_applied` is complete.** Grepped
  `*.py`/`*.md` repo-wide: no remaining reference outside historical plan docs (`plans/
  spu8-intercom/*`, `plans/bl15-mission-start/plan.md`) that correctly describe the superseded
  mechanism, and one comment-only header line in `test_crew_console.py` naming what the new tests
  replace. No dangling call site, test, or docstring. `CrewConsole.reset_for_new_mission`'s
  docstring was rewritten to describe `on_ground`, with the supersession dated and named
  (`[[BL-B82]]`, user direction 2026-10-19) rather than silently deleted — matches `docs/
  PROCESS.md`'s "marked, not deleted" rule.
- **BL-15's completeness test automatically covers `on_ground`.** `test_crew_console_reset_
  preserves_declared_fields_and_resets_rest` enumerates via `dataclasses.fields()` rather than a
  hard-coded name list, so the new `on_ground` field falls into the "resets to constructor default"
  bucket with no test file edit required — confirmed by reading the test and by the full suite
  passing (2236 passed, 4 xfailed).
- **`on_ground` is refreshed before command handling on every poll-loop path.** In `_run_crew_
  text_poll_loop`, `crew_console.on_ground` is set right after `run_once()` (mirroring
  `enrichment`), and both `_poll_f10_commands` and `_poll_transcripts` run later in the same
  iteration — so F10 and voice always see this poll's value. Typed crew-text runs on a separate
  REPL thread reading the same shared field asynchronously, the same latency class `enrichment`
  already has; not a new risk. **Before the first telemetry poll, `on_ground` is `False`** (the
  dataclass default) — i.e. "assumed airborne" until the first `OwnshipState` arrives. Noted as an
  optional refinement below, not a defect: the window is one poll-cycle wide at process start.
- **The `alt_agl_m` gate** — `OwnshipState.alt_agl_m: float = 0.0` is never `None`; `from_telemetry_
  dict` requires the key and raises `KeyError` if absent (pre-existing, unrelated to this change).
  A missing/degenerate reading defaults to `0.0`, which fails toward "on the ground" (no scanning)
  rather than toward over-detection — the safe direction. `ContactStore.tick`/`ingest([], ...)` run
  unconditionally on the ground, so existing belief decays normally and is not wiped — verified by
  `test_console_runner_existing_belief_decays_but_is_not_wiped_on_the_ground` and by my own
  mutation test (below). A contact aging past `LOST_THRESHOLD_S` purely from decay while grounded
  (no new observations) is expected behaviour under the existing decay model, not a new failure
  mode this change introduces.
- **`_LOOK_COMMAND_TOKENS` scope** — every scan token + `watch_nearest`/`watch_nearest_air_
  defence`/`follow`. Matches the two named examples (`watch`, `scan forward`) plus the one other
  token sharing their job (`follow` raises binoculars via `last_command_target_contact_id`).
  `select_target`/`engage`/`step`/`report*` correctly excluded — they read existing belief only and
  degrade sensibly. Confirmed `radio_check`/`greeting` are in `DISPATCHED_COMMAND_TOKENS` and
  **not** in `_LOOK_COMMAND_TOKENS` (checked directly in a REPL). Reasonable, stated judgment call,
  not escalated — correctly so per the Escalation Rules.
- **audio-adapter/body-layer agreement on the `time_of_day` slot shape** — identical key
  (`"time_of_day"`) and identical four string values on both sides; confirmed by reading both
  `_handle_greeting`/`render_greeting` and `vocabulary.py`/`command_matcher.py`'s greeting branch.
  Near-miss matching is measured, not assumed: `test_radio_check_does_not_falsely_fire_on_report_
  or_check_style_speech`, `test_good_night_does_not_collide_with_stop_or_cancel_style_speech`,
  `test_good_job_degrades_rather_than_falsely_resolving_a_greeting` all exist and pass, and the
  stated verb-anchor ratios (`"good"` at exactly `VERB_FLOOR`, `"radio"` at 0.444 below it) check
  out against the actual `VERB_ANCHOR_WORDS`/`VERB_FLOOR` mechanism.
- **Mutation-checked, per role guidance, rather than trusting the report's own counterfactual
  claim:**
  - `crew_console.py`'s `if self.on_ground and token in _LOOK_COMMAND_TOKENS:` guard, neutralized
    with `if False and ...` — `test_look_command_on_ground_answers_unable`, `test_scan_command_
    on_ground_answers_unable`, `test_follow_on_ground_answers_unable` all go red for the stated
    reason (dispatch proceeds and hits `"no world-model connection configured"` instead of the
    refusal line). Restored; suite green again.
  - `logger.py`'s `ConsolePerceptionRunner.run_once` gate, replaced with an unconditional poll —
    `test_console_runner_ingests_nothing_while_on_the_ground` goes red for the stated reason (a
    real `Observation` appears). Restored; suite green again.
- Checks run directly (not taken from the report): body-layer `ruff format --check`, `ruff check`,
  `mypy src` (68 files), `pytest tests -q` (2236 passed, 4 xfailed) — all pass. audio-adapter
  `ruff format --check`, `ruff check`, `mypy src` (15 files), `pytest tests -q` (300 passed, 1
  pre-existing skip) — all pass.

### Required Fixes

- **The hand-synced `time_of_day` drift guard is asymmetric, and audio-adapter's own test
  docstring claims otherwise.** `audio-adapter/tests/test_vocabulary.py::
  test_time_of_day_words_are_exactly_the_four_greetings` says in its docstring: *"body-layer
  asserts the same membership against its own set; a drift then fails a test on whichever side
  changed."* Grepped `body-layer/tests/` and `body-layer/src/belief/*.py`: there is no test
  anywhere that imports or asserts `_GREETING_TIMES_OF_DAY`'s literal membership — the closest
  thing is `test_greeting_token_echoes_the_pilots_own_word`'s four-value `parametrize` list, which
  exercises the four known-good values but would not fail if a fifth value were added to (or one
  removed from) `_GREETING_TIMES_OF_DAY` itself. So today, a body-layer-only change to that set
  (e.g. dropping `"night"`) would pass the full body-layer suite silently, and only surface in
  flight as a voice command that audio-adapter still offers/dispatches but body-layer now answers
  with "say again" — exactly the drift class this mechanism exists to catch, on the one side the
  comment claims is covered. Fix: add a one-line body-layer test pinning `_GREETING_TIMES_OF_DAY ==
  frozenset({"morning", "day", "evening", "night"})` (mirroring the audio-adapter test exactly), so
  the claim in the audio-adapter docstring becomes true rather than aspirational. Cheap, local,
  and closes a real latent gap rather than just correcting a comment.

### Optional Refinements

- **`CrewConsole.on_ground` defaults to `False` ("airborne") until the first telemetry poll
  completes** — a look command issued in the brief window before `runner.last_ownship_state` is
  first set would dispatch rather than refuse, even if the aircraft is sitting on the ramp at
  process start. Narrow (one poll-cycle wide) and low-consequence (degrades to "no contact" absent
  perception, not a crash), but the safer default for an unknown state would be `True`. Worth a
  one-line fix if touched again; not worth a dedicated pass on its own.
- **`ON_GROUND_AGL_THRESHOLD_M` is now doing substantially more work** (gates perception in two
  poll loops plus look-command refusal, versus its previous one-shot silence-default use) while
  staying a bare module literal rather than going through `tuning.py`. Already flagged
  transparently by the implementer in both the plan and the implementation report as a deliberate
  scope-control call, which is the right call for this change — noting it here only so a future
  touch of this constant's semantics is the trigger to finally wire it through the tuning
  mechanism, per root `CLAUDE.md`'s rule.
- **`DISPATCHED_COMMAND_TOKENS` membership note.** `radio_check`/`greeting` correctly land in
  `DISPATCHED_COMMAND_TOKENS` and correctly do not land in `_LOOK_COMMAND_TOKENS` — verified
  directly, no fix needed, recorded here only as evidence this was checked rather than assumed.

### Verdict

APPROVED WITH MINOR FIXES

The one required fix is small (a single test addition on the body-layer side) and does not change
any shipped behaviour — it only closes a documentation/coverage gap the audio-adapter side already
claims exists. Everything else — the decided behaviour, the removal of the superseded mechanism,
the refusal/silence/on-ground ordering, the look-command scope judgment, and the voice-side
near-miss matching — checks out against the entry files and is mutation-verified where the review
guidance calls for it.

### Review Confidence

Full read. Both `crew_console.py`'s and `logger.py`'s relevant diffs were read in full (not
summarized from the implementation report), the ground-gate and look-command-refusal guards were
independently mutation-tested, and both subprojects' format/lint/type/test commands were run
directly rather than taken on the report's word. The one gap found (the asymmetric drift test) was
found by grepping for the specific claim made in a test docstring, not inferred.

### Fix review

Reviewed fix commit `2f1c8d8c` (`Radio-check review fixes: greeting drift test,
on-ground-by-default, tuning`) against this review's one required fix and two of its three
optional refinements, diff base `192c1b0f` (the commit this review itself was written against).
Four files touched: `body-layer/src/belief/crew_console.py`, `body-layer/tests/test_crew_console.py`,
`body-layer/config/defaults.toml`, `audio-adapter/tests/test_vocabulary.py`.

- **Required fix (drift-guard asymmetry) — closed, and verified both directions.**
  `test_greeting_times_of_day_are_exactly_the_four_greetings` was added to
  `body-layer/tests/test_crew_console.py`, pinning `_GREETING_TIMES_OF_DAY ==
  frozenset({"morning", "day", "evening", "night"})` — read directly, matches the drift-guard
  claim exactly. Both test docstrings now name the other side's test function by name (confirmed
  by reading the diff on both files): `test_time_of_day_words_are_exactly_the_four_greetings`'s
  docstring in `audio-adapter/tests/test_vocabulary.py` now says "`test_greeting_times_of_day_
  are_exactly_the_four_greetings` in `body-layer/tests/test_crew_console.py` asserts the same
  membership," and the new body-layer test names it back — the claim each file makes is now
  checkable from either side, closing the exact asymmetry flagged.
- **Optional fix (`on_ground` default flips to `True`) — applied correctly, and the 50-test
  fallout is setup, not weakening.** Confirmed by diff: the dataclass field default changed from
  `False` to `True`, with both the field's own docstring and `reset_for_new_mission`'s updated to
  match (the latter now correctly says resetting to `True` is harmless, since
  `_check_for_new_mission` re-evaluates it from live telemetry the next poll, same as
  `enrichment`). Extracted the function each of the 50 new `console.on_ground = False` lines
  landed in by parsing the diff directly (not trusting the report's count) — all 50 are
  `watch_nearest`/`follow`/`scan_*`/`cancel_task`-after-a-scan/`handle_transcript`-dispatching-a-
  look-token tests; none is named or shaped as an on-ground/airborne test, and the six dedicated
  on-ground tests from the original review (`test_look_command_on_ground_answers_unable` and its
  five neighbours) already set `on_ground` explicitly both ways and received no new line — so no
  test now passes vacuously on the new default, and none of the flipped 50 was meant to exercise
  on-ground behaviour.
- **Mission-restart interaction checked directly (reviewer's own addition, not in the fix
  report).** Read `logger.py`'s `_run_crew_text_poll_loop` body end to end: on a detected mission
  (re)start, `_check_for_new_mission` resets `crew_console` (giving the new `on_ground=True`
  default) and `runner.run_once()` runs immediately after in the *same* iteration, setting
  `runner.last_ownship_state` from real telemetry; `crew_console.on_ground` is then refreshed from
  that same-iteration telemetry (the existing `if runner.last_ownship_state is not None:` block)
  *before* `_poll_f10_commands`/`_poll_transcripts` run later in that same iteration. So a hot/
  airborne mission restart does not wrongly refuse a look command in its first poll — by the time
  any command can dispatch, `on_ground` already reflects the real (airborne) telemetry read that
  same cycle, not the reset default. The only window the new default actually governs is before
  the very first `run_once()` of a fresh process ever completes — narrower than "first poll," and
  the same optional-refinement framing the original review gave it still holds; not a defect.
- **Optional fix (`ON_GROUND_AGL_THRESHOLD_M` wired through `tuning.py`) — applied correctly,
  rendered file checked, no cross-key coupling.** Read the **rendered**
  `body-layer/config/defaults.toml`, not the source `#:` comment: the full warning (what the
  constant does, which direction is dangerous in both directions, used-by) survives as one
  rendered line, because the source comment is written as a single sentence with no internal
  period — the exact trap this role's guidance warns about (generator renders only the first
  sentence) does not apply here because there is only one sentence to begin with. `status:
  uncalibrated | range: 0.5 .. 50.0` matches the declared `lo=0.5, hi=50.0`; the value (`10.0`) is
  unchanged from the prior bare literal, consistent with the fix's own framing. Value-binding
  trap: grepped every consumer (`logger.py`'s only import site, `from belief.crew_console import
  ON_GROUND_AGL_THRESHOLD_M`) — Python fully executes `crew_console.py` (including its top-level
  `tuning.real(...)` call) before binding the name into `logger.py`'s namespace, so the one
  consumer module sees the loaded override, not the code default. `lo`/`hi` are AST float
  literals, not references, matching the declaration form `tuning.py` requires. No cross-key
  coupling: grepped for every other reference to `ON_GROUND_AGL_THRESHOLD_M` in `src/` — the only
  call sites are `logger.py`'s two poll-loop gates and the on-ground refresh, none sharing an
  asserted relationship with another tunable (`belief.decay`'s `OBSERVED_WINDOW_S <
  POSITION_HALF_LIFE_S` coupling is unrelated to this constant).
- **Checks run directly, not taken from the fix report:** body-layer `ruff format --check`, `ruff
  check`, `mypy src` (68 files), `pytest tests -q` (2237 passed, 4 xfailed — matches the report's
  claimed count exactly). audio-adapter `ruff format --check`, `ruff check`, `mypy src` (15 files),
  `pytest tests -q` (300 passed, 1 pre-existing skip — matches).

**No new required fixes.** Both optional refinements the fix addressed were applied correctly and
without regressing the behaviour the original review verified; the third (`DISPATCHED_COMMAND_
TOKENS` membership note) was correctly left alone, as the original review already stated nothing
needed to change there.

### Final Verdict

APPROVED

### Final Review Confidence

Full read. The fix commit's diff was read in full against the diff base this review was itself
written against (not re-reading the whole feature branch), the drift-guard pairing and the
50-test fallout were verified by parsing the diff for function names rather than trusting the
fix report's count, the mission-restart interaction was independently traced through `logger.py`
rather than taken from the report, the rendered `defaults.toml` was read directly (not the source
comment), and both subprojects' format/lint/type/test commands were run directly.
