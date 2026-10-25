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
