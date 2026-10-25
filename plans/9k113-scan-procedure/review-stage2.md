### Review Summary

BL-B89 Stage 2 (`look`/`sight`/`what is [at] <where>`, the explicit 9K113 request) reviewed
against `plan-stage2.md`, `explore-notes.md`'s verbatim decisions, and `security-plan-stage2.md`'s
"Passed to Reviewer" list. Reviewed at tip `0ab8965581a348762c1d0a40363ca044addebc9c` (6 commits on
`feature/9k113-scan-procedure`, diff `8f5d2ade..0ab89655`).

Scope, vocabulary design, OBSERV gating, the confirm-band reuse, attack-run refusal, the
`relative`-vs-bounded asymmetry, and the compass-wedge geometry all match the plan and the user's
verbatim decisions. `ruff format --check`, `ruff check`, `mypy src` (strict, run from inside each
subproject) and `pytest` are clean in both `audio-adapter` (357 passed, 2 skipped) and `body-layer`
(2611 passed, 4 xfailed) — run once, normally; the coordinator corrected the brief that
`pytest-randomly` is installed in `body-layer`'s venv (it is not, only an empty leftover
`__pycache__`), so no `-p no:randomly` comparison was run or needed, and no order-dependent failure
was observed.

One required fix was found by mutation-testing the Co-moving Fields concern the plan itself flags
as a risk area ("two deferred-queue shapes... worth a `grep` sanity check") — not in the field
itself (which is correctly threaded through every construction site touched), but in how
`body.py` applies a transition signal that happens to share a field (`OpticState.look_started_sim`)
with two unrelated mechanisms.

### Required Fixes

