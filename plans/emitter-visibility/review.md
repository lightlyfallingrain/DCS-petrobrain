### Review Summary

Reviewed `feature/emitter-visibility` @ `94a8f29` (Stage A of `BL-B72`/`AC-B7`: the shared gate
bypass, the burning-unit emitter, its transport). Rebuilt both subprojects' venvs from scratch
(pinned versions per the dispatch) and ran format/lint/type/test myself rather than trusting the
implementer's report; every number matched. Read the full plan, the acceptance document, both
roadmap entries, the implementer's own account, and the diff across all 23 changed files. Mutation-
tested the one guard the dispatch asked me to mutate (the group-salience non-interaction pin) and
found it does not actually catch the regression it is supposed to pin.

The gate chain, tier clamp, wording, Lua transport and tuning constant are all correct and well
tested. Two things need to change before this merges: the truth-boundary test weakening, and the
group-salience non-interaction test's actual coverage.

---

### Required Fixes

**1. `test_percept_has_no_truth_carrying_field` must not have `"provenance"` removed from its
forbidden set — fix the design, not the guard.**

The plan is explicit: *"No schema change to `Observation`, `Percept` or `Contact`."*
(`plans/emitter-visibility/plan.md`, "Provenance rides on a field that already exists"). The shipped
code breaks that promise in both places the plan named: `Percept` gained a new `provenance: str |
None` field, and `Contact` gained two (`is_burning`, `last_emitted_burning`). The plan's own design
turned out to be infeasible — `Contact.record` only ever sees a `Percept`, never the raw
`Observation`, so if `Contact` needs to learn "this report came from the emitter bypass" at all,
*something* has to cross that was not crossing before. That part of the implementer's reasoning is
correct and I agree the plan under-specified this.

What is not correct is the fix chosen: rather than add a narrow, bounded signal, the implementer let
the *existing, free-form* `Observation.provenance: str` field cross wholesale, and widened the
central no-omniscience guard test to stop objecting to it.

Judging it on the merits the dispatch asked for:

- **Is `provenance` genuinely channel-self-description, or can it carry anything derived from ground
  truth?** Today, yes, it is self-description — every value is a project-chosen enum-like string
  (`PROVENANCE_VISIBILITY_FILTER_ONLY`, `PROVENANCE_EMITTER_BURNING`, and `hybrid_source.py`'s
  `"petrovich_indication+world_objects[/ambiguous_association]"`). But the *field's declared type* is
  a bare `str`, not a closed enum, and nothing enforces that discipline. `hybrid_source.py`'s value
  already names an internal pipeline detail (`ambiguous_association`) that has nothing to do with
  what a crewman perceived — it describes the *system's own uncertainty bookkeeping*. That is a
  milder version of exactly the thing the test exists to keep out, and it is already riding this
  field. Opening the field to `Percept` makes every future producer of `Observation.provenance` a
  silent producer of `Percept.provenance` too, with no further check.
- **Does the forbidden set exist to block truth, or to block anything that crosses the boundary?**
  The test's own docstring: *"`Percept` must lack every DCS-truth field `Observation` carries, so no
  downstream `belief/` function can read one by accident."* `t_wall` and `contact_id` are not DCS
  ground truth either — they are internal bookkeeping forbidden from crossing for the same reason
  `derived_world_position` is: belief must only ever see what was *perceived*, and an internal
  system detail is not a perception. `provenance`-as-currently-written is closer to
  `classification_level`/`count_bucket` (I agree with the implementer there), but the test's own
  stated purpose is broader than "DCS ground truth" alone — it also catches unperceived internal
  signal in general, which is precisely the risk a free-form string carries forward.
- **Is there a design that gets `Contact.is_burning` without widening the set at all?** Yes, cheaply.
  `visibility.VisibilityResult.emitter_kind` and `DetectionTrace.emitter_kind` already exist as a
  narrow, bounded signal (an `EmitterKind.value` string or `None`) computed purely from gate-bypass
  outcome. Add `Percept.emitter_kind: str | None = None` instead of `Percept.provenance`, populated
  by `percept_of()` from `observation.provenance` via the existing
  `_PROVENANCE_BY_EMITTER_KIND`-style mapping (or simply pass the already-resolved `emitter_kind`
  through `Observation` itself, parallel to how `count_bucket` already rides the cluster-level fold).
  `Contact.is_burning` becomes `percept.emitter_kind == EmitterKind.BURNING.value`. This is the same
  size of change — one field, one assignment site, same tests — but it is a *closed, purpose-built*
  signal rather than a passthrough of an open-ended string, so `test_percept_has_no_truth_carrying_
  field`'s set does not need touching at all. `Observation.provenance` itself never has to cross the
  boundary.
