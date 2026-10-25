### Implementation Summary

BL-B89 Stage 2 — `look`/`sight`/`what is [at] <where>`, the explicit 9K113
request, on top of Stage 1's sector scan — built against
`plans/9k113-scan-procedure/plan-stage2.md` and `explore-notes.md`'s
verbatim decisions, security-reviewed (APPROVED,
`security-plan-stage2.md`).

**One deliberate, flagged deviation from the plan's own band-shape
description**, called out up front so Reviewer/DoD do not have to find it:
the plan's "The sweep itself" section describes the no-distance-given case
as covering the wedge's own full `SIGHT_SEARCH_NEAR_M`–`SIGHT_SEARCH_WIDE_FAR_M`
reach in **one continuous near-to-far sweep** of the sight's own S-shape.
What is actually built generates that reach as **one `search_pattern` call**
(`body._sight_point_sweep`), stepped through by a new, self-contained
`_advance_bounded_look` in `optic_policy.py` — this *is* what the plan asked
for; I do not believe there is a divergence here after all (re-checked while
writing this summary: `_sight_point_sweep` passes `near_m=bounded_look.near_m,
far_m=bounded_look.far_m` straight to `search_pattern`, which already derives
its own row count/S-shape from `fov_full_width_deg` vs. the depression spread,
exactly the mechanism Stage 1 already proved). Recorded anyway because I
spent real effort convincing myself of it and a reviewer would otherwise have
to re-derive the same thing.

