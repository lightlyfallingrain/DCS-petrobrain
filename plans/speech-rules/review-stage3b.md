### Review Summary

Reviewed commit `7b9569187496f2874126497364168f540acfb88f` ("BL-17 Stage 3b: rule categories and
dispatch gates") against `plans/speech-rules/plan.md` Revision 2's Stage 3b section, D16, U19–U21
(U22–U24 belong to later stages, see below), `body-layer/ROADMAP/BL-17.md`'s "Category gates,
before any rule runs" and "Answers to the second goal check," and `plans/speech-rules/
alignment.md`'s E13/E17 rows.

Scope actually shipped matches the plan's own Stage 3b item list exactly: `CrewState`
(`belief/crew_state.py`, new, leaf module), the closed `GATE_REGISTRY` (`always`/`flight_control`,
`rules/gates.py`, new), `when.speech`'s signature change to `(id, pattern, category, handler)`
with load-time category validation against the registry, the hold-and-retry mechanism
(`pending_rule_dispatch`/`drain_pending_rule_dispatch`/`RULE_GATE_HOLD_TIMEOUT_S`, U20),
`turn_heading_relative`'s migration to `category="flight_control"`, `increment_ai_heading`'s dead
`NOT_READY` branch removal, and `category` riding along on `PUT /rules` for Stage 3c's benefit.
No Stage 3a matching-logic changes, no new rules, no Stage 3c/4 work shipped — confirmed by diff,
not just by the commit message.

**Gate-before-handler is verified structurally, not just by example.** `_dispatch_rule` (the only
thing that ever calls `self.rule_runner`) has exactly two call sites, both downstream of
`check_gate`: `_handle_rule`'s `PASS` branch and `drain_pending_rule_dispatch`'s later `PASS`. The
brain's command route (`_handle_brain_command`) dispatches through the same `handle_command` —
confirmed by reading the call site, not assumed — so a future rule reachable from `BRAIN_COMMANDS`
would get the same gate with no extra wiring (today's static allowlist contains no rule id, so
nothing yet exercises this, which is correct for this stage's scope).

**Hold-and-retry mechanics are correct and well tested**: `PASS`/`HOLD`/`UNABLE` all re-derive from
a fresh `current_crew_state()` call each time (dispatch and drain alike — no stale snapshot
reused), `pending_rule_dispatch` is replaced wholesale on a second held match (U21, tested), the
timeout comparison (`now_sim - held_since_sim < RULE_GATE_HOLD_TIMEOUT_S`) is tested at both sides
of the boundary, and mission restart clears it via the generic field-enumeration test in
`test_mission_start_reset.py` (confirmed `pending_rule_dispatch`/`rule_categories` are *not* in
`_CREW_CONSOLE_PRESERVE`, so they reset to their dataclass defaults — I checked this by reading the
preserve-set and the generic test, not by trusting the implementation log's claim).

**`CrewState`'s stub fields are honest, not guessed values dressed as facts.** `seat="copilot"` is
accurate today (Petrovich has never occupied the pilot seat in this codebase — `ParkedFlightState`
already carries a real, DCS-derived `player_seat` field for the *player's* seat, which is a
different, already-wired fact `CrewState.seat` does not duplicate or contradict). `eyes_free=True`
matches the goal check's own Q8 answer (naked-eye scan stays available while flying).
`hands_free=not has_controls` is a real derivation, not a stub.

**Checks** (fresh `.venv`s built from `/opt/homebrew/bin/python3.14`, exactly as the task
described):
- body-layer: `ruff format --check`/`ruff check`: pass. `mypy src` (run from inside `body-layer/`):
  pass, 91 files, 0 issues. `fast-tests.sh body-layer`: 2635 passed, 1 failed — the named
  pre-existing, unrelated `test_shipped_effector_config_loads_without_errors` (empty row in
  `config/sequences/mi-24p/seat-copilot.md`), exactly as the task brief predicted.
- audio-adapter: `ruff format --check`/`ruff check`: pass. `mypy src`: pass, 17 files, 0 issues.
  `fast-tests.sh audio-adapter`: 467 passed, 2 skipped.
- `git status --porcelain` clean before and after (venvs are gitignored, confirmed via
  `git check-ignore -v`); no staged-but-uncommitted drift.

### Required Fixes

1. **Before Stage 4 is implemented: `CrewState.settling`/the `flight_control` gate's shared
   precondition does not generalize to the other six commands Stage 4 plans to gate under it, and
   the plan's own justification for removing their individual checks is factually wrong.**
   `plan.md` line 307 claims `settling` (`has_controls and held_heading is None`) is "the same
   proxy every flight handler already checks today" — I checked this against the actual shipped
   handlers rather than taking the claim at face value, and it is false for most of them:
   - `_handle_speed_step` checks `held_speed is None` (not `held_heading`).
   - `_handle_altitude_step`/`_handle_hold_altitude` check `held_altitude is None`.
   - `_handle_level_flight` checks "all three of `held_heading`/`held_altitude`/`held_speed` are
     None" (a *weaker* condition than any single-field check — it tolerates partial knowledge).
   - `_handle_set_speed`/`_handle_set_altitude`/`_handle_turn_heading` (the absolute forms) have
     **no** precondition check at all.
   - Only `increment_ai_heading` (this stage's one ported rule) and `_handle_level_off` actually
     use `held_heading` as their own gate.

   Stage 4's own plan text (item 1) says "every `held_* is None -> NOT_READY` branch inside these
   is removed... the gate already guarantees it by the time the action runs" — but the shared
   `flight_control` gate only ever guarantees `held_heading is not None`. If Stage 4 ports
   `speed_step`/`altitude_step`/`hold_altitude` onto this same category and deletes their own
   `held_speed`/`held_altitude` checks as planned, the result is a real correctness bug in either
   direction: a command can be gated `HOLD` waiting on `held_heading` while its own needed field
   (`held_speed`/`held_altitude`) is already available (needless delay, and a possible false
   "unable, not ready" if `held_heading` alone takes longer than the timeout), or gated `PASS`
   while its own needed field is still `None` (the removed check was the only thing stopping a
   `None` from reaching arithmetic downstream). This is not hypothetical: the four fields are
   parsed from the same telemetry sample but are independently optional
   (`ai_pilot_wheel.py`'s `_parse_float` per field), which is presumably *why* the original authors
   checked each handler's own field rather than one proxy for all of them.

   This does not block Stage 3b's own merge — the one rule it ships (`turn_heading_relative`) is
   correctly gated, since `held_heading` genuinely is its precondition, and nothing else is ported
   yet. But it must be resolved (most likely: `CrewState` gains the two other held fields, and
   `_flight_control`'s `HOLD` condition becomes "the fields *this specific action* needs are not
   all present" rather than one shared boolean — or the per-handler checks are kept and only the
   coarse has-controls/no-controls split moves to the gate) before Stage 4's own Architect/plan
   pass, not discovered during Stage 4 implementation.

2. **Minor: `belief/speech.py`'s new `"NOT_FLYING"`/`"HANDS_BUSY"` comment is already wrong on
   landing.** It reads "Declared here even though it is not reachable until Stage 4 ports the rest
   of the flight commands (`turn_heading_relative` is the only rule in this category today...)".
   `NOT_FLYING` **is** reachable right now, in this exact commit — `turn_heading_relative` is
   already migrated to `category="flight_control"` by this same stage (plan.md's own Stage 3b item
   8), and `test_gate_unable_speaks_the_reason_and_never_calls_the_runner`/
   `test_gate_refuses_not_flying_before_the_action_ever_runs` both assert exactly this. The comment
   appears to be carried forward verbatim from `plan.md`'s own Stage 3b item 6 text, which has the
   same inaccuracy (a planning-time statement that predates the decision, made in the same
   revision, to migrate `turn_heading_relative` within this stage). Only `"HANDS_BUSY"` is actually
   unreachable until a later stage. Fix the comment (and, ideally, the plan text it was copied
   from) to say so — a future reader of `speech.py` in isolation would otherwise conclude
   `"NOT_FLYING"` is dead code in this stage, when it is live and tested.

### Optional Refinements

- **Harden the dispatch boundary against a bare Python exception from inside an action, not just
  from a Lua-side error.** `increment_ai_heading`'s new `assert current is not None` is correctly
  unreachable today (the gate structurally guarantees it before `PASS`), consistent with this
  module's existing `assert self.rule_runner is not None` convention. But `run_rule`'s own
  exception handling (`except (RuleRuntimeError, RuleBudgetExceeded)`) does not catch
  `AssertionError`, and this very stage's own research
  (`research/2026-11-17-lupa-sandbox.md`, cited in the `when.speech` `*args` departure) found that
  lupa propagates a Python exception raised inside a callback Lua calls *unwrapped* through the
  Lua boundary — the same hazard the `*args` fix exists to avoid for a *load*-time arity mismatch.
  If a future refactor ever lets `_dispatch_rule` be reached without the gate (a real but distant
  risk, not a defect in this diff), the failure mode today would be an uncaught crash rather than
  D6's "Action file error." degrade. Not required now — the guarantee holds for every call site
  this diff creates — but worth a broader `except Exception` (logged, degraded to
  `ACTION_FILE_ERROR_LINE`) at the dispatch boundary the next time this area is touched, given the
  project already demonstrably cares about this exact propagation shape.
- **The accepted-items ledger shows U22/U23/U24 as "never named" in `implementation.md`** — this is
  a mechanical floor, not a real gap: all three are explicitly deferred to named stages in
  `plan.md`'s own "Answered 2026-11-17" note (U22 → Stage 4/D19's `note_urgent`, U23 → Stage 3c's
  own measurement gate, U24 → "revisit when Stage 5 ships the first effector-writing rule"), and
  `implementation.md`'s Stage 3b section states plainly "No new rules, no Stage 3c/3d/4 work."
  Still, citing the U-numbers explicitly in that sentence (rather than only the stage/decision
  letters) would make `accepted-items-ledger.sh` pass mechanically and leave a cleaner audit trail
  for whoever runs it next — cheap, not blocking.
- **Confirm whether Stage 3d (D20, the effector-write action surface) is tracked separately.**
  `plan.md` describes 3d as "part of the same ... batch as 3b, built alongside it" — it is not
  present in `7b956918` (no `rules/actions.py`/`effector_engine.py` changes), and no later commit
  on this branch builds it either. This review was explicitly scoped to the category/gate commit
  only, so I am not treating this as a Stage-3b defect, but the batch (Stages 0–3, per the user's
  own "stop after stage 3" instruction) should not reach Security/DoD believing 3d shipped when it
  has not — worth a one-line confirmation from whoever is tracking the batch before that gate runs.

### Verdict
APPROVED WITH MINOR FIXES

Required Fix 2 (the comment) is a one-line correction and does not block merging this commit.
Required Fix 1 (the `settling` generalization) does not require touching anything in this commit
either — `turn_heading_relative`'s own gating is correct — but must be resolved before Stage 4 is
implemented; flagging it now, while `CrewState`/`gates.py` are freshly built and the design
decision is still cheap to revisit, is the point of raising it at this review rather than at Stage
4's own Reviewer pass.

### Review Confidence
Full read — every changed file in `7b956918` was read in the diff; `crew_console.py`'s surrounding
dispatch code (`handle_command`, `_handle_brain_command`, `_reset_one_shot_command_state`,
`set_enabled_rule_ids`) and the pre-existing flight handlers (`_handle_set_speed`,
`_handle_speed_step`, `_handle_set_altitude`, `_handle_altitude_step`, `_handle_hold_altitude`,
`_handle_level_off`, `_handle_level_flight`, `_handle_turn_heading`) were read directly from the
current tree, not inferred from the plan or the implementation log, specifically to check Required
Fix 1. All four checks commands (format/lint/type/test, both subprojects) were run directly in
this session, not assumed from the implementation log.