- **What now stops a future field being added to `provenance` that is truth-derived, if the change
  ships as written?** Nothing. The test that existed to make "does this field carry something
  `Percept` shouldn't see" a structural question, checked by introspection, has had its one defence
  against this exact field removed. The next producer of `Observation.provenance` (`BL-B73`'s
  `targets_ownship` wording, or a future channel) has no mechanical check stopping it from folding in
  something richer — the discipline is now a comment in a test file, not a guard. A boundary that
  moved once to accommodate a feature moves again the next time a feature finds it inconvenient,
  unless the narrower design above is taken instead.

This is substantial enough that I considered escalating per the "existing tests must be rewritten"
rule, but the implementer already flagged it explicitly for Reviewer judgment per their own role
instructions, which is the right place for this to land — so I'm resolving it here as a required fix
rather than bouncing it back to the user first. Recommended fix: revert the `test_percept.py`
change, add `Percept.emitter_kind` (or equivalent narrow field) instead of `Percept.provenance`, and
rewire `Contact.is_burning`/`record`/`from_percept` off that.

**2. The `group_salient_ids`-before-visibility non-interaction test does not pin what it claims to.**

`test_emitter_does_not_widen_group_salience_for_a_non_emitting_neighbour`
(`test_naked_eye_source.py`) places both units at 9 km, which is beyond even `group_salience.py`'s
loosened `RESOLUTION_ANGULAR_RADIUS_RAD` threshold (~5469 m for a 7 m vehicle). I mutation-tested
this directly: patching `naked_eye_source.py` so that `salient_ids` is widened by `emitter_by_
object_id`'s ids, and separately so that *any* emitter present marks every candidate in the whole
poll `group_salient=True` (the actual shape of the regression the plan's Risks section warns about —
"one AAA gun makes a whole convoy visible") — **the full test suite still passes, unchanged, under
both mutations.** The test's two units are far enough out that group-salience relaxation makes no
observable difference for either one, so the test cannot distinguish "the leak the plan worried
about" from "no leak at all." It currently passes only because the code is structurally correct
(`group_salient_ids(candidates, observer, UNAIDED_OPTIC)` has no `emitter` parameter at all — verified
by reading the call site), not because the test would catch a regression that broke that structural
guarantee.

Fix: add a healthy, non-burning neighbour positioned between `RESOLUTION_ANGULAR_RADIUS_RAD`'s and
`LOWRES_ANGULAR_RADIUS_RAD`'s thresholds (the window group-salience relaxation actually opens, ~5.4–
9.3 km for a 7 m vehicle) alongside a burning unit, and assert the neighbour is still *not* reported.
That range window is exactly where the current test's units are not, which is why the mutation
passed silently.

---

### Optional Refinements

