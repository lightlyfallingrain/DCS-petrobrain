### Implementation Summary

Implements `plans/attack-run-los/plan.md` in full: F2's `tier`-keyed loss/regain register (fixing
the reported "eyes on fired with no fresh look" bug), Decision 2's `terrain_blocked_held` flag
(holding a genuine `"obstructed"` verdict's consequence across its own freshness-window staleness),
and F3's "where is it?" voice-only query command (Decision 1: answerable whenever a target is
selected, whether or not a run is engaged; Decision 3: voice only, no typed-console path).

**Security plan review waived by the user, 2026-10-24** ("skip the security in the attack run plan,
go to implement"), recorded here per the dispatching instruction rather than a separate Security
agent run.

### Files Changed
- `body-layer/src/belief/attack_run.py` — redefined `AttackRunState.last_spoken_unresolved`'s
  baseline from `cause == "too_far"` to `tier != 1` (F2); added `AttackRunState.
  terrain_blocked_held: bool = False` and its per-tick update rule (Decision 2); factored the
  shared cause/tier/alignment/qualifier computation out of `decide()` into a new `_Alignment`
  dataclass + `_current_alignment()` helper (also computes Decision 2's `effective_cause`
  substitution); `decide()` now branches the losing-sight edge three ways
  (`too_far`/`obstructed`/`unknown`, the last falling through silently per Decision 2); added
  `query()` (F3) — a pure function reusing `_current_alignment`, never writing `state`. Updated the
  module's and several functions'/fields' docstrings to describe the new semantics (not a comment
  sweep — only the blocks this change actually touches).
