### Implementation Summary

Implements the four-stage plan in `plans/sortie-2026-09-26-fixes/plan.md` against
`decisions.md`'s binding spec: an observability gate on spontaneous callouts (Fix A), an
interrupted binocular look no longer burning the retry budget (Fix B1), time-based
re-eligibility alongside the existing range-based retry (Fix B2), and command-dependent
binocular lowering (Fix C). Sector coverage (Decision 2a) is confirmed out of scope, per the
user's own sizing answer, and not touched.

### Files Changed

- `body-layer/src/belief/decay.py` — new `CALLOUT_OBSERVABILITY_GRACE_S = 10.0` constant,
  explicitly documented as a starting value pending a flown sortie, not a measurement.
- `body-layer/src/belief/contacts.py` (Fix A) — `Contact` gains `last_observable_sim: float |
  None`; new `_callout_may_speak(contact, ownship, now_sim)` helper computes the contact's
  current true bearing via `perception.geometry.body_relative_direction` and gates it through
  `perception.cockpit_mask.is_visible` (the same primitive `perception.visibility` uses at
  detection time — deliberately not the gaze cone, per Decision 1). `ContactStore.tick`'s fifth
  block (`CONTACT_MOTION_CHANGED`) and sixth block (`CONTACT_RANGE_CROSSED`) both gate emission
  on this (computed once per contact per tick, reused by both blocks); block six's "governs the
  event and the `last_announced_range_km` update" rule mirrors the existing `fresh` gate's shape.
  `ownship is None` (every pre-existing caller) leaves the gate a true no-op.
- `body-layer/src/belief/optic_policy.py` (Fix B1/B2/C) — `OpticState` gains
  `pending_attempted_at_range_m` (uncommitted look-in-progress marks), `attempted_at_time_sim`
  (Fix B2's time-of-attempt twin), and `look_contact_id` (Fix C's chosen-target tracking). The
  SCANNING→GLASSING transition now writes into `pending_attempted_at_range_m`, not
  `attempted_at_range_m` directly. `decide`'s `GLASSING` branch splits `not steady`
  (interruption — drops the pending map via `_back_to_scanning`) from `look_is_finished` (natural
  end — commits pending into the two committed maps, then calls `_back_to_scanning`).
  `lower_binoculars` reaches the same drop path unchanged, which is the actual Fix B1 mechanism.
  `is_worth_a_look` gains a `now_sim: float = 0.0` parameter (default keeps every pre-existing
  call site unaffected) and an `OPTIC_RETRY_INTERVAL_S` (`4 * SCAN_CYCLE_PERIOD_S ≈ 64s`,
  explicitly a starting value) time-based branch alongside the existing range check — either
  suffices. Also added a `pending_attempted_at_range_m` check to `is_worth_a_look` to preserve a
  pinned invariant (see Notable Discoveries).
- `body-layer/src/belief/crew_console.py` (Fix C) — `_handle_utterance`'s `_note_player_command()`
  call moved from unconditional to inside the `if parse.disposition == "handled":` branch,
  fixing the actual bug (an unparseable `fallthrough` no longer burns the interrupt).
  `CrewConsole` gains `last_command_target_contact_id: str | None`, reset at the top of every
  `handle_command` dispatch and set by `_handle_follow` when it resolves a target.
- `body-layer/src/logger.py` (Fix C) — the "any command lowers binoculars" glue block gains an
  `already_on_target` check: if the just-dispatched command's target equals the current look's
  `look_contact_id` while still `GLASSING`, `lower_binoculars` is skipped.

### Tests Added

- `test_contacts.py::test_range_crossing_still_fires_within_the_observability_grace_window` —
  a contact confirmed observable once, then masked for 1s (< grace), still gets its crossing.
- `test_contacts_motion.py::test_motion_changed_does_not_fire_for_an_unwatched_contact_behind_the_cockpit_mask`
  — Decision 4.2's unwatched-case coverage requirement.
- `test_optic_policy.py::test_time_based_reeligibility_fires_for_a_naturally_completed_look_on_a_stalled_contact`
  — Fix B2's own companion test (a completed look, constant range, eventually re-eligible).
- `test_crew_console.py`: `test_an_unrecognised_utterance_does_not_burn_the_optic_interrupt`,
  `test_say_again_does_not_burn_the_optic_interrupt` (regression guard), `test_follow_records_its_resolved_target`,
  `test_follow_target_resets_between_unrelated_commands`.