- `plans/forest-occlusion/plan.md`'s Risks note that this merge needs a numbered `Decision N
  REVISED` sub-decision recorded there once merged — not blocking the review, but flag it for DoD/
  merge so it doesn't get lost (the plan says "at merge," and this isn't merged yet).
- `implementation.md`'s note 2 (the `PROVENANCE_EMITTER_BURNING` constant's real home being
  `naked_eye_source.py`, not `source.py` as the plan named) is a reasonable, well-documented
  deviation and needs no further action — leaving it as a discovered correction for `BL-B73`/`BL-B74`
  to follow is fine.

---

### Verdict

**NEEDS REVISION** — two required fixes, both scoped and contained: narrow the field crossing the
truth boundary instead of widening the guard test, and strengthen the group-salience non-interaction
test to a range window where it would actually fail if the structural guarantee were broken. Neither
touches Stage A's core mechanism (the gate chain, tier clamp, wording, or Lua transport), all of which
checked out clean on direct reading, independent test execution, and (for the one guard the dispatch
asked me to mutate) mutation testing.

Per the project's re-entry rule, this goes back to Implementer for the fix, then Reviewer again on
the fix, before DoD.

---

### Review Confidence

Full read of the plan, acceptance document, both roadmap entries, implementer's account, and the
full diff (23 files). Independently rebuilt both subprojects' venvs and ran `ruff format --check`,
`ruff check`, `mypy --strict` (via `mypy src` from each subproject's own directory), and `pytest -q`
myself — did not rely on the implementer's reported counts, though they matched exactly (body-layer:
1998 passed/4 xfailed; aircraft-layer: 262 passed; both pre-existing `ruff format` findings
reproduced in the exact files named). Mutation-tested the group-salience non-interaction claim
directly (two separate mutations, both passing when they should have failed) and the `FIRE_LIFE_
FRACTION_MAX` cross-key-coupling claim (grepped for module-level asserts referencing it; none found,
consistent with the implementer's note). Read the rendered `config/defaults.toml`, not just the
source comment, for the one new tuning constant — renders as a single clean sentence, no blank-line
truncation or backtick-wrap defect despite both being named as live risks in agent memory. Did not
independently re-derive the `(0.69, 0.84]` fire-fraction bracket or the sightline-cap exposure claim
beyond reading the cited acceptance documents and the call sites named — both are consistent with
what's on disk, not independently re-measured in a live sortie, which is correctly DoD's/the user's
to do, not Reviewer's.

---

## Fix-Pass Review — commit `607ba78`

Reviewed the single commit `607ba7803f4a64b287d092921702239ae27d99d0` on `feature/emitter-visibility`,
addressing the two required fixes above. Checked out the branch directly into a fresh worktree
(HEAD landed exactly on the named tip; no ff-from-stale-base was needed since the branch was not
checked out anywhere). Rebuilt the body-layer venv from the pinned versions and ran every check
myself; aircraft-layer is untouched by this commit (confirmed — `git show --stat` names no
`aircraft-layer/` path) so its own venv was not rebuilt.

### Fix 1 — `Percept.emitter_kind`, closed mapping

**Genuinely closed.** Grepped `body-layer/src/` for `Percept(` construction sites: `percept_of` in
`belief/percept.py` is the only one. Grepped for `.provenance` reads outside `Observation`: the only
hits are `belief/enrichment.py` and `belief/tools.py`, both reading an unrelated `provenance` field
on GIS features (settlement/road/water/landcover match objects), not `Observation`/`Percept` at all —
no second passthrough exists. `_EMITTER_KIND_BY_PROVENANCE.get(...)` is a `dict.get` with no default
override, so any `provenance` value absent from the mapping — every non-emitter value today, and any
future `PROVENANCE_*` constant nobody has added here yet — resolves to `None`. The mapping is the
only path; an unregistered provenance cannot leak through.

**Mutation of the forbidden-set guard.** Re-added `provenance: str | None = None` to `Percept`
(leaving `emitter_kind` in place) and ran `test_percept.py`. Two tests failed as expected:
`test_percept_has_no_truth_carrying_field` (the guard itself) and
`test_percept_of_maps_emitter_provenance_to_emitter_kind` (its own `not hasattr(percept,
"provenance")` assertion). Reverted; `git diff --stat` empty, full `test_percept.py` green again
(6 passed). The restored forbidden-set entry is a live contract, not a comment — confirmed by
mutation, not by reading the diff.

**The trade (mapping on `Percept` vs. adding `Observation.emitter_kind`).** Right call. The mapping
needed no change to `Observation`'s shape and left `test_naked_eye_source.py`'s/
`test_contacts_burning.py`'s/`test_speech.py`'s existing `Observation.provenance=PROVENANCE_EMITTER_
BURNING` fixtures exercising the real production path unchanged — confirmed by diff: none of those
three files appear in this commit. The one cost is a second place (`belief/percept.py`) that now has
to know about `PROVENANCE_EMITTER_BURNING` as a literal, alongside `naked_eye_source.py`'s own
definition of it — a small, explicit, one-directional dependency (belief importing a perception-layer
constant it already imported transitively anyway via `Observation`), not indirection that obscures
anything. The alternative would have touched more files for no corresponding gain in closure: the
mapping is exactly as closed as a dedicated `Observation.emitter_kind` field would have been, since
both ultimately need one hand-maintained list of which provenances count as emitters. No objection.

### Fix 2 — the falsifiable group-salience test

**Re-did the mutation independently**, inserting the leak at the actual call site named in the
implementer's own proof (`naked_eye_source.py`'s `salient_ids = group_salient_ids(...)` line, in this
checkout), not accepting the pasted red/green:

- Mutated to `salient_ids = frozenset(c.object_id for c in candidates)` (every candidate forced
  group-salient — the "one AAA gun makes a whole convoy visible" shape).
- `pytest -q tests/test_naked_eye_source.py -k test_emitter_does_not_widen_group_salience` →
  **FAILED**, `assert 2 == 1` — the healthy neighbour wrongly admitted as its own observation. Matches
  the implementer's reported result exactly.
- Reverted; `git diff --stat` empty; same command → **PASSED** (1 passed, 45 deselected).

**The 200 m cross-offset and clustering.** Computed `angular_separation_rad` directly between the
burning unit `(x=9000, z=0)` and the moved neighbour `(x=4000, z=200)` from the ownship origin:
theta_sep ~= 0.0500 rad (~2.86 deg), against a combined half-angular-size of ~0.00126 rad and the
`RESOLUTION_ANGULAR_RADIUS_RAD` floor of 0.00128 rad (at `presence_range_mult = 1.0` for
`UNAIDED_OPTIC`) — both (S) and (A) in `clustering.py`'s separability predicate clear by roughly
40x. The two candidates do not merge into one cluster; the test measures what it claims to.

**The window.** Recomputed from the running constants: `LOWRES_ANGULAR_RADIUS_RAD = 0.003` (the live
value in `config/defaults.toml`, not the `lo=0.00128` bound) gives a lone-presence range of
`7.0 / 0.003 = 2333.33 m`; `RESOLUTION_ANGULAR_RADIUS_RAD = 0.00128` gives the relaxed, group-admitted
range of `7.0 / 0.00128 = 5468.75 m`. **The implementer's figure, 2333-5469 m, is correct.** The
neighbour's actual range, `hypot(4000, 200) = 4005 m`, sits inside that window: beyond the
lone-presence threshold (so a correctly-unflagged candidate is rejected) but inside the relaxed one
(so a wrongly-flagged candidate would be admitted) — exactly the discriminating property the fixture
needs, confirmed by the mutation above actually flipping the outcome.

**The correction to this review.md's own cited figure.** The implementer was right to override it,
and this file does need correcting in place for a future reader. The earlier "~5.4-9.3 km" (Required
Fix #2, above) is wrong: the 5.4 km half (5469 m, rounding `RESOLUTION_ANGULAR_RADIUS_RAD`'s range to
one decimal of km) is the correct upper bound, but 9.3 km is not the lower bound of anything — it is
`visibility.py`'s own docstring citing a *different*, unrelated calibration rung (the S-300 complex
"nothing" observation near the ~10.4 km atmospheric limit, explicitly flagged in that same docstring
as not usable to bound this threshold). That earlier figure conflated an adjacent calibration note
with the actual code boundary instead of computing `size_m / LOWRES_ANGULAR_RADIUS_RAD` directly. The
correct window, confirmed twice now (implementer's calculation and this independent one), is
**2333-5469 m**, not 5.4-9.3 km. The original Required Fix #2 text above is left unedited as the
historical record of what was asked for and why the original fixture failed; any reader relying on
its cited window for a future test should use 2333-5469 m instead.

### Verification

Rebuilt `body-layer/.venv` from the pinned versions (`ruff==0.16.6`, `mypy==2.3.1`,
`pytest==9.1.1`, `numpy==2.4.6`, `pyproj==3.8.0`):

- `ruff format --check src tests` → `132 files already formatted` (clean; no pre-existing
  out-of-scope finding appeared in this checkout).
- `ruff check src tests` → `All checks passed!`
- `mypy src` (run from inside `body-layer/`) → `Success: no issues found in 60 source files`.
- `pytest -q` → **2000 passed, 4 xfailed** (the claimed 1998+2 new, matching exactly). No test was
  removed; the only change to the forbidden-set test was the one entry restored, and no other
  assertion anywhere was loosened to compensate (checked the full diff — the only other test file
  touched, `test_naked_eye_source.py`, only moved a fixture's position and added two straight
  assertions, no relaxation).
- Three-case end-to-end demonstration (`test_a_burning_unit_beyond_naked_eye_range_becomes_visible`,
  `test_the_same_unit_not_burning_is_not_visible`, `test_a_burning_unit_behind_terrain_stays_
  invisible`) → all three pass.

`aircraft-layer` untouched by this commit; not re-run (nothing changed there to verify that the
first review pass didn't already cover).

### Verdict

**APPROVED.** Both required fixes are correctly closed: the truth-boundary guard is restored and
confirmed live by mutation, and the group-salience test now sits inside the real discriminating
window and is confirmed falsifiable by an independent mutation at the actual call site. The
implementer's correction of this review's own cited figure is right; corrected above for any future
reader. Proceeds to Performance Reviewer and Security, then DoD.

### Review Confidence

Full read of the commit diff, `implementation.md`'s new section, and the implementer's agent-memory
note. Independently rebuilt the venv and ran every check rather than trusting the reported counts
(all matched). Both required fixes verified by independent mutation at the actual code (not by
re-reading the pasted red/green), including a mutation the implementer did not themselves report
(re-adding `provenance` to `Percept` directly, rather than only the two unit tests they added).
Independently recomputed the angular-separation arithmetic for the cross-offset claim rather than
taking "the two do not cluster" on faith.

---

## Stage B Review — `AC-B8`/`BL-B73`, commit `f02ec43`

Reviewed `feature/emitter-events` @ `f02ec435fe17d964f289095913c9d14d1afbc011` (Stage B: the
production firing-event Hook, the collector-side `EmitterTracker` latch/watchdog, `CONTACT_FIRING_SEEN`
and its priority/wording). Checked out the branch directly into a fresh worktree (HEAD landed exactly
on the named tip; no ff-from-stale-base was attempted since the dispatch already flagged the base as
diverged). Rebuilt both subprojects' venvs from the pinned versions and ran every check myself. Read
the plan (Stage B), the acceptance document, `AC-B8`/`BL-B73`/`BL-B74`'s roadmap entries, the
2026-09-24 closed probe, the implementer's own account, and the full diff (31 files, 3014/58).
Independently verified the concurrent-branch additivity claim for `events.py`/`speech.py` by reading
their diffs directly rather than trusting the implementer's note.

The gate chain, closed-mapping pattern, priority bands, wording, and the 128-sightline mitigation are
all implemented as planned and well tested. One correctness gap in the latch/watchdog state machine
needs to be addressed before this merges.

### Required Fixes

**1. `FIRING_WATCHDOG_S=10.0` can silently end a sighting while the unit is still genuinely firing,
and this rests on an unverified assumption about DCS event semantics the project's own research
already flagged as unknown.**

`EmitterTracker._apply` only refreshes `expires_at_sim` on `S_EVENT_SHOOTING_START` (once, at the
start of a burst) and on `S_EVENT_SHOOTING_END` (which tightens it). Nothing refreshes it while a
burst is merely continuing. `test_a_start_with_no_end_is_bounded_by_the_watchdog`
(`aircraft-layer/tests/test_firing_receiver.py:127`) demonstrates — and asserts as correct — that a
unit with an open `START` and no further events disappears from the snapshot at exactly
`FIRING_WATCHDOG_S` later, "no END, no DEAD, nothing but time."

The watchdog's stated purpose (plan's Co-moving Fields table, and this file's own module docstring)
is to bound "a `START` whose `END` never arrives." That phrase conflates two different causes with
one mechanism:

- **the unit was destroyed mid-burst** — already handled, immediately and independently, by the
  `S_EVENT_DEAD`/`S_EVENT_CRASH` removal path (`_DEATH_KINDS`). The watchdog is not needed for this
  case at all.
- **the unit is alive and still firing, and the burst has simply run longer than
  `FIRING_WATCHDOG_S`** — a continuous-fire weapon (autocannon/AAA holding fire on a target) engaging
  for more than 10 seconds is an entirely ordinary thing for this feature's own target scenario (a
  unit shooting at the aircraft). If `S_EVENT_SHOOTING_START` fires once per continuous trigger-pull
  rather than retriggering periodically — which is exactly what the Lua handler's one-time
  `PB_ACTIVE_FIRING_UNITS[initName] = true` on `SHOOTING_START` implements, with no mid-burst
  refresh — the entry is removed at t=10s even though the unit is still actively firing and a real
  `SHOOTING_END` will eventually arrive.

This is not a hypothetical I'm inventing: `aircraft-layer/research/2026-09-24-damage-and-firing-events
-over-mission-bridge.md:178-179` says explicitly, of this exact question, *"Whether
`S_EVENT_SHOOTING_START` fires once per burst or is retriggered mid-burst is **not documented**"* —
the project's own prior research already identified this as an open unknown, and neither the Stage B
plan nor the implementation re-raised it, resolved it, or flagged it in Risks & Unknowns. If DCS does
retrigger `START` periodically during a sustained burst, this gap doesn't exist in practice; if it
doesn't (which the Lua handler's own implementation assumes, by only writing the entry once), a
sustained engagement — the scenario the user's own direction was written around (*"taking fire"*) —
goes silently invisible mid-attack, with no error, no log line indicating why, and no test that would
catch it (every watchdog test in this file assumes "no further events" means "nothing is happening,"
never "the unit is still firing and no further event has fired yet").

**This is a correctness risk against the feature's own acceptance criterion** (*"the firing unit can
be seen at max player bubble range during the time it is firing"* — not for the first 10 seconds of
it), not a style nit, and it was not flagged anywhere in `plan.md` or `implementation.md`.

Recommended fix, scoped to be small: (a) raise `FIRING_WATCHDOG_S` to a conservative value well above
any plausible sustained engagement (its downside is minimal — it only matters in the genuine
"`END` dropped by the bridge and the unit died with no `DEAD`/`CRASH` either" case, which is already
rare), and (b) add this open question explicitly to the plan's Risks & Unknowns and to the live-sortie
acceptance checklist — specifically, whether `S_EVENT_SHOOTING_START` retriggers mid-burst needs a
live answer before `FIRING_WATCHDOG_S`'s true safe floor is known. This does not require touching the
latch (`FIRING_MIN_VISIBLE_S`) or the death-removal path, both of which are correct as built.

### On the 128-sightline mitigation — confidence assessment (per dispatch)

**Moderate-to-high confidence, not proof, and that is the right level for this stage.** Beyond the
three verification methods the implementer's report already names (Lua syntax check, self-containment
reading, static sort-key guards), I found the cross-Hook-global-sharing claim rests on a *stronger*
precedent than the one cited: `petrobrain-line-of-sight-hook.lua` already reads `PB_LOOK_HOUR`/
`PB_LOOK_FOV_DEG` — globals written by a *different* Hook script's own `dostring_in` call — in
*production*, not merely as an analogy to `PB_F10_QUEUE` (which is one Hook script's own queue,
written and drained by itself). That is the literal mechanism this mitigation needs (Hook A writes a
global in the `"scripting"` state, Hook B reads it on its own `dostring_in` call), already shipping.
So the mechanism itself is proven; what is not proven is that `PB_ACTIVE_FIRING_UNITS`'s specific
read/write pattern (written inside a persistent `world.addEventHandler` closure that runs
continuously, rather than written by a periodic `dostring_in` snippet like `PB_LOOK_HOUR` is) behaves
identically. **What would actually confirm it**: a live sortie with ≥128 units in one 180° look wedge
and one of them firing beyond the nearest 128 by range — the exact scenario the mitigation exists for
— confirming the far firing unit still gets a sightline. Short of that, the static guards correctly
pin the mechanism against silent regression, which is the right thing to have before a live sortie
exists to run.

### Optional Refinements

- **`implementation.md`'s "Files Changed" prose miscounts two new-file test totals** — it says
  `test_firing_schema.py` "(13 new)" and `test_firing_receiver.py` "(17 new)", but both files are
  new, and `grep -c '^def test_'` gives 12 and 15 respectively — matching the "Checks" section's own
  (correct) 12+15+2=29 arithmetic, which is also what the actual `pytest` run confirms (291 =
  262+29). The final numbers reported and verified are right; only the earlier prose narrative is off
  by one and two. Cosmetic, but worth a one-line fix in the plan file so a future reader doesn't
  recompute it and get confused by the mismatch between the two sections of the same document.
- **The rendered `config/defaults.toml` entry for `FIRING_MAX_AGE_S` drops its leading backtick**
  (`# plans/emitter-visibility/plan.md\` Stage B...` instead of `` # `plans/emitter-visibility
  /plan.md`...``). I checked whether this is a defect this PR introduced — it is not: the same
  generator drops the leading backtick on every pre-existing `#:`-comment that begins directly with
  a backtick-wrapped term (confirmed on `ATTACK_RUN_CHANGE_THRESHOLD_DEG`/
  `ATTACK_RUN_ELEVATION_GATE_DEG`'s own rendered entries, both pre-existing and both exhibiting the
  identical dropped-backtick pattern). A systemic, pre-existing generator quirk, not something to fix
  in this feature's scope — flagging only because the role instructions ask to read the rendered file
  and this is exactly the class of defect that check exists to catch, even when (as here) it turns
  out to be out of scope.
- **No module-level assert pins the ordering invariants this stage introduces** — `FIRING_MIN_VISIBLE_S
  (1.5) < FIRING_WATCHDOG_S (10.0)` in `firing_receiver.py`, and
  `_FIRING_TARGETS_OWNSHIP_THREAT_BAND (-2) < _FIRING_THREAT_BAND (-1) < _DEFAULT_THREAT_BAND (0)` in
  `callouts.py`. Both are bare module constants (no tuning loader for the first pair; a stated
  judgement call for the second), so neither can be broken by a config file — only by a future code
  edit. A one-line `assert` at each site costs nothing and converts "a future edit silently breaks
  the ordering" into an import-time failure. Not required: the relationships are correctly
  documented in each constant's own comment and the risk surface is a direct code edit, not
  configuration drift.

### Confirmed, no issues

- **`events.py`/`speech.py` are genuinely additive** relative to `main` — read both diffs directly:
  every change is a new import, a new `EventKind` literal appended to the `Literal[...]` tuple, a new
  `Final` constant, a new dataclass field with a `False` default, and one new `if` branch in
  `_render_lifecycle_text`. Nothing existing is modified or reordered. Safe for the concurrent
  `feature/attack-run-fixes` branch (which touches the same two files) to merge independently; any
  conflict will be textual, not semantic.
- **`visibility.py` is untouched in Stage B**, confirmed by `git diff` — the gate chain, tier clamp,
  and bypass logic are exactly Stage A's, as the plan said they would be.
- **`BL-B74`'s seam is genuinely inert.** `S_EVENT_SHOT` is accepted on the wire
  (`schema/firing.py`), parsed, and its `x`/`z` carried through to `FiringRawEvent`, but
  `EmitterTracker._apply` has no branch for it at all — it falls through the `if`/`elif` chain as a
  deliberate no-op (commented as such). No dissipation constant, no `LAUNCH_SMOKE` entry, nothing
  acted on.
- **The priority bands displace nothing else.** `_FIRING_THREAT_BAND`/
  `_FIRING_TARGETS_OWNSHIP_THREAT_BAND` are `-1`/`-2`; every other `EventKind` still resolves to
  `_DEFAULT_THREAT_BAND = 0` unchanged (grepped for every other reference to that constant; none
  exist outside `callouts.py`). Strictly more urgent, nothing bumped down.
- **The second closed mapping (`_TARGETS_OWNSHIP_PROVENANCE`) is the right pattern repeated, not a
  sign the pattern needs generalising** — `targets_ownship` is a genuinely independent bit from
  "which kind", exactly the reasoning the implementer gave (Notable Discovery 7) for not folding it
  into a fourth `EmitterKind` value. `test_percept.py`'s forbidden-set test is untouched (diffed
  directly); unregistered provenance values still map to `None`/`False`, never pass through. If
  `BL-B74` needs a third independent bit (e.g., the frozen position), it would be worth asking then
  whether `Percept` should carry one small per-emitter metadata object instead of a third parallel
  frozenset — not before.