- `body-layer/src/belief/speech.py` — new `render_attack_run_behind_terrain` ("Behind the ridge,
  &lt;phrase&gt;.") and `render_no_target` ("No target."); updated `render_attack_run_regained_sight`'s
  docstring for the new not-sighted→sighted framing.
- `body-layer/src/belief/crew_console.py` — new `where_is_it_requested: bool = False` field + its
  reset in `handle_command`; new `_handle_where_is_it` (sets the flag, returns `[]`); `"where_is_it"`
  added to `DISPATCHED_COMMAND_TOKENS` and `NO_RETURN_VALUE_COMMAND_TOKENS`; new
  `drain_where_is_it(attack_run_state, now_sim, ownship, *, resolving_optic=None)` — Decision 1's
  "target set, not run engaged" gate, with a throwaway `AttackRunState` constructed for the
  unengaged case.
- `body-layer/src/logger.py` — poll loop calls `crew_console.drain_where_is_it(...)` immediately
  after `drain_attack_run`, with the same `runner.attack_run_state`/`runner.last_ownship_state`/
  `runner.optic` already in scope there, and clears `where_is_it_requested` afterward.
- `audio-adapter/src/vocabulary.py` — new `"where_is_it"` token in `VOICE_ONLY_TOKENS` (Decision 3:
  no F10 equivalent, by construction) and three phrasings in `PHRASES`
  (`"where is it"`/`"where is target"`/`"where is it now"` — no filler article, per this module's
  own "what this speaker actually says" rule, which the pinned
  `test_no_phrasing_carries_a_filler_article` test caught when I first wrote "where is the target").
- `body-layer/tests/test_attack_run.py` — see "Tests Added" and "Notable Discoveries" below; five
  **existing** tests had to be updated (not just extended) because the plan's own F2/Decision 2
  behaviour change makes their old pinned assertions describe the bug being fixed.
- `body-layer/tests/test_crew_console.py`, `body-layer/tests/test_logger.py` — new tests, below.
- `body-layer/ROADMAP/BL-B76.md` — added a dated note (2026-10-24) per the plan's "Amending open
  plans" section: this plan answers the register half of BL-B76's open step 3, narrower than that
  step framed it, and Decision 2 adds a mitigation that narrows but does not close BL-B76's own
  open question (step 2's mountainous-sortie measurement is unchanged and still necessary).

### Existing tests updated (plan's test-impact hypothesis was wrong for these five)

The plan's step 1 said running the existing suite "alone should not break any passing test... since
every existing test that exercises regaining_sight/losing_sight does so via genuine tier-1/tier-2
transitions." Running it found five failures, all for the same reason: several existing tests
constructed their tier-2 scenarios either with `_contact_at` (a helper whose own docstring says it
**forces tier 2 regardless of range**, built for `_no_look_cause` tests, not transition-register
tests) or by letting a tier-1 percept go briefly stale while a fresh `"obstructed"` verdict was
present — both now exercise the *exact* mechanism F2 fixes, so their old assertions describe the
pre-fix (buggy) behaviour:

- `test_decide_falls_through_to_tier_2_once_the_relative_observation_goes_stale` — the tier-1→tier-2
  edge with a fresh `"obstructed"` cause now speaks `"Behind the ridge, a little lower."` (Decision
  2), not the old `"A little lower, obstructed."` (which now speaks one tick later, since its text
  differs from the transition line — see below).
- `test_decide_tier_transition_speaks_the_qualifier_without_flipping_direction` — same edge,
  `"Behind the ridge, right."` first; the ordinary qualified phrase `"Right, obstructed."` follows
  one tick later (new text, so it still emits once before truly steady); regaining sight now speaks
  `"Eyes on, a bit right."` not the bare phrase.
- `test_decide_lined_up_tier_transition_speaks_once_each_way` — same shape, `"lined up"` wording.
- `test_decide_losing_and_regaining_sight_keys_on_resolvability_not_masking` — its final step
  ("turning back in, now within acquisition range -- eyes on, once") was the bug itself: range alone,
  with no percept ever set (`_contact_at`), used to (wrongly) regain sight under the old `cause`-
  keyed register. Rewritten so the regain step uses a genuine tier-1 look, which is what F2 now
  requires; the masked-break portion (never reaching tier 1) is unchanged.
- `test_decide_retarget_resets_last_spoken_unresolved` — `contact_b` was "within range" but
  carried no percept (`_contact_at`, tier 2 forced); under F2 a tier-2-only contact is *never*
  "resolved," so this would read `last_spoken_unresolved is True` regardless of whether the reset
  worked, which no longer distinguishes the thing the test claims to test. Gave `contact_b` a
  genuine tier-1 look instead.

Each of these is a **deliberate, specification-driven update** — the new assertions describe exactly
the behaviour `plans/attack-run-los/plan.md`'s F2/Decision 2 sections specify, not a workaround for
an unrelated failure. Confirmed via this entry's own mutation runs (below) that the updated tests
still fail under the mutations that would reintroduce the bug.

I also found one test the plan's test-impact list did not name, in the other direction (not a
phantom — a mismatch the plan simply didn't anticipate): `audio-adapter/tests/test_vocabulary.py`'s
`test_no_phrasing_carries_a_filler_article` rejected my first `"where is the target"` phrasing;
fixed by using `"where is target"` instead (no modification to the test itself).

### Tests Added
- `test_decide_f2_repro_no_eyes_on_after_a_long_unresolved_occlusion` — the exact F2 reproduction:
  sighted → genuine `"too_far"` episode → masked → unmask a minute later with `cause == "unknown"`
  (no live LOS verdict ever recorded) → no "Eyes on". Mutation-confirmed (see below).
- `test_decide_masked_then_obstructed_on_unmask_speaks_behind_the_ridge_once` — Decision 2's option
  C: sighted → masked → unmask with a fresh `"obstructed"` verdict → `"Behind the ridge, ..."` once,
  `terrain_blocked_held` `True` afterward.
- `test_decide_sighted_then_too_far_still_speaks_the_full_remembered_claim` — regression guard: F2
  changes the register's keying, not the `"too_far"` wording.
- `test_decide_terrain_blocked_held_survives_the_obstructed_verdicts_own_staleness` — Decision 2's
  own case: the held flag keeps the `", obstructed"` qualifier alive through several `"unknown"`
  ticks after the verdict itself has aged out. Mutation-confirmed.
- `test_decide_terrain_blocked_held_clears_on_a_live_look` — the hold does not survive a genuine
  tier-1 look.
- `test_decide_terrain_blocked_held_resets_on_retarget` — a new target's hold starts `False` even
  though the old target's was `True`.
- `test_query_never_mutates_the_state_it_is_given` — F3's purity guarantee, checked by value
  equality against the original.
- `test_query_renders_the_steady_state_phrase_for_each_effective_cause` — all four effective causes
  (`too_far`/`unknown`/`masked`/`obstructed`, plus held-`unknown`), and confirms no transition
  wording ever appears in a query answer.
- `test_where_is_it_with_no_target_selected_says_no_target` — Decision 1's "No target." case.
- `test_where_is_it_with_target_selected_but_no_engaged_run_answers_the_guidance` — Decision 1's own
  reproduction: answers from a throwaway state rather than refusing.
- `test_where_is_it_with_an_engaged_run_reuses_the_live_state` — confirms the engaged-run path
  passes the *live* `AttackRunState` through (proven via a non-default `terrain_blocked_held=True`
  the throwaway path could not have produced).
- `test_crew_text_poll_loop_drains_where_is_it_with_an_engaged_run` /
  `test_crew_text_poll_loop_drains_where_is_it_with_no_engaged_run` — the real poll-loop wiring
  (mirroring the existing `resolving_optic` wiring test's harness shape exactly): `drain_where_is_it`
  is called with whatever `runner.attack_run_state` is, `None` included, and the flag clears so it
  does not re-fire on the next poll.

### Checks

**body-layer/**
- ruff format --check: pass (174 files)
- ruff check: pass
- mypy src (and tools): pass (84 source files)
- pytest -q: pass (2663 passed, 4 xfailed; was 2650 passed, 4 xfailed before this feature)

**audio-adapter/**
- ruff format --check: pass (31 files)
- ruff check: pass
- mypy src: pass (16 source files)
- pytest -q: pass (349 passed, 2 skipped)

**Live mutation runs** (restored by checksum after each, `shasum` verified):
- Reverted `now_unresolved = tier != 1` to `cause == "too_far"` → 8 tests failed, including the F2
  repro test and three of the five updated pre-existing tests.
- Reverted the `effective_cause` substitution to plain `cause` → 2 tests failed (the held-staleness
  test and the `query` steady-state test).

### Command map

`python3 .claude/scripts/command-map-check.py` reports the map STALE (`not on the map: where_is_it`)
— expected, since the vocabulary changed. Per the task brief this is the main loop's job to redraw
(`/command-map`), not mine.

### Notable Discoveries
- The plan's own test-impact assessment ("this alone should not break any passing test") was wrong
  for five existing tests, all for the identical reason: a helper (`_contact_at`) or a scenario built
  for a different purpose happened to exercise the exact tier-2-without-a-genuine-look mechanism F2
  exists to fix. None of this is a defect in the plan's design — it is the plan's own fix correctly
  invalidating assertions that pinned the pre-fix behaviour. Flagged per the role's "treat the test-
  impact list as a hypothesis" instruction rather than silently working around it.
- A transition sentence (`"Behind the ridge, ..."`/`"Eyes on, ..."`) and the ordinary steady-state
  qualified phrase for the identical cause are different texts, so `_should_emit`'s text-equality
  veto lets the *next* tick after a transition speak once more (a new text) before truly settling
  into silence. This already existed for the `"too_far"` transition before this plan (visible in
  `test_decide_losing_and_regaining_sight_keys_on_resolvability_not_masking`'s own pre-existing
  `speech3`); this plan's `"obstructed"` transition inherits the same shape. Worth knowing for anyone
  reading a sortie's speech log and wondering why an "obstructed" episode produces two lines close
  together rather than one.