- `test_logger.py`: `test_follow_already_on_target_does_not_lower_the_binoculars`,
  `test_follow_off_target_still_lowers_the_binoculars` — both reproduce `_run_crew_text_poll_loop`'s
  exact conditional, mirroring the existing `test_a_player_command_lowers_the_binoculars` pattern.
- The two already-committed failing tests (`test_contacts.py::test_range_crossing_does_not_fire_for_a_contact_behind_the_cockpit_mask`,
  `test_optic_policy.py::test_a_command_interrupted_look_is_not_permanently_burned`) now pass.
- Two pre-existing tests updated (not rewritten in substance — see Notable Discoveries):
  `test_optic_policy.py::TestEveryContactInTheConeIsAttempted` (both tests) and
  `test_a_look_is_not_ended_by_its_own_attempt_marking` now check `pending_attempted_at_range_m`
  instead of `attempted_at_range_m`, since the Stage 2 committed/pending split moved what an
  in-progress look's marks live in.

### Checks (body-layer/)

- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src` (`cd body-layer && mypy src`): pass, no issues in 52 source files
- `pytest -q`: 1303 passed, 4 xfailed (baseline on `main` was 1292 passed, 4 xfailed — 11 new
  tests, no regressions)

### Notable Discoveries

- **The `CALLOUT_OBSERVABILITY_GRACE_S` field needed different semantics than "duration since it
  started failing" (mirroring `los_masked_since_sim`) to make the committed cockpit-mask test
  pass.** A literal reading of the plan's own prose ("`unobservable_since_sim` tracks how long the
  mask check has failed continuously... may fire only while `now_sim - unobservable_since_sim <
  GRACE`") means a contact that has *never once* been confirmed observable would still get a full
  grace window's worth of callouts starting from its very first evaluated tick (elapsed always
  starts at 0). The committed test (`test_range_crossing_does_not_fire_for_a_contact_behind_the_
  cockpit_mask`) places a contact permanently astern from founding and expects immediate,
  permanent suppression — which only works if grace requires having been genuinely observable at
  least once. Implemented as `last_observable_sim: float | None` (time of *last confirmed
  observable*, not time a failing run started) — `None` means "never confirmed observable," which
  denies grace unconditionally. Added a companion test proving the *other* half: a contact
  observed once, then masked for less than the grace window, still gets its callout. Both
  behaviors are now pinned; flagging this because it is a real refinement beyond the plan's
  literal field-semantics description, not a deviation from its intent.
- **Two pre-existing `test_optic_policy.py` tests asserted `state.attempted_at_range_m` is
  populated immediately when a look starts** — exactly the field Stage 2's pending/committed
  split moves that immediate mark out of. This is a direct, mechanical consequence of the plan's
  own design (not a scope change), so I updated the two assertions to check
  `pending_attempted_at_range_m` instead, preserving each test's original intent
  ("a look marks all the contacts it covers the instant it starts") rather than rewriting their
  logic. A third test (`test_a_look_is_not_ended_by_its_own_attempt_marking`) additionally needed
  `is_worth_a_look` itself to gain a `pending_attempted_at_range_m` membership check (a contact a
  look is actively covering right now is not worth *starting a second* look over) to keep its
  pinned invariant true — `decide()` never actually reaches this branch mid-`GLASSING` in the real
  control flow (its own stop condition is `look_is_finished`, not `is_worth_a_look`), so this is a
  defensive addition with no live behavioral effect, not a functional change.
- **"Whose job is whose" lens (root `CLAUDE.md`, added mid-task, `4e6d916`), applied to this
  feature's open judgment calls**: none required a design change.
  - Fix A's 10s grace window: a briefly-occluded contact still matters to a pilot deciding
    whether to evade/attack; a permanently-astern one (now correctly suppressed via
    `last_observable_sim`) does not — the discovery above actually *strengthens* this alignment,
    since the literal plan-prose reading would have granted grace to contacts the pilot never
    had a real look at.
  - `CONTACT_MOTION_CHANGED`'s wider (unwatched) reach: a pilot deciding whether to evade or
    attack benefits from knowing an unwatched contact started moving just as much as a watched
    one — suppressing it only when genuinely unobservable (not merely unwatched) is the right
    scope.
  - `follow <target>` re-judging binoculars rather than assuming: needed no new code (the
    existing `SCANNING`→`choose_look`/`is_worth_a_look` cycle already re-evaluates from scratch),
    and correctly serves "identifying what is out there is the point of asking."
- Both constants (`CALLOUT_OBSERVABILITY_GRACE_S = 10.0`, `OPTIC_RETRY_INTERVAL_S ≈ 64s`) are
  documented at their definition as starting values to tune against a flown sortie, per Decision
  4.3.
