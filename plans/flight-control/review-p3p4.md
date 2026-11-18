### Review Summary

Reviewed `feature/bl16-p3p4-cbtm` tip `29653f3b` (fast-forwarded cleanly from `59192cfa`) against
`plans/flight-control/plan.md`'s "Revised 2026-11-18 -- Stages P3+P4 ready to build" as narrowed by
its own trailing "Amendment 2026-11-18 (main loop, after the plan check)" (mode-2 only this batch),
`explore-notes.md`'s three 2026-11-18 rounds, and `alignment.md`'s goal check + plan check for this
batch (both CONCERNS, both settled by the implementation's own Fix 1/Fix 2).

Checks run this pass (binaries from the main checkout's venvs, cwd inside this worktree's
subproject dirs, per the dispatch instructions):

- **aircraft-layer**: `ruff format --check` -- 85 files unchanged; `ruff check` -- clean; `mypy src`
  -- 28 files, no issues; full `pytest tests -q -m "not slow"` -- **961 passed**, matching the
  implementation log.
- **body-layer**: `ruff format --check` -- 227 files unchanged; `ruff check` -- clean; `mypy src`
  -- 92 files, no issues; smoke (`--collect-only`) -- **3649 collected**, no import errors, matching
  the implementation log; targeted run (the nine files the implementation log named) -- **249
  passed**, matching exactly.
- Behaviour constants: both new tunables (`AI_PILOT_RECOVER_AGL_DROP_M`,
  `AI_PILOT_RECOVER_IAS_CEILING_KMH`) checked against the **rendered** `defaults.toml`, not the `#:`
  source comment -- both docstrings are genuinely single-sentence, so there is no second-sentence
  drop here; the rendered text matches the source and the figures (40.0/280.0, same as the goal
  check's own Q-P3-2/Q5 answers) are correct. `BREAK_TURN_BANK_DEG`/`turn_bank_override_deg` are
  correctly absent from the tree -- the main-loop amendment withdrew them from this batch and
  nothing was left behind.
- Scope fit: the amendment's mode-2-only split is respected throughout. Mode 1 gets exactly what
  the amendment specifies -- `_axes_cbtm_align_unready` (permanent `AI_OVERLAY`) and
  `_axes_cbtm_break_unready` (temporary `NOT_READY`) -- and nothing more.
- Fix 1 (second "align for launch" keeps the first snapshot) and Fix 2 (recovery heading stays
  aligned, not restored) are both implemented as specified -- `cbtm_apply_align_for_launch`'s
  re-entry branch and `seed_recovery_goal`'s deliberate heading exclusion, confirmed by reading the
  code directly against the plan text.
- Decision 26 (recovery is press order, not settle order; `pending_order` seeded directly, never
  through the slice-timer rotation) is implemented and tested at the pure-function layer
  (`TestDecideAiPilotWheelCbtm`, `test_ai_pilot_wheel.py`).
- The Q0 simplification the dispatch flagged (`implementation.md`'s fourth "notable
  discovery/simplification"): the user's words were *"first level at current, then start recovery to
  pre alignment params"*; the code freezes **heading** at its current held value but jumps
  **altitude/speed** straight to `seed_recovery_goal`'s pre-align targets rather than first freezing
  them at their current values too. Judged **not a required fix**: the "level, then recover"
  sequencing already describes the plan's pre-existing, previously-reviewed E-P14 auto-recovery
  mechanism exactly (floor/ceiling/payload-drop trigger does the identical thing --
  `decide_ai_pilot_wheel` step 2, unchanged by this round's own notable-discoveries text), so this
  reading does not introduce new risk beyond what E-P14 already carries; and the most coherent
  reading of "level at current" in a conversation that also produced "keep aligned heading" in the
  same answer is that it is talking about **heading** (correctly frozen), not describing a
  mandatory two-phase altitude command the AI-pilot-wheel's own interface has no primitive for
  (there is no "freeze then separately re-target" action distinct from "set target"). Flagging it
  here rather than silently agreeing, because the plan's own "Flight test steps" is the actual
  acceptance gate for this reading and the live sortie should listen for whether the aircraft looks
  like it pulls level before climbing, or climbs directly -- if the user sees it fly wrong, this is
  where to look first.

### Required Fixes

- **No test exercises the Stage P3+P4 composition in `body.py` at all -- only the underlying pure
  functions are tested.** `test_body_ai_pilot_wheel.py`'s own module docstring states its reason for
  existing: *"these tests exercise only the composition `body.py` adds on top"* (as opposed to
  `belief.ai_pilot_wheel`'s own tested surface). This file was **not extended** this round despite
  `body.py` gaining ~150 new lines of composition logic for this batch
  (`_apply_ai_pilot_wheel_goal`'s new `ai_pilot_cbtm_transition` branch, the F-P6 "any voice command
  ends align_phase" branch, the F-P8/Q0 `level_flight`-abort branch, the CBTM wire send, and the
  `agl_m`/`ias_kmh`/`payload_count_dropped` wiring into `decide_ai_pilot_wheel`). Concretely,
  nothing in the test suite exercises, through `_apply_ai_pilot_wheel_goal` itself:
  - a `cbtm_align`/`cbtm_align_for_launch`/`cbtm_break`/`cbtm_break_away` one-shot transition
    reaching `align_phase`, `cbtm_action_sent`, and a correctly-bumped `cbtm_seq` wire send;
  - the F-P6 abort (`ai_pilot_goal_transition` arriving while `align_phase` is `"aligning"` or
    `"launch_aligned"` ends it and still flies the command);
  - the F-P8/Q0 `level_flight` abort reaching `"recovering"` with altitude/speed seeded from
    `pre_align_snapshot` while `align_phase == "launch_aligned"` -- this is exactly the behaviour
    the "Judged not a required fix" note above relies on; without a test pinning it, the Q0 reading
    is undocumented in the one place a future change could silently break it;
  - `decide_ai_pilot_wheel` actually being called with `agl_m`/`ias_kmh`/`payload_count_dropped`
    computed from `runner`'s own live state (as opposed to the pure function's own unit tests, which
    pass these in directly).

  This is the project's own standing lesson from this exact module
  (`.claude/agent-memory/reviewer/feedback_release_path_must_clear_what_a_take_path_assumes_is_none.md`
  and the Co-moving-table-scope lesson it links): a guarantee that reads correctly against the pure
  function in isolation can still be wrong in the glue that drives it, and nothing here would catch
  that. Add `TestApplyAiPilotWheelGoal`-shaped cases to `test_body_ai_pilot_wheel.py` for the four
  bullets above before this batch is considered done.

- **No test exercises the four new rules through the real dispatch path.**
  `test_rules_flight_actions.py`'s own stated convention (module docstring, and every existing
  `TestLevelFlight`/`TestHvrtTranslate`/etc. class) is to differentially test every ported/added
  flight command through `_dispatching_console` -- the real `handle_command` → gate → `run_rule`
  against the real shipped `flight.lua`, checking both the readback text and the resulting state.
  `test_shipped_rule_files_load_with_zero_failures` only confirms the four `cbtm_*` rule ids exist
  in the loaded rule set; nothing calls `handle_command("cbtm_align", ...)` (or the other three) and
  asserts the readback ("Aligning.", "Aligning for launch.", "Breaking left."/"Breaking right.",
  "Breaking away.") or the mode-1 `_axes_cbtm_align_unready`/`_axes_cbtm_break_unready` "unable"
  path (`AI_OVERLAY`/`NOT_READY`) the same way `TestHandoverActions`/`TestSeatNeverGatesMode1` do for
  the adjacent handover commands. Add a `TestCbtm*` class in the same file, mirroring the existing
  classes' shape, covering at minimum: each rule's overlay-mode readback and action dispatch, and
  each of the two gated rules' mode-1 "unable" reason.

### Optional Refinements

- **`cbtm_align()` unconditionally restarts a plain alignment from any prior `align_phase`,
  including mid-`"recovering"`.** The implementation's own notable-discoveries note flags this
  honestly: the plan only specifies Fix 1's re-entry rule for `cbtm_align_for_launch`, not for plain
  `cbtm_align`. Read through to a worst case: "align" said mid-recovery sets `align_phase =
  "aligning"` and clears `pre_align_snapshot`, but does not touch the in-flight altitude/speed
  recovery goal already seeded -- so the recovery keeps climbing in the background while the
  aircraft also re-aligns. If "align for launch" is then said again, `cbtm_apply_align_for_launch`
  sees `align_phase == "aligning"` (not `"recovering"`/`"launch_aligned"`), so it is **not** caught
  by Fix 1's re-entry branch and re-captures a fresh snapshot -- potentially from mid-recovery
  altitude/speed, the exact "would not" case the original goal check warned against, reachable
  through one extra step the plan never considered. Low likelihood in a real sortie (it requires
  saying "align" with no launch intent while a recovery from an *earlier* shot is still climbing),
  and not a safety issue (the floor/ceiling limits still apply independently), but worth a one-line
  decision from the user rather than leaving it to the natural-reading default. (Optional: either
  confirm the default is fine, or have `cbtm_align()` also keep an existing `pre_align_snapshot`
  while `"recovering"`, matching `cbtm_align_for_launch`'s own posture.)
- **The plan's "Flight test steps" section does not call out the two re-entry edge cases above**
  (a second "align for launch" during recovery -- Fix 1's own worked case -- and a plain "align"
  during recovery -- the refinement above). Both are cheap to add as one more line each to that
  section so the live sortie actually exercises them, rather than relying on the mechanism alone.
- Consider renaming `cbtm_action_sent`'s simplified break-wins check (reads every poll while it
  names a break, rather than the plan's literal "still running per Lua's own `lua_cbtm_status`"
  condition) in its own docstring to state plainly that it is a deliberate, safe narrowing -- it
  already does this reasonably well; no code change needed, just confirming the existing docstring
  is sufficient (it is).

### Verdict

NEEDS REVISION -- both required fixes are test-coverage gaps, not behavioural defects; the
mechanism itself traces cleanly against the plan, the amendment, and both goal/plan check rounds,
and every static check (format/lint/type/targeted-and-smoke tests) is green. Once the two missing
test classes land (body.py composition, and real-dispatch rule tests for the four new commands),
this is ready for Security's deep-analysis pass and DoD -- DoD's own acceptance gate still needs a
live sortie per the plan's "Flight test steps," unchanged by this review.

### Review Confidence

Full read of the plan's P3+P4 section (including the mid-task amendment and the main-loop
amendment), the three relevant `explore-notes.md` rounds, both `alignment.md` check rounds for this
batch, the implementation log's full "Notable discoveries" section, and the actual changed code in
`body-layer/src/belief/ai_pilot_wheel.py`, `body-layer/src/belief/crew_console.py`,
`body-layer/src/body.py`, and `body-layer/src/rules/actions.py`. Not independently re-read line by
line: `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`'s own per-frame press/mode-cycle
mechanics (Lua) -- taken on the implementation log's own account (`luac5.1 -p` clean, the bytecode
global-safety check clean, 961 aircraft-layer tests passed including the new `TestOnStop` case) and
the project's own standing posture that Lua press-timing mechanics are validated live, never by
static review. No live DCS flight was possible from this environment, consistent with the
implementation log's own note and the plan's "Flight test steps" remaining the acceptance gate.

---

### Re-review (2026-11-19) -- review-fix round, commit `6e0421e3`

Scope: `6e0421e3` only (`body-layer/tests/test_body_ai_pilot_wheel.py`,
`body-layer/tests/test_rules_flight_actions.py`, and `implementation.md`'s "Review-fix round
(2026-11-19)" note), judged against this file's own Required Fixes 1/2. Fast-forwarded cleanly
from `59192cfa` to `6e0421e3` (`d5eaee9b` in between is the Reviewer commit this round answers).
No `src/` file changed -- confirmed from `git show --stat 6e0421e3` (two test files plus the plan
note, 585 insertions, 5 deletions) and from reading `body.py`/`ai_pilot_wheel.py`/
`actions.py` directly: untouched by this commit.

**Required Fix 1 -- CLOSED.** `test_body_ai_pilot_wheel.py` gained `TestCbtmTransitions`,
`TestFlightCommandEndsAlignment`, `TestLevelFlightAbortRecovery`, `TestRecoveryTriggerWiring`
(20 new tests). Read each class against the four bullets this fix named, not just the class
names: `TestCbtmTransitions` drives all four `cbtm_*` transitions through
`_apply_ai_pilot_wheel_goal` itself and asserts `align_phase`/`cbtm_action_sent`/the bumped
`cbtm_seq` wire send (via a `_cbtm_send` helper that filters on the `cbtm_action` field rather
than asserting a brittle total-call count -- see the next finding); `TestFlightCommandEndsAlignment`
covers F-P6 for both `"aligning"` and `"launch_aligned"`, plus the `"recovering"`-is-excluded
negative case; `TestLevelFlightAbortRecovery` covers the F-P8/Q0 abort from both `"launch_aligned"`
(recovery seeded from the snapshot, heading frozen at the *held* value, not the snapshot's) and
`"aligning"` (nothing to recover); `TestRecoveryTriggerWiring` drives the payload-drop, AGL-floor,
and (read past the excerpt but present in the file) IAS-ceiling triggers from `runner`'s own live
state (`last_ownship_state.alt_agl_m`, `last_ias_kmh`, a real `previous_payload_counts` diff), not
the pure function's direct arguments. This is exactly what the fix asked for, not a decorative
pass -- every test asserts real post-call state, none merely exercises a code path without
checking its effect.

**Required Fix 2 -- CLOSED.** `test_rules_flight_actions.py` gained `TestCbtmActions` (10 tests),
dispatching all four `cbtm_*` rules through `_dispatching_console`/`handle_command` against the
real shipped `flight.lua`: each rule's overlay readback and `ai_pilot_cbtm_transition` value, the
coarse "not flying" gate taking priority over either mode body, and both mode-1 "unable" reasons
(`AI_OVERLAY` for align/align-for-launch, `NOT_READY` for the two breaks). Matches
`TestHandoverActions`/`TestSeatNeverGatesMode1`'s own shape exactly, as the fix asked.

**The implementer's own flagged "extra null-param goal message on first poll" -- judged genuinely
harmless, not a required fix.** Traced by hand against both sides of the wire rather than taking
the docstring's account on its word:
- On the body-layer side (`body.py`'s `_apply_ai_pilot_wheel_goal`), the unconditional
  `goal=goal` write-back (the function's own closing `replace(...)` call) only produces a
  all-`None` `AiPilotWheelGoal()` when `state.goal` was `None` *and* nothing in this same poll's
  transition handling touched it -- true only for a bare CBTM/`hvrt_step` trigger with no prior
  goal, confirmed by reading every branch above it (heading/altitude/speed/HVRT requests all call
  a `set_parked_*`/`set_hvrt_direction` helper that bumps `goal_seq` and fills a real field,
  so they never hit this gap). **This is not new to CBTM** -- `hvrt_step` (Stage P2b) already had
  the identical shape, so CBTM reuses an existing gap rather than opening a new one, exactly as
  the implementer's note claims (confirmed by reading `hvrt_step`'s own branch, not assumed).
- On the Lua side (`ai_pilot_wheel.lua`'s `handle_ai_pilot_goal_command`), the blank message
  (`param=nil`, `goal_seq=0`, `cbtm_action=nil`) arrives first, strictly before the CBTM-carrying
  second message (both are synchronous, blocking HTTP POSTs from the same function call, so
  arrival order is guaranteed). On that first message: `param == ai_pilot_goal.param` already
  holds (`ai_pilot_goal.param` is reset to `nil` by the unpark branch, line 1385, and starts `nil`
  at table construction, line 372) -- so `ai_pilot_goal_release_hold()` and the mode-cycle-reset
  block are **not** triggered; `progress` is set to `"idle"`, which it already was. The second,
  CBTM-carrying message then runs its own branch unaffected -- `cbtm_seq` has its own comparison,
  untouched by the first message. Read for the one case that would make this unsafe (a *stale*
  non-`nil` `ai_pilot_goal.param` on the Lua side at the moment a `None`-state activation starts on
  the body side) and found none: the unpark branch clears it, and `_apply_ai_pilot_wheel_goal`'s
  own unparked branch resets `runner.ai_pilot_goal_last_sent_seq` to `None` in lockstep, so the two
  sides cannot disagree about "no goal yet" at the point this fires.
- Net effect confirmed: one extra, no-op `POST /command/ai_pilot_goal` per CBTM (or bare
  `hvrt_step`) activation that starts with no prior goal -- no state change, no spoken side
  effect, self-correcting the next poll. **Agreeing with the implementer's own verdict**: not a
  behavioural defect, correctly left as test-coverage-only scope for this round, and correctly
  not silently hidden (flagged in both the implementation log and the test module's own
  docstring). Not escalated to a required fix. One optional note: this is a real, if harmless,
  double-send on the wire and would cost nothing to file as a one-line backlog item for future
  reference (its own "why this exists" is now only in a test docstring, which a later refactor
  of `_apply_ai_pilot_wheel_goal` could silently invalidate without anyone reading it) -- the
  user's call, not a blocker.

**Checks reproduced independently, not taken on the implementation log's word**:
`ruff format --check .` -- clean on every file this commit touches (the 2 files flagged
reformattable, `research/2026-10-05-security-audit.md` and one other, are pre-existing and
untouched by this commit -- unrelated markdown-embedded code snippets, not this round's own);
`ruff check .` -- all checks passed; `mypy src` -- 92 files, no issues; the exact nine-file
targeted run (`test_ai_pilot_wheel.py` + `test_body_ai_pilot_wheel.py` +
`test_crew_console_ai_pilot_wheel.py` + `test_flight_control.py` + `test_body_flight_control.py` +
`test_rules_flight_actions.py` + `test_voice_commands.py` + `test_tuning_defaults_toml.py` +
`test_rule_gates.py`, `-m "not slow"`) -- **275 passed**, matching the implementation log exactly
(up from 249 by exactly the 26 new tests, 20 + 10 - 4 reused-helper overlap aside, consistent with
the log's own 29/69 per-file breakdown); `tests --collect-only` (smoke) -- **3675 collected**, up
from 3649 by exactly 26, no import errors. `aircraft-layer` untouched by this commit (no files
under `aircraft-layer/` in the diff) -- correctly not re-run.

#### Verdict (re-review)

**APPROVED.** Both Required Fixes are closed with real, non-decorative test coverage that
matches what each fix asked for; the one flagged "extra null-param goal message" is independently
confirmed harmless (traced through both the body-layer write-back logic and the Lua command
handler, not taken on trust) and correctly left outside this round's scope. No production code
changed. Ready for Security's deep-analysis pass and DoD; DoD's own "Flight test steps" live
sortie remains the acceptance gate, unchanged by this round.

#### Review Confidence (re-review)

Full read of `6e0421e3`'s diff (both test files, in full, and the implementation-log note) against
both Required Fixes; traced the flagged null-param-message claim by hand through
`body.py`'s `_apply_ai_pilot_wheel_goal` and `ai_pilot_wheel.lua`'s `handle_ai_pilot_goal_command`
rather than accepting the docstring's account; independently reran every check this round's log
reports (`ruff format --check`, `ruff check`, `mypy src`, the nine-file targeted run, the
whole-suite collect-only smoke) rather than trusting the logged numbers. Not re-run: the full,
non-`-m "not slow"` suite and any `aircraft-layer` check (neither touched by this commit); no live
DCS flight was possible from this environment, consistent with every prior pass on this feature.