- **The `FakeAircraftClient` method addition is the minimum change** — exactly the 5 files the
  dispatch named, each adding only `get_firing_latest`, caused by the new unconditional call site in
  `naked_eye_source.poll()`. No other coupling masked.
- **Mission-restart reset is correct and does not inherit `BL-B68`'s known gap** — `EmitterTracker`
  clears on `dcs_model_time_s` regression independently of body-layer's belief layer (which `BL-B68`
  correctly still does not reset); after a restart, the firing snapshot going empty simply lets
  `firing_event_kind`'s one-directional design quietly stop reporting `is_firing`, with no stale
  `CONTACT_FIRING_SEEN` re-fired and no crash.
- **Detection-only held**: no path from `FIRING`/`targets_ownship` to `CLASS`/`TYPE` — the tier clamp
  this inherits from Stage A is untouched, and `callout_priority`'s special-case is purely an
  ordering change, never a classification one.
- **Aircraft-layer's two bare constants** (`FIRING_MIN_VISIBLE_S`, `FIRING_WATCHDOG_S`) are
  acceptable as plain module constants per the project's own stated rule (no `tuning.*` loader exists
  outside body-layer) — correctly flagged in the implementer's own report as a candidate for that
  mechanism if/when aircraft-layer grows one, which is the right amount of ceremony for this stage.