1. **`body.py`'s `point_request_transition` apply block clobbers an unrelated, in-progress sight
   look, silently abandoning the contact and leaking a pending-forever mark.**

   `body.py` (around the "Supersession" apply block, right after `drain_pending_point_request`/
   `_poll_transcripts`):

   ```python
   if crew_console.point_request_transition is not None:
       transition = crew_console.point_request_transition
       runner.optic_state = replace(
           runner.optic_state,
           bounded_look=(None if transition == "clear" else transition),
           look_started_sim=None,   # <-- unconditional
       )
       crew_console.point_request_transition = None
   ```

   `point_request_transition` is set to `"clear"` for **every** token in
   `_POINT_LOOK_SUPERSEDING_TOKENS` — not just `look`/`scan`, but also `select_target`, `follow`,
   `watch_nearest(_air_defence)`, `engage`, `disengage`, `drop_target`, `step`,
   `cancel_task`/`cancel_scan`/`cancel_watch` — set unconditionally at the top of
   `handle_command`, before dispatch, regardless of whether a `bounded_look` was ever running.
   The apply block above then resets `look_started_sim=None` on `runner.optic_state` every time
   any of those fires, with no check that a bounded look was actually involved.

   `look_started_sim` is not a private field of the bounded-look mechanism — it is also the
   **sight's own per-target look clock** (`_decide_sighting`'s `look_contact_id` mid-look
   continuation check: `if state.look_contact_id is not None and state.look_started_sim is not
   None:`) and the **idle 3-leg search cycle's own leg clock** (`_idle_sight_search`'s docstring:
   "`look_started_sim` reused as the per-leg clock... exactly the mechanism `GLASSING`/`SEARCHING`
   already use"). Resetting it to `None` for an unrelated command silently breaks the first of
   these. Demonstrated directly against `optic_policy._decide_sighting` (not inferred):

   ```
   === normal mid-look poll (no unrelated command fires) ===
     look_contact_id after: c1
     pending_attempted_at_range_m: {'c1': 3000.0}
     decision.optic: sight_narrow        # look continues correctly

   === pilot says "follow"/"select_target"/"engage"/... while the sight is
       mid-look at contact c1 (unrelated to any look/scan command) ===
     look_contact_id after: None          # <-- the look was silently abandoned
     pending_attempted_at_range_m: {'c1': 3000.0}   # <-- never committed, never cleared
     decision.optic: sight_wide           # fell back to idle search
   ```

   Root cause, traced through the real code: with `look_started_sim` forced to `None`, the
   "continue the existing mid-look sweep" branch's second condition
   (`state.look_started_sim is not None`) fails even though `look_contact_id` is still set. Control
   falls through to `choose_sighting_look` re-evaluating candidates from scratch. `is_worth_a_look`
   excludes contact `c1` because it is already in `pending_attempted_at_range_m` — this is the
   exact trap `_decide_sighting`'s own comment warns about ("must not re-run `is_worth_a_look` on
   this contact first... which would make every look vanish after its first poll"), triggered here
   by a different path than the one that comment was written against. The contact is dropped with
   no target chosen, `look_contact_id` becomes `None`, and the `pending_attempted_at_range_m` entry
   is **never committed and never cleared** until the next full OBSERV off→on cycle (`_back_to_
   home`'s `replace()` is the only thing that resets it) — until then, `c1` reads as "a look
   already in progress" and is silently excluded from every future look, so it can never improve
   past its current classification level.

   This is reachable in ordinary play: OBSERV on, the sight mid-look at a real contact, and the
   pilot says almost any other command — `follow`, `select_target`, `watch_nearest`, `engage`,
   `disengage`, `step`, `cancel_task`, or any `scan`/`look` phrase. None of this is exercised by
   the new tests: every `test_a_new_scan_command_supersedes_a_running_point_request`-style test
   only asserts `CrewConsole.point_request_transition`'s *value*, never applies it the way `body.py`
   does against a concurrently active, unrelated sight look — the gap the plan's own "Risks &
   Unknowns" flagged generically ("worth a `grep` sanity check that `drain_pending_point_request`
   is wired in") but did not specifically name.

   **Fix**: only reset `look_started_sim` when the transition actually concerns the bounded-look
   clock — i.e. when `runner.optic_state.bounded_look is not None` before the change, or the new
   `transition` is a `BoundedSightLook` (a fresh bounded look starting). Something like:

   ```python
   if crew_console.point_request_transition is not None:
       transition = crew_console.point_request_transition
       new_bounded_look = None if transition == "clear" else transition
       reset_clock = (
           runner.optic_state.bounded_look is not None or new_bounded_look is not None
       )
       runner.optic_state = replace(
           runner.optic_state,
           bounded_look=new_bounded_look,
           look_started_sim=(
               None if reset_clock else runner.optic_state.look_started_sim
           ),
       )
       crew_console.point_request_transition = None
   ```

   Add a test exercising the apply block (or `_decide_sighting` directly, as above) with a
   superseding token fired while an unrelated, in-progress contact look is active, asserting
   `look_contact_id`/`pending_attempted_at_range_m` are unaffected.

### Optional Refinements

- **The `point`-verb fuzzy match admits several unrelated common words at full confidence**:
  `"book"`/`"cook"`/`"hook"`/`"took"` (ratio 0.75 against `"look"`) and `"fight"`/`"sighted"`
  (ratio 0.8/0.73 against `"sight"`) all clear `VERB_FLOOR` (0.5) and dispatch `point` outright when
  paired with a `where`-word (e.g. `"fight two o'clock"` → `point`, `clock=2`, ratio 1.0). This is
  the same VERB_FLOOR tradeoff already accepted for `follow`/`report`/`walk`→`look`, extended to two
  new, shorter, more collision-prone words — unlike `"walk"`/`"skin"`, these two were not checked
  against `tools/stt_bench.py`'s own corpus before shipping. Given push-to-talk discipline this is
  low-risk, but worth a corpus pass before the vocabulary grows further around `"look"`/`"sight"`.
- **A bare `"look"`/`"sight"` with no slot does reach the generic phrase table and resolves to
  `point`/`slots=None`** (ratio 1.0, via the `PHRASES["point"] = ("look", "sight")` calibration
  entry) — the implementation notes' claim that this entry is "never reached by the generic phrase
  table in practice since the dedicated branch below always resolves first" is not quite right for
  this one case (the dedicated branch returns `None` on no slot and falls through by design). The
  behavioural outcome is still correct (`_handle_point` already degrades `slots=None` to "say
  again"), so this is a documentation nit, not a functional issue.
- The redundant `point_request_transition = "clear"` write on a `look` command refused for
  `ATTACK_RUN_ENGAGED` (set at the top of `handle_command` before the refusal fires in
  `_handle_point`) was traced and confirmed harmless: `bounded_look` is already `None` by the time
  `attack_run_engaged` can be `True`, because every path that sets `attack_run_transition`
  (`engage`/`disengage`) is itself in `_POINT_LOOK_SUPERSEDING_TOKENS` and already clears it on
  entry. Not a correctness issue, just worth noting since the test suite doesn't assert it directly.

### Review Confidence

Full read of the diff (all 6 commits), the plan, explore-notes, and the security plan review.
Mutation-tested two of the new tests (`test_two_sweeps_then_clear_and_resume`,
`test_two_where_slots_is_a_detected_error`) against the real code — both caught the intended
mutation. Ran adversarial transcripts against the real matcher (`match_transcript`), not just the
plan's own worked examples. Traced the Required Fix above against the real `_decide_sighting`
function with concrete before/after state, not inferred from reading alone. Did not independently
re-derive the compass-wedge 45° geometry's trigonometry beyond checking it against the existing
30°/o'clock derivation the plan cites — low risk, single new helper, already has its own direct
test per the plan's own instruction.

### Verdict

CHANGES REQUESTED

### Re-review

Re-reviewed the fix commit `627ab398b074b308f90ba4ec023edb765ecdd25e` (parent `d0b58959`, this
review's own CHANGES REQUESTED tip) on `feature/9k113-scan-procedure`, against
`implementation-stage2.md`'s "Review fixes" section and `plan-stage2.md`.

**Required Fix 1 — resolved.** `body.py` now has a named helper,
`_apply_point_request_transition(optic_state, transition)`, extracted from the inline apply block
in `_run_crew_text_poll_loop` and used at its sole call site. It implements exactly the guard this
review sketched: `reset_clock = optic_state.bounded_look is not None or new_bounded_look is not
None`, and `look_started_sim` is only reset when `reset_clock` is true. `grep -n
point_request_transition src/body.py` confirms there is exactly one place in `body.py` that writes
`look_started_sim` via this transition (the helper itself) and exactly one call site — no second,
unguarded write was left behind.

**Confirmed by mutation, not just reading.** Reverted the helper's body to the pre-fix
unconditional `look_started_sim=None` and re-ran the new test
(`test_an_unrelated_superseding_command_does_not_abandon_a_running_look`): it goes red with the
exact symptom this review's own repro showed (`assert None == 'CONTACT_1'` on `look_contact_id`
after the second `decide()` poll). Restored the file; `git diff` against the restored file shows no
difference, confirming the restore was exact. The new test also calls
`body_module._apply_point_request_transition` directly, the same function the poll loop calls, not
a reimplementation of its logic — so the regression test is wired to the real code path, not to a
parallel assertion that could drift from it.

**Remaining write sites.** `grep -n look_started_sim src/body.py` returns three lines: the
docstring, the one conditional write inside the helper, and a comment referencing the helper. There
is no other place in `body.py` that writes this field from the point-request path.

**Bounded-look teardown on supersession, checked by direct construction against the real
dataclasses (not inferred):**
- **A new look/scan superseding a running bounded look** (`transition` is a fresh
  `BoundedSightLook` while `optic_state.bounded_look` was already set): `reset_clock` is true via
  either disjunct, `look_started_sim` is reset to `None`, `bounded_look` becomes the new wedge —
  correct, the new look starts its own clock from the next poll rather than inheriting the stale
  value.
- **`cancel`/`cancel_scan` clearing a running bounded look** (`transition == "clear"`,
  `bounded_look` was set): `reset_clock` is true via the first disjunct, both fields clear
  together — correct.
- **OBSERV off** does not go through `_apply_point_request_transition` at all — it is a distinct
  mechanism (`CrewConsole.observ_transition`, applied separately in the poll loop, driving `decide`
  into a phase transition that reaches `optic_policy`'s `_back_to_home`, which clears
  `look_started_sim`/`look_contact_id`/`bounded_look` together in its own `replace()`). That path is
  unchanged by this fix and already covered by
  `test_observ_off_command_stops_the_sight_through_the_real_poll_loop`, which this re-review re-ran
  and confirms still passes with `look_contact_id is None` after the transition.
- **The fix's own case** (an unrelated superseding token with no bounded look running): confirmed
  `look_started_sim` is left untouched, reproducing the new test's own assertion from a hand-built
  `OpticState`.

All three mutation checks above (new bounded look, cancel, no-bounded-look) were run against the
real `_apply_point_request_transition` with real `BoundedSightLook`/`OpticState` instances, not
read off the diff.

**Comment pruning.** The removed comment lines ("`'clear'` and a fresh `BoundedSightLook` both just
`replace()` the field — the latter *is* the start of a new bounded look, the plan's own 'clear then
start' collapsing to one write") described the pre-fix behaviour, which the fix itself changes; no
dated line, verbatim user quote, or measurement was among what was removed, and the replacement
text points to the new helper's own docstring, which carries the fuller explanation (including the
`look_started_sim` reasoning) that used to live only in the review and the implementation notes. No
boundary case moved into a test and vanished — the one boundary case this fix is about shipped with
the new test in the same commit.

**Optional refinements.** Both left as-is, matching the review's own conclusions:
`VERB_FLOOR`'s "book"/"fight" collisions need a corpus measurement (`tools/stt_bench.py`), not a
code change — not acted on, correctly deferred rather than guessed at; the `PHRASES["point"]`
documentation claim was corrected in `implementation-stage2.md` itself (no source change needed,
behaviour was already correct); the harmless redundant `point_request_transition = "clear"` write
under `ATTACK_RUN_ENGAGED` was left untouched, as the review itself concluded it should be. Nothing
here required a change.

**Checks, run from `body-layer/`:** `ruff format --check src tests` — 173 files already formatted.
`ruff check src tests` — all checks passed. `mypy src` — success, no issues in 74 source files,
strict. `pytest -q` — 2612 passed, 4 xfailed (one run hit a single, non-reproducing failure in
`test_mission_start_reset.py::test_check_for_new_mission_keeps_the_traceback_for_a_non_connection_failure`,
unrelated to anything this commit touches; it passed in isolation and on two subsequent full runs,
so treated as a pre-existing order-sensitive flake rather than a regression from this fix). The fix
commit touches only `body-layer` (`git diff --stat d0b58959 627ab398`), so no `audio-adapter`
commands were re-run for this pass.

### Re-review Verdict

APPROVED

### Re-review Confidence

Full read of the fix commit's diff (`body.py`, `test_body.py`, `implementation-stage2.md`).
Mutation-confirmed the regression test against the real pre-fix code, with an exact-restore check.
Independently constructed and ran all three teardown scenarios (new bounded look, cancel,
no-bounded-look) against the real dataclasses rather than inferring correctness from the guard
expression alone. Did not re-verify the OBSERV-off path's own internals beyond re-running its
existing test, since that path is untouched by this commit.
