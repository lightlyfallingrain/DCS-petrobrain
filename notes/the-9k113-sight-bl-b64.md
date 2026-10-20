# The 9K113 sight (BL-B64)

- **A field that should carry a physical/mechanical bound and is only ever read with `is not
  None` downstream needs the real bound check added at the point the value is *chosen*, not at the
  point it is consumed.** `Optic.regard_azimuth_half_deg`/`regard_elevation_*` were added as data
  in Stage 1 with a docstring saying enforcement was deferred to Stage 2; Stage 2 landed and never
  closed that deferral, because nothing on its own task list named "close the deferral" and three
  review passes each verified a true but narrower claim (the cone reads actual aim; the cone and
  cap are correctly paired; OBSERV-off tears the cone down) without ever checking whether the aim
  the cone was built from had itself been validated against what the instrument could mechanically
  reach. Found by Security, not Review, because Review's checklist never had "was this bound ever
  enforced" on it — the docstring read as "deferred, not yet due" rather than "missed."
- **Fixing a leak at the point a value is chosen does not fix every place that value is swept or
  derived.** The field-of-regard fix closed `_decide_sighting`'s look-selection leak; a second,
  smaller leak survived in `look_sweep`, which could still generate steps past the same mechanical
  limit at a tighter margin (67° against a 60° limit, found while fixing the first). Any check
  added at a "where the value is chosen" point should prompt a grep for every other place the same
  raw value is swept, widened, or otherwise derived into a new value before being used.
- **A deferral note that outlives the stage it names reads as a settled decision to everyone after
  it, not as an open item.** "Enforcement deferred to Stage 2" shipped in Stage 1; Stage 2 landed
  without adding the enforcement and without updating or removing the note. Three independent
  review passes read the unchanged comment as "this is still pending, as documented" rather than
  "the thing this note promised should have happened by now and didn't." A deferral note needs a
  stage name that can be checked against reality, and checking it against reality is only cheap if
  something other than the note's own wording prompts the check.
- **A dataclass documented as "frozen and replaced rather than mutated" can still silently drop a
  persisted field, if some of its construction sites build it fresh instead of calling
  `replace()`.** `OpticState`'s docstring reads as if every transition goes through
  `dataclasses.replace(state, ...)`, which would carry every field forward automatically — but two
  phase-entry branches construct `OpticState(...)` fresh, naming only the fields that phase's own
  bookkeeping needs, so a newly added persistent field (`actual_aim_*`) silently resets to its
  default on exactly those transitions. Before adding a field meant to persist independently of a
  state machine's phase, grep every construction site of the dataclass and classify each as
  `replace()` (safe) or a fresh call (needs the field added by hand) — this is invisible to "does
  the feature work" testing if the feature's own trivial-passthrough stage never exercises the gap.
- **The same defect shape — state that should reset or carry across a transition, and doesn't —
  recurred independently seven times across two related features** (`BL-14`'s attack-run work and
  this entry): a stale target surviving re-selection, a dataclass field dropped on fresh
  construction, a command-driven field divergence invisible to a phase dispatch that only checked
  its own internal stop conditions, and others. Four different people/passes found instances of it
  (two by the implementer's own failing tests, one by a reviewer building a diverged state by
  hand, one by security executing a scenario) — suggesting this is a property of this kind of
  code (phase/mode state machines with more than one field that should move together) rather than
  of any one implementation, and worth a structural check (e.g. "do all fields that should move
  together actually get updated by every transition path") rather than relying on each instance
  being caught individually.
- **Two Hook scripts can share state with no new transport, because their separate
  `dostring_in("scripting", ...)` calls execute in the same persistent mission-scripting Lua
  state.** A global a first Hook script's drained snippet writes (`PB_ACTIVE_FIRING_UNITS`,
  `petrobrain-firing-events-hook.lua`) is directly readable by a second, unrelated Hook script's
  own snippet (`petrobrain-line-of-sight-hook.lua`'s sort-key splice) with no collector round trip,
  no wire message, and no coupling between the two scripts' own code beyond agreeing on a global's
  name. This was not obvious from reading either script's header alone — found only by noticing
  that `petrobrain-f10-commands-hook.lua`'s own header already documents the same persistence for
  its own queue global. Worth checking for before reaching for a new transport whenever one Hook
  script's state needs to influence another's `dostring_in` snippet (`plans/emitter-visibility/
  implementation.md`, Notable Discoveries Stage B).
- **`Contact` carries no DCS `object_id` at all** -- the no-omniscience boundary means belief
  retains what was *observed*, not the engine's ground-truth identity -- so any later code needing
  to correlate a raw `object_id` back to a `contact_id` has to build its own cache from admitted
  rows rather than reading the id off `Contact`. `BL-B76`'s rejected-candidate join hit this and
  had to invent one; `perception/naked_eye_source.py` already keeps a richer private version for
  its own majority-overlap clustering. The gap is structural, not an oversight, so expect it to
  recur whenever new code needs that correlation *outside* a normal admission -- and note that any
  such cache, being admitted-only, cannot see a cluster split whose child was rejected that poll
  (`plans/bl-b76-tripwire/implementation.md`).
- **A helper written for an optic with no field-of-regard limit can have an elevation gap that is
  a true no-op for every existing caller, and stays invisible until a *new* caller gives it an
  optic that is actually regard-bound.** `belief.optic_policy.search_pattern`'s elevation
  (`atan2(altitude_agl_m, range_m)`) was never checked against `regard_elevation_down_deg` —
  harmless for its original caller (`BINOCULAR_OPTIC`, which has no field of regard at all), and
  still harmless for the plan's own azimuth-only framing of the fix. `9k113-narrow-search`'s idle
  search cycle became the function's first caller for a regard-bound sight optic, at an ordinary
  cruise altitude (>~625 m AGL, not an edge case) — a third occurrence of the exact field-of-regard
  enforcement gap this entry's first bullet already names, missed by the plan, the implementer and
  two Reviewer passes, caught only by Security's deep analysis. When a plan reuses an existing
  helper for a new optic/caller, ask explicitly which of the helper's own silent assumptions were
  true only because of the *old* caller's properties — "no field of regard" is one such property,
  and it does not transfer.
- **An invariant test built with empty/default inputs and a realistic-geometry test that checks
  only one axis can sit side by side for an entire review cycle without ever covering the
  combination that matters.** The existing `within_field_of_regard` idle-aim tests passed no real
  `sight_*_search` sequences at all, so they exercised the trivial hold-last-position fallback, not
  `search_pattern`; the tests that *did* drive real geometry checked azimuth sub-spans only, never
  elevation. Neither test was wrong on its own terms, and together they still missed the gap above.
  When adding a new producer to an existing invariant test, drive it with the real sequence-builder
  the production call site uses, not a synthetic or empty stand-in, and check every axis the bound
  has, not just the one the existing tests already cover.