### Verification

Rebuilt both subprojects' venvs from the pinned versions (`ruff==0.16.6`, `mypy==2.3.1`,
`pytest==9.1.1`, `numpy==2.4.6`, `pyproj==3.8.0`):

**aircraft-layer**
- `ruff format --check .` → 1 file would be reformatted (`research/2026-10-06-unit-id-join-reduce.py`
  — the exact pre-existing out-of-scope file the dispatch said to expect), 117 already formatted.
- `ruff check .` → 1 pre-existing `EXE001` in the same research file; no other findings.
- `mypy src` (run from inside `aircraft-layer/`) → `Success: no issues found in 23 source files`.
- `pytest -q` → **291 passed** (claimed: 291, baseline 262). Matches exactly.

**body-layer**
- `ruff format --check src tests` → `133 files already formatted` (clean — the canonical command per
  this subproject's own `CLAUDE.md` scopes to `src`/`tests`, not `research/`, so the out-of-scope
  finding the dispatch named for the full-tree form correctly does not appear here).
- `ruff check src tests` → `All checks passed!`
- `mypy src` (run from inside `body-layer/`) → `Success: no issues found in 60 source files`.
- `pytest -q` → **2041 passed, 4 xfailed** (claimed: 2041/4, baseline 2000/4). Matches exactly.