**One genuine simplification, not flagged as equivalent**: a bounded look
interrupted mid-sweep by a found contact resumes the *current* traversal
from its own first step, not the exact step it was on (`_advance_bounded_
look`'s own docstring: "a deliberately simpler 'resume' than the idle
cycle's own leg-position tracking"). `sweeps_completed` is never lost or
double-counted by this — only the within-sweep step position is. The plan's
own correctness requirement ("a found contact does not consume a sweep")
holds; "resumes at the exact same step" was never a stated requirement.

### Files Changed

**audio-adapter:**
- `src/vocabulary.py` — new `point` token; `PHRASES["scan_ahead"/"scan_left"/
  "scan_right"]` lose their `"look ..."` phrasings (look is no longer a scan
  alias); `PHRASES["point"] = ("look", "sight")` added as a calibration-only
  entry (reaches `VERB_ANCHOR_WORDS`/`to_prompt()`). **Correction
  (review-stage2.md, Optional Refinements):** this entry *is* reached by the
  generic phrase table for a bare `"look"`/`"sight"` with no slot — the
  dedicated branch returns `None` on no slot by design and falls through to
  it, resolving to `point`/`slots=None` at ratio 1.0. The outcome is still
  correct (`_handle_point` degrades `slots=None` to "say again"), so this
  was a documentation nit, not a functional issue.
- `src/command_matcher.py` — `_POINT_VERBS`/`_WHAT_VERB`, `_parse_point_
  slots`, and two new slot-resolution branches in `match_transcript` (point
  verbs, then `"what"`), ordered with the existing `follow`/`report`/
  `select_target`/`step`/`engage`/`greeting` branches, before the generic
  phrase table.
- `tests/test_command_matcher.py` — `TestPointSlots` (8 cases); `test_walk_
  ahead_matches_end_to_end` updated to its new, intended resolution (see
  "Notable Discoveries").

**body-layer:**
- `src/perception/gaze.py` — `compass_wedge_body_relative`/`COMPASS_SECTOR_
  HALF_WIDTH_DEG` (45°, the compass-point reading of the same spacing
  `FOCUS_CONE_HALF_WIDTH_DEG` already gives the o'clock reading), and
  `clock_wedge_body_relative`, a public wrapper over the existing private
  `_gaze_for_clock_hour`.
- `src/belief/optic_policy.py` — `BoundedSightLook`, `OpticState.
  bounded_look`/`point_clear_label`, `_advance_bounded_look`, a new hook in
  `_decide_sighting`'s idle branch (checked before `_idle_sight_search`), a
  new `sight_point_search` parameter threaded through `decide`/`_decide_
  without_guidance`/`_decide_sighting`, and `_back_to_home`'s OBSERV-off
  branch now clears `bounded_look`. New tunables `POINT_SWEEP_COUNT` (2),
  `POINT_READY_TIMEOUT_S` (5.0 s), `POINT_DISTANCE_BAND_HALF_KM` (1.0 km).
- `src/belief/speech.py` — `render_point_readback` (the "Two o'clock."
  acknowledgement, deliberately not `render_scan_readback`'s "Scanning
  ..." wording); new `render_unable` reason `ATTACK_RUN_ENGAGED`.
- `src/belief/voice_commands.py` — `PendingConfirmation.observ_request`,
  the third mutually-exclusive confirm payload.
- `src/belief/crew_console.py` — `PendingPointRequest`; `CrewConsole.
  attack_run_engaged`/`sight_phase_is_sighting`/`pending_point_request`/
  `pending_point_clear`/`point_request_transition` fields; `_point_slots_
  label`/`_start_point`/`_handle_point`; `drain_pending_point_request`/
  `drain_pending_point_clear`; `_handle_scan` gained an optional `readback_
  text` override (so `_start_point`'s `relative` branch can reuse its task
  registration with the point-style readback instead of `render_scan_
  readback`'s); the OBSERV-off confirm affirm branch in `handle_transcript`
  gained the `observ_request`/`"observ on"`-also-counts-as-yes case;
  `_POINT_LOOK_SUPERSEDING_TOKENS` and the top-of-`handle_command` check
  that sets `point_request_transition = "clear"` for every member; `"point"`
  added to `_LOOK_COMMAND_TOKENS` (on-ground refusal) and `DISPATCHED_
  COMMAND_TOKENS`.
- `src/body.py` — `_sight_point_sweep` (the `_sight_in_regard_sweep` sibling
  driven by a `BoundedSightLook` directly); `decide_optic`'s call site in
  `run_once` gains `sight_point_search=_sight_point_sweep(self.optic_state.
  bounded_look, ownship)`; the poll loop gains `point_clear_label`
  forwarding (right after `run_once()`), two new drains (`drain_pending_
  point_clear`/`drain_pending_point_request`, alongside the existing three),
  `crew_console.attack_run_engaged`/`sight_phase_is_sighting` refresh
  (alongside `on_ground`), and the `point_request_transition` application
  block (right after the existing `lower_binoculars` glue, since both are
  keyed off a command having just been dispatched or a deferred drain
  having fired this poll).
- `config/defaults.toml` — regenerated (`tools/generate_defaults.py
  --write`); gains the three new tunables' rows.

### Tests Added

- `audio-adapter/tests/test_command_matcher.py::TestPointSlots` — clock,
  clock+distance, `"what is at"`, `"what do you see"` unaffected, `look
  left/right/ahead` → `relative`, `scan left` unaffected, two-where-slot
  detected error, compass sector.
- `body-layer/tests/test_optic_policy.py::TestBoundedSightLook` — pre-empts
  the idle cycle; two sweeps then clear-and-resume; a found contact mid-sweep
  does not consume a sweep; OBSERV off clears `bounded_look`; an empty step
  list falls back without announcing.
- `body-layer/tests/test_body.py::TestSightPointSweep` — `None` is empty; a
  forward wedge sweeps within its own bounds; a wedge wholly outside the
  sight's field of regard is empty.
- `body-layer/tests/test_crew_console.py` — 16 new tests: clock/relative/
  compass dispatch, distance narrowing, attack-run refusal, the full
  OBSERV-off confirm round trip (yes / no / "observ on" / guidance-not-
  ready), `drain_pending_point_request`'s wait-for-both-flags gate,
  `drain_pending_point_clear`, and supersession (a new scan/cancel clears a
  running point request; `silence`/`report` do not).

### Checks

**audio-adapter/:**
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (from `audio-adapter/`): pass, 16 source files
- `pytest tests -q`: pass, 357 passed, 2 skipped

**body-layer/:**
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (from `body-layer/`): pass, 74 source files
- `pytest tests -q`: pass, 2611 passed, 4 xfailed (run with `-p no:randomly`
  — see "Notable Discoveries" for why that flag matters here)

### Mock transcript (real `CrewConsole` output, not illustrative)

Produced by calling the actual `handle_command`/`handle_transcript`/
`drain_pending_point_*` methods, not hand-written:

```
> look left                          (OBSERV on, enrichment configured)
  Left.
> scan left                          (unaffected -- still its own verb)
  Scanning left.

> look two o'clock                   (OBSERV on)
  Two o'clock.
  ... two empty sweeps later ...
  Two o'clock, clear.

> look two o'clock, three kilometres (OBSERV on)
  Two o'clock.
  (band narrows to 2.0-4.0 km instead of 1.5-8.0 km)

> look two o'clock                   (OBSERV off)
  Need observ, confirm?
> yes
  Observ on.
  (deferred look starts once home_phase reaches SIGHTING)

> look two o'clock                   (OBSERV off)
  Need observ, confirm?
> no
  (silent -- no acknowledgement, per task item 3)

> look two o'clock                   (attack run engaged)
  Unable, attack run.

> look two o'clock                   (OBSERV on; a bounded look starts)
  Two o'clock.
> scan left                          (supersedes it)
  Scanning left.
  (point_request_transition now "clear" -- body.py drops bounded_look)
```

### Notable Discoveries

- **`"look ahead"` removal collides with an existing pinned mishearing
  test.** `test_walk_ahead_matches_end_to_end` pinned `"walk ahead"` (a
  measured mishearing, `ratio("walk","look")=0.5`) resolving to `scan_ahead`
  via the *old* `"look ahead"` phrasing on that token. Removing that phrasing
  (per the plan, explicit and approved) makes `"walk ahead"` now anchor
  `point`'s own verb branch at the identical `VERB_FLOOR` and resolve to
  `point`/`relative="ahead"` instead — the *intended* consequence of `look`
  no longer aliasing `scan`, not a regression, but not named in the plan's
  own Tests section either. Updated the test to the new resolution and
  explained why in its docstring, per the role's "treat the test-impact list
  as a hypothesis" instruction — this is exactly the "missing entry" class
  that instruction warns is the dangerous one.
- **`_start_point` originally required `self.enrichment` even for the clock
  case**, which needs no heading at all (the o'clock wedge is already
  body-relative). Found while writing `test_drain_pending_point_request_
  waits_for_sighting_phase`, which has no enrichment configured. Fixed by
  moving the enrichment check inside the `sector` (compass) branch only.
- **A pre-existing test-order-dependent flake**, unrelated to this feature:
  `test_mission_start_reset.py::test_check_for_new_mission_keeps_the_
  traceback_for_a_non_connection_failure` fails under `pytest-randomly`'s
  default shuffled order (passes alone, passes with `-p no:randomly`) —
  looks like `caplog` state leaking across tests depending on run order.
  Did not investigate further (out of this feature's scope); flagging so
  it is not mistaken for something this change broke.
- **`DISPATCHED_COMMAND_TOKENS`'s own regression-guard test** (`test_
  dispatched_command_tokens_all_return_something`) exercises every token
  with `slots=None` — `point` needed to degrade to `render_say_again()`
  for that case, which `_handle_point`'s existing `slots is None` branch
  already does; no change needed there, just confirmed it by running the
  test before writing anything new.
- **The relative/bounded asymmetry, re-confirmed by implementation**:
  `look left` genuinely needs no new state at all — `_start_point`'s
  `relative` branch is a direct call into `_handle_scan` (Stage 1's own
  mechanism), with only the readback text substituted. The entire new
  `BoundedSightLook`/`point_request_transition` machinery exists only for
  the `clock`/`sector` (compass) case. A future reviewer tempted to
  "unify" the two paths should re-read the plan's own flagged risk on this
  point before doing so.

### Review fixes (review-stage2.md)

**Required Fix 1 — fixed.** `body.py`'s `point_request_transition` apply
block reset `OpticState.look_started_sim = None` unconditionally, for
every `_POINT_LOOK_SUPERSEDING_TOKENS` entry, even when no bounded look
was ever active. Because `look_started_sim` is shared with the sight's own
per-target look clock (`_decide_sighting`'s mid-look continuation check)
and the idle 3-leg search cycle's per-leg clock, this silently abandoned a
real, unrelated, in-progress contact look and leaked its `pending_
attempted_at_range_m` entry — reachable from almost any other command
(`follow`, `select_target`, `watch_nearest`, `engage`, `disengage`,
`step`, `cancel_task`, any `scan`/`look` phrase) fired while the sight was
mid-look.

**Fix, as sketched in the review**: the apply block is now a named helper,
`body._apply_point_request_transition`, applying the review's own guard —
`look_started_sim` is reset only when the transition actually concerns the
bounded-look clock (a bounded look was running before the change, or the
new transition is a fresh `BoundedSightLook` starting one); otherwise it
is left untouched. Extracted into its own function (previously inline in
`_run_crew_text_poll_loop`) specifically so it is unit-testable without
driving the whole poll loop.

**Test added first, confirmed red, then fixed** (`test_body.py::
test_an_unrelated_superseding_command_does_not_abandon_a_running_look`):
starts a real mid-look via `decide()` (same starting point as `test_
optic_policy.py`'s `test_the_look_survives_past_the_poll_that_started_
it`), applies an unrelated superseding `"clear"` transition the way the
poll loop does, then runs `decide()` again and asserts the look continues
onto the same contact. Verified red against the pre-fix (unconditional
reset) body of the helper — `AssertionError: assert None == 'CONTACT_1'`
— then restored the fix (checksum-verified identical to the pre-break
source) and confirmed green.

**Optional Refinements — left as-is, with reasons:**

- **The "book"/"fight"-class fuzzy collisions** (`audio-adapter/src/
  command_matcher.py`'s `VERB_FLOOR = 0.5`): not tightened. `VERB_FLOOR` is
  one global floor shared by every verb, including the two collisions it
  was deliberately set to admit (`"skin"`→`scan` and `"walk"`→`look`, both
  exactly 0.5, per that constant's own docstring/provenance). There is no
  per-verb floor to narrow without either introducing a new, unplanned
  per-word threshold table (an architectural change, not the "small and
  consistent with matcher precedent" the review conditioned this on) or
  running `tools/stt_bench.py`'s corpus to see whether "book"/"fight" are
  actually produced for "look"/"sight" in practice — a measurement task,
  not an implementation one. Given push-to-talk discipline this is
  low-risk per the review's own read; flagging for a dedicated corpus pass
  rather than guessing at a fix here.
- **The `PHRASES["point"]` documentation claim**: fixed directly in this
  implementation notes file (the inaccurate claim lived here, not in
  source) — see the "Files Changed" entry above for the correction. No
  source change needed; the behavioural outcome was already correct.
- **The redundant `point_request_transition = "clear"` write under
  `ATTACK_RUN_ENGAGED`**: left as-is per the review's own conclusion — confirmed
  harmless, not a correctness issue, no test or source change requested.
