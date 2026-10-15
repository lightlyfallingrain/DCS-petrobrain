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