Test-count accounting independently recomputed per file (`git diff ... | grep -cE '^\+def test_'`),
not taken from the implementer's prose: body-layer's 9+4+5+10+3+4+6=41 matches the suite delta
exactly; aircraft-layer's actual 12+15+2=29 matches the suite delta exactly but differs from the
"Files Changed" section's own prose (13/17) — see Optional Refinements.

Re-ran the specific demonstration tests named in the dispatch directly (not just as part of the full
suite): far-range firing visible, same-unit-not-firing invisible, firing-behind-terrain invisible,
sub-poll-burst-survives-one-poll (at the collector layer, where the latch actually lives),
`targets_ownship` wording selection, and firing-wins-over-burning precedence — all pass.

### Verdict

**NEEDS REVISION** — one required fix, scoped and small to apply (raise `FIRING_WATCHDOG_S` to a
safer default, document the open DCS-retrigger question in Risks & Unknowns and the live-sortie
checklist), though the underlying DCS-behaviour question it rests on can only be closed by a live
sortie or an Investigator pass, not by code alone. Everything else — the gate chain, the closed
mappings, the priority bands, the wording, the 128-sightline mitigation, the seam discipline for
`BL-B74`, and the concurrent-branch additivity of `events.py`/`speech.py` — checked out clean on
direct reading and independent test execution.

Per the project's re-entry rule, this goes back to Implementer for the fix, then Reviewer again on
the fix, before DoD.

### Review Confidence

Full read of the plan (Stage B), the acceptance document, all three new/updated roadmap entries
(`AC-B8`, `BL-B73`, `BL-B74`), the 2026-09-24 closed probe and its underlying research note, the
implementer's own account, and the full diff (31 files). Independently rebuilt both subprojects'
venvs and ran every check myself; all counts matched the implementer's claims exactly except the
`implementation.md` prose-vs-Checks test-count mismatch noted above (the Checks numbers, and the
actual test run, are correct). Did not independently fly a live sortie to confirm the 128-sightline
mitigation or resolve the `FIRING_WATCHDOG_S` question — both correctly require a live DCS process,
which is DoD's/the user's to run, not Reviewer's; this review's job was to establish what is and is
not yet verified, and the watchdog gap specifically because it was not flagged as an open question
anywhere on this branch.
