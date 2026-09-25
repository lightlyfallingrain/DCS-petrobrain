### Debug Report

**2026-09-25, `body-layer`, branch `fix/scan-is-not-watch`.** Two linked live
defects reported by the user flying `main` (`7aeaa8e`), building on
`plans/callout-outside-gaze/debug.md`'s finding that the "ground 10 o'clock,
2 km" callout was `CONTACT_RANGE_CROSSED`, a watched-only report, not a gaze
defect. This session answers the question that investigation left open: why
was an unwatched contact treated as watched at all.

### Observed Issue

User, flying `main`: *"Such automatic updates should be for watched units.
These were not watched, just scan results. For watched units it's signal,
for non-watched noise. Same goes for the moving/stopped. Also, moving/
stopped seems to fire for units out of sight, that should not happen."*

Two symptoms: (1) unprompted `CONTACT_MOTION_CHANGED`/`CONTACT_RANGE_CROSSED`/
`CONTACT_ENGAGEMENT_CHANGED` callouts for contacts the player only `scan`ned,
never deliberately watched; (2) motion ("moving"/"stopped") callouts for
contacts not currently in sight.

### Hypothesis

**Defect 1 (root cause).** `belief/tools.py::scan_area` registered a
`"watch"`-level `belief.attention.AttentionArea` (`store.add_area(...,
level="watch", source="scan_area", ...)`) -- literally the same level
`watch_area`'s own default produces. `belief/attention.py::effective_attention`
then returns `"watch"` for any contact geometrically inside that area,
independent of whether the player ever issued a deliberate watch. Every
consumer of "is this contact watched" (`belief/callouts.py`'s
`_WATCHED_ONLY_KINDS` gate, and `ContactStore.tick`'s own `is_watched` check
that gates `CONTACT_RANGE_CROSSED`/`CONTACT_ENGAGEMENT_CHANGED` at emission)
reads this same derived value, with no way to distinguish "the player asked
Petrovich to look here" from "the player asked Petrovich to keep reporting
on this."

