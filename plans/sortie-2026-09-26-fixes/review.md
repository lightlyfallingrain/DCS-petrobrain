### Review Summary

Reviewed `fix/sortie-2026-09-26`'s substantive commit `195085f` (merged into the branch as
`f1feb5b`), diffed against `main` three-dot (`git diff main...f1feb5b`) since both sides merged
`main` separately. Read `decisions.md` (binding spec), `plan.md`, `implementation.md`,
`diagnosis.md`, and root `CLAUDE.md`'s "Whose job is whose" section and no-omniscience invariant.
Read every changed line of `body-layer/src/belief/{contacts,optic_policy,crew_console}.py`,
`body-layer/src/logger.py`, `body-layer/src/belief/decay.py`, and all new/modified tests.

This is careful, well-scoped work. The one deliberate deviation from the plan (Item 1 below) is
correct and the implementer's own reasoning for it holds up under direct empirical check. Scope
discipline is real: sector coverage (Decision 2a) is genuinely untouched, `plans/binocular-optic/
plan.md` is untouched, both new constants are documented as starting values at their definition,
and Fix C's change is exactly the one-line move the diagnosis identified — nothing wider.

One required fix: a stale/wrong doc comment in `decay.py` that still describes the superseded
"elapsed since it started failing" field semantics and references a field name
(`Contact.unobservable_since_sim`) that was never implemented — the actual field is
`last_observable_sim` with inverted semantics ("time last confirmed observable", not "time it
started failing"). This is exactly the mechanism the implementer got right elsewhere in the same
commit; the one place documenting *why* the constant means what it means still describes the
wrong (and empirically broken) mechanism.

### Required Fixes

- **`body-layer/src/belief/decay.py`, `CALLOUT_OBSERVABILITY_GRACE_S`'s docstring (lines ~112-127)
  still says "based on `Contact.unobservable_since_sim` tracking how long the mask check has
  failed *continuously*"** — that field was never built. The actual field, `Contact.
  last_observable_sim` (`contacts.py`), tracks the opposite thing: the time the contact was *last
  confirmed observable*, not how long it has been failing. I confirmed by direct experiment that
  the "elapsed since it started failing" model this docstring describes is actually broken (it
  passes the committed defect test `test_range_crossing_does_not_fire_for_a_contact_behind_the_
  cockpit_mask` at t=0 but fails it at t=1, exactly the "one full grace window regardless" bug
  `implementation.md`'s own "Notable Discoveries" section describes and fixes). So this is not a
  cosmetic naming slip — it's the single authoritative place documenting the constant's meaning,
  and it currently describes a mechanism that was tried, found wrong, and replaced, without being
  updated to say so. A future reader (or agent) tuning this constant would reason from the wrong
  model. Fix: update the docstring to name `last_observable_sim` and describe "grace since last
  confirmed observable, not since first unobservable" — matching `_callout_may_speak`'s own
  docstring in `contacts.py`, which already gets this right.

### Optional Refinements

- `test_logger.py`'s two new tests (`test_follow_already_on_target_does_not_lower_the_binoculars`,
  `test_follow_off_target_still_lowers_the_binoculars`) reproduce `_run_crew_text_poll_loop`'s
  `already_on_target` conditional inline rather than exercising the real loop function. This
  matches the file's own established pattern (`test_a_player_command_lowers_the_binoculars` does
  the same, with the same "reproduces the exact conditional... rather than checking as two
  unrelated facts" framing) — not a new gap introduced here, but worth naming: a future edit to
  the real conditional in `logger.py` that isn't mirrored in these three tests would go undetected
  by all three simultaneously. Not blocking; this is the same tradeoff the codebase already made
  and lives with.
- `plan.md`'s own Stage 1 prose (the historical planning document, not live code) still describes
  the superseded `unobservable_since_sim` field-name/semantics. Leaving a plan's own text as
  originally written is the project's convention when a decision is superseded elsewhere (same
  pattern as `plans/binocular-optic/plan.md` D4/D5, explicitly preserved per `decisions.md`'s own
  framing) — no action needed, noted only so it isn't confused with the `decay.py` issue above,
  which is live code, not a decision record.

### Scrutiny items — verified

1. **The `last_observable_sim` deviation from the plan's literal `unobservable_since_sim` formula
   is correct, and I verified it empirically, not just by reading the argument.** I patched a
   literal implementation of the plan's prose (an "elapsed since the mask check started failing"
   field, reset on success, checked against `now_sim - failing_since < GRACE`) into a scratch copy
   of `contacts.py` and reran the two range-crossing tests: `test_range_crossing_still_fires_
   within_the_observability_grace_window` still passed (coincidentally — both models agree on the
   "recently seen, briefly masked" case), but `test_range_crossing_does_not_fire_for_a_contact_
   behind_the_cockpit_mask` **failed** — the naive model grants a full grace window to a contact
   masked continuously since founding, exactly reproducing the sortie's reported symptom the fix
   exists to close. The implementer's `last_observable_sim` (`None` = never confirmed observable,
   denying grace unconditionally) is what makes both tests pass together. The plan was wrong on
   this point; the implementer caught it correctly and documented why in `implementation.md`.
   - A contact never observed: denied grace unconditionally — confirmed (`None` check in
     `_callout_may_speak`).
   - A contact observed once then briefly occluded: gets grace, loses it after the window —
     confirmed by the grace-window test and by reading the `< CALLOUT_OBSERVABILITY_GRACE_S`
     comparison.
   - `last_observable_sim` is updated on **every** tick `ownship` is passed, for every contact
     (not gated on watch/attention) — confirmed by reading `tick()`: `observable_or_grace` is
     computed unconditionally per contact right after the cardinality block, before the
     watched-only sixth block even checks attention. The sole production caller (`logger.py`
     line 515) always passes `ownship`. So the field is refreshed everywhere it should be, not
     only on some paths — the failure mode the task brief specifically flagged as most likely
     did not occur here.

2. **The two modified pre-existing tests preserve their original intent**, and the added `is_
   worth_a_look` defensive check is real but genuinely unreachable from `decide()`. Both
   `TestEveryContactInTheConeIsAttempted` assertions and `test_a_look_is_not_ended_by_its_own_
   attempt_marking` now check `pending_attempted_at_range_m` in place of `attempted_at_range_m` —
   a direct, mechanical consequence of the committed/pending split (the mark simply lives
   somewhere else now), not a weakening: each test's own docstring-stated invariant ("a look
   marks all the contacts it covers the instant it starts", "starting a look and continuing one
   are different questions") still holds and is still what's asserted. I confirmed the
   `pending_attempted_at_range_m` membership check inside `is_worth_a_look` is not reached by
   `decide()`'s own control flow — `decide()` only calls `is_worth_a_look` from the `SCANNING`
   branch, never mid-`GLASSING` (its own stop condition is `look_is_finished`) — but it *is*
   directly reached by `test_a_look_is_not_ended_by_its_own_attempt_marking`, which calls `is_
   worth_a_look` standalone against a `GLASSING` state to pin the invariant. So the "defensive,
   no live behavioural effect" framing in `implementation.md` is accurate for production code
   paths, and the test that exercises it directly is legitimate, not decorative.

3. **Fix A's gate placement is correct**: it gates unobservability (cockpit mask against current
   true bearing), not gaze-cone membership. Confirmed by reading `_callout_may_speak` (uses
   `perception.cockpit_mask.is_visible`, never `perception.gaze`/`within_gaze`/
   `FOCUS_CONE_HALF_WIDTH_DEG`) and by reading `plans/callout-outside-gaze/debug.md`'s shipped
   scenario (a contact at 10 o'clock during a commanded `scan right`, which is well inside the
   cockpit mask's forward visibility and would not be caught by this gate) — that fix's wording
   still carries the entire burden of the "recently watched, currently looked-elsewhere" case, and
   Fix A does not regress it. The gate sits entirely inside `ContactStore.tick`'s spontaneous path
   (fifth/sixth blocks); `route_event`/`_render_lifecycle_text` gained no visibility parameter, so
   the pull-only answering path Decision 3 reserves for later (`describe_contact`/`render_contact_
   report`) is structurally untouched — confirmed by grep, no calls into the gate from either.
   `CONTACT_MOTION_CHANGED`'s wider (unwatched) reach has its own dedicated test
   (`test_motion_changed_does_not_fire_for_an_unwatched_contact_behind_the_cockpit_mask`), per
   Decision 4.2's explicit requirement.

4. **Fix C's scope matches the diagnosis exactly.** The only functional change in `crew_console.py`
   is moving `self._note_player_command()` from unconditional to inside `if parse.disposition ==
   "handled":` — confirmed by diff, nothing else in the dispatch logic changed. The `follow`
   already-on-target carve-out reads `CrewConsole.last_command_target_contact_id` (reset at the top
   of every `handle_command` dispatch, set only by `_handle_follow`) against `OpticState.
   look_contact_id` (the look's chosen centre, set at the SCANNING→GLASSING transition, cleared by
   `_back_to_scanning`), confined to the single `lower_binoculars` call site in `logger.py`'s "any
   command lowers binoculars" glue block — no other `lower_binoculars` call site (e.g. the
   manoeuvring/not-steady interruption inside `decide()` itself) was touched. The "re-judge, don't
   assume" claim checks out: once `already_on_target` is false and binoculars are lowered, nothing
   in the changed code path pre-selects an optic — the existing `SCANNING`→`choose_look`/`is_
   worth_a_look` cycle is genuinely what re-decides, confirmed by reading `decide()`'s unchanged
   scan-to-glassing transition logic; no new code was needed there and none was added.

5. **Scope discipline confirmed**: `git diff main...f1feb5b -- plans/binocular-optic/plan.md`
   is empty (untouched). No `choose_look` changes anywhere in the diff — sector coverage
   (Decision 2a) is not present even partially. Both `CALLOUT_OBSERVABILITY_GRACE_S` and
   `OPTIC_RETRY_INTERVAL_S` are documented at their definition as starting values pending a flown
   sortie, per Decision 4.3.

### Verification

Ran from a temporary checkout of `f1feb5b`'s `body-layer/` files into this worktree (using the
main checkout's existing `body-layer/.venv`, since this worktree has none), then reverted cleanly
before finishing:

- `ruff format --check src tests` — 111 files already formatted, pass
- `ruff check src tests` — all checks passed
- `mypy src` (run from `body-layer/`, per the CWD-only config-discovery trap) — Success: no issues
  found in 52 source files
- `pytest tests -q` — **1303 passed, 4 xfailed**, matching the implementer's report exactly. I did
  not independently re-run the `main`-baseline count (1292/4) — that figure comes from
  `diagnosis.md`, a separately-authored document produced before implementation began, which I
  treat as adequate provenance for the baseline rather than re-deriving it.
- Empirically confirmed (Item 1 above) that the primary defect test would fail under the plan's
  literal `unobservable_since_sim` formula, and that the grace-window companion test does not by
  itself distinguish the two models (both pass it) — the discriminating test is the original
  committed defect test, not the new companion.

No worktree-pythonpath trap encountered (ran with `cd body-layer && mypy src` / `pytest tests`,
not from repo root); no `.venv` existed in this worktree, so the main checkout's `.venv` was used
directly against the worktree's checked-out sources, which is safe for these read-only checks.

### Verdict
APPROVED WITH MINOR FIXES

The one required fix is a documentation-only correction (no behavioural change, no new test
needed) — update `decay.py`'s `CALLOUT_OBSERVABILITY_GRACE_S` docstring to name the actual field
(`last_observable_sim`) and its actual semantics (grace since last confirmed observable), matching
`_callout_may_speak`'s own docstring in `contacts.py`. Everything else — the deliberate plan
deviation, the two modified pre-existing tests, Fix A's gate placement and scope, Fix C's
narrowness, and scope discipline around sector coverage — checks out under direct verification,
not just the implementer's account of it.

### Review Confidence
Full read. All five changed source files and all new/modified tests were read in full; the
deliberate-deviation claim (the most consequential item) was verified empirically, not just by
argument; format/lint/type/test commands were run directly rather than trusted from the report.
