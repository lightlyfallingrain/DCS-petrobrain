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