**Defect 2.** No second, independent code defect was found. `CONTACT_
MOTION_CHANGED`'s state (`Contact.motion.state`) can only ever change via
`belief.motion.fold_motion`, which runs exclusively from `Contact.record`
during `ContactStore.ingest` -- i.e. only when a fresh naked-eye percept
carrying `apparent_motion` arrives. `perception/naked_eye_source.py::poll`
only computes `apparent_motion` for candidates that already passed `check_
visibility`'s Gate 0 (`within_gaze`) *that same poll* (`motion_by_object_id`
is built only from the `visible` list). `ContactStore.tick` runs in the
same call, at the same `now_sim`, as `ingest` (`logger.py`'s poll loop), and
`Contact.last_emitted_motion` is unconditionally kept in sync with `Contact.
motion.state` every tick (`contacts.py` line 1033, outside the cooldown-gated
`if`), so a transition can never be "queued" past a poll where it wasn't
actually witnessed. Structurally, `CONTACT_MOTION_CHANGED` cannot fire for a
contact that was not in gaze at the instant of the transition.

Given that, Defect 2 as observed live is fully explained by Defect 1: with
`scan_area` conferring `"watch"`, motion callouts became eligible for
*every* contact the scan swept up, not only contacts the player deliberately
watched. Because the scan cone cycles through several o'clock legs
(`perception/gaze.py`'s `_SECTOR_LEGS`), and because a callout can be
spoken up to `CALLOUT_MAX_AGE_S` (10s) after its underlying event, a motion
event witnessed on one leg could be spoken several seconds later while gaze
had already moved to a different leg entirely -- reading as "fires for
units out of sight" even though the transition itself was genuinely
witnessed. No separate freshness bug exists in the motion block itself.

### Evidence

1. **`belief/tools.py::scan_area`'s own (now-corrected) docstring**
   explicitly said "the same call `watch_area` makes," confirming the two
   commands shared one attention level by design, not accident.
2. **Dependency check before choosing the fix.** Grepped every other
   consumer of `AttentionArea.level`:
   - `belief/tasks.py` (`TaskStore`, scan-task completion) reads only
     `area_contains` -- never `.level`.
   - `logger.py::_active_gaze` (gaze steering for a commanded scan) reads
     only `relative_sector`/`relative_clock_hour`/`sector` -- never
     `.level`.
   So `.level` had exactly one behavioural consumer:
   `belief.attention.effective_attention`, read only by the callout/report
   family. Changing `scan_area`'s level cannot affect scan-task success or
   gaze steering.
3. **Reproduced Defect 1 directly** with a scratch script (`ContactStore` +
   `TaskStore` + `scan_area`): before the fix, a contact whose
   `last_position` fell inside a `scan_area`-registered area reported
   `effective_attention == ("watch", "AREA_1")`, exactly like a real
   `watch_area`/`watch_contact` mark.
4. **`_observation`'s existing test-fixture docstring in `test_callouts.py`
   was already wrong/stale** (claimed `dwp_x`/`dwp_z` drive `Contact.
   last_position` "entirely independently" of enrichment) -- confirmed by
   reading `belief/percept.py::percept_of`, which structurally strips
   `Observation.derived_world_position` before it ever reaches `belief/`
   code (the no-omniscience boundary). Actual `last_position` comes from
   the observation's `bearing_deg`/`range_m` projected from `ownship_at_
   observation`. This was caught only by empirically printing `Contact.
   last_position` after ingest -- the existing `test_watched_contact_
   speaks_a_range_crossing` test still passed despite this because its
   inline km-value comments were also wrong and its assertion never
   actually checked the numeric range, only the rendered text (which is
   identical for `CONTACT_DETECTED` and `CONTACT_RANGE_CROSSED` on an
   unenriched contact). Not touched -- out of this debug's scope, but
   worth a reviewer's attention if that test file is touched again.
5. **`CONTACT_RANGE_CROSSED`/`CONTACT_ENGAGEMENT_CHANGED` are gated at
   *emission*** (`ContactStore.tick`'s sixth/seventh blocks, both under
   `is_watched`) -- an unwatched contact never gets the event appended to
   `store.events` at all. `CONTACT_MOTION_CHANGED` is gated only at the
   *speech* layer (`belief/callouts.py`'s `_WATCHED_ONLY_KINDS`) -- the
   underlying event is always logged, regardless of watched status, and
   only speaking it is suppressed. This asymmetry is pre-existing,
   documented design (both modules' own docstrings), not something this
   fix changes; it just meant the two families needed slightly different
   regression-test shapes (see Verification).

### Fix Applied

`belief/tools.py::scan_area` now registers its `AttentionArea` at
`level="normal"` instead of `level="watch"`. `watch_area` (and everything
built on it -- `watch_contact_task`/`watch nearest`/`follow`) is untouched;
it still defaults to `level="watch"` and is the only path that can raise a
contact into the watched-only reporting family. `scan_area`'s docstring is
updated to state the decision and why it is safe (the two non-`.level`
consumers checked in Evidence #2).

No fix was made for a "Defect 2 mechanism" separate from Defect 1, because
none was found -- see Hypothesis. A regression test locks in that a
genuinely watched contact's motion state cannot spuriously "re-fire" purely
from elapsed sim time with no new evidence (it already couldn't; this pins
it).

### Verification

- `body-layer` baseline before this change: 1266 passed / 4 xfailed
  (`main` @ `7aeaa8e`).
- New/updated tests in `body-layer/tests/test_tools.py` and
  `body-layer/tests/test_callouts.py`:
  - `test_scan_area_registers_a_normal_level_area_and_a_pending_task`
    (renamed/updated from `..._registers_a_watch_area_...`, which pinned
    the old, now-reversed, behaviour -- this is the one test that encoded
    Defect 1's own bug as a passing assertion. Renaming it required no
    escalation: the user's own words in this task's brief already settled
    the design question ("for watched units it's signal, for non-watched
    noise"), so this isn't an ambiguous call, it's applying an explicit,
    already-made decision).
  - `test_scanned_but_unwatched_contact_never_speaks_a_motion_change`
  - `test_scanned_but_unwatched_contact_never_speaks_a_range_crossing`
  - `test_watched_contact_motion_stays_silent_while_out_of_sight`
  - All four confirmed to **fail against the pre-fix code** (`level=
    "watch"`, tested by temporarily reverting the one-line change and
    re-running) and **pass against the fix**.
  - `watch nearest`/`follow`/`watch-area` are unaffected by construction
    (they call `watch_area`/`watch_contact_task`, never `scan_area`) --
    confirmed by grep: `store.add_area` has exactly two call sites,
    `tools.watch_area` and `tools.scan_area`.
- Full suite after the fix: **1269 passed / 4 xfailed** (net +3 tests, 0
  regressions).
- `ruff format --check body-layer/src body-layer/tests`: pass (one file
  auto-reformatted during development, re-verified clean).
- `ruff check body-layer/src body-layer/tests`: `All checks passed!`
- `mypy body-layer/src` (run as `cd body-layer && mypy src`, per
  `body-layer/CLAUDE.md`'s CWD-only config-discovery note): `Success: no
  issues found in 51 source files`.

### What was not changed, and why

- **`CONTACT_RANGE_CROSSED`'s wording** (no lead/event_clause,
  indistinguishable from a live sighting) -- left to the user per the prior
  debug session's recommendation; this fix does not touch `belief/
  speech.py`. Fixing Defect 1 substantially narrows when that ambiguity can
  even arise (only for genuinely watched contacts now), but does not
  resolve it -- the user should decide separately whether a distinguishing
  lead is still wanted for a truly watched contact reported from memory.
- **No gaze-gating was added anywhere.** Per this task's brief and the
  prior investigation, gating these events on *current* gaze would be
  wrong -- it would silence a legitimate "closing on something you told me
  to watch" report the moment the player looks away, which is the entire
  point of `watch_area`/`watch_contact`.
- **No freshness/certainty gate was added to `CONTACT_MOTION_CHANGED`'s
  emission**, unlike `CONTACT_RANGE_CROSSED`'s explicit `fresh = certainty_
  of(...) in ("observed", "tracked")` check. Evidence #2 above shows this
  isn't needed: a motion *state change* is structurally impossible without
  a contemporaneous percept, so there is nothing stale to guard against --
  adding a redundant gate would be unmotivated defensive code with no
  reproducing failure behind it.
