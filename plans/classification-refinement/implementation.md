### Implementation Summary

Stages 1-4 of `plans/classification-refinement/plan.md` (BL-2.6), fully offline, one commit
per stage per the plan's "mechanism and calibration never share a commit" rule. Stages 5-10
(live acceptance, tier-derived confidence, gate calibration, tuning, docs) are not started --
out of scope for this pass.

**Update (second session): Stages 6-7 done, also offline, also one commit per stage.** Stage 5
(live acceptance #1) was not run this session -- it needs a live DCS sortie and was explicitly
out of scope for this pass, same posture as Stages 8-9 below. Stages 8-10 remain outstanding.

**Stage 6** (`6bea387`): `visibility.check_visibility` now computes the *achieved* recognition
tier via a new `_achieved_tier(range_m, size_m)` helper, instead of always returning the flat
`"medres"` constant it returned before. Three confidence constants replace the old single flat
one: `NAKED_EYE_PRESENCE_CONFIDENCE` (0.2), `NAKED_EYE_VISIBILITY_CONFIDENCE` (0.4, kept under its
original name -- it is still the `medres`/class-tier value, and every existing caller/test already
refers to it that way), `NAKED_EYE_TYPE_CONFIDENCE` (0.55, still below `association.
CONFIDENT_ASSOCIATION_CONFIDENCE = 0.6` per the module's existing "weaker evidence than a real
HelperAI detection" invariant). `naked_eye_source._classification_for_tier(tier, object_type,
op_class)` maps the achieved tier to `(classification_raw, classification_level)`: `hires` tries
`reporting_names.reporting_name_for(object_type)` first (level 3, type), falling back to `op_class`
at level 2 when the reporting-name table has no exact entry for that `object_type` (Petrovich can't
speak a name he doesn't have, even from a close look); `medres` stays at `op_class`/level 2,
unchanged from before. The gating tier itself stayed `medres`
(`NAKED_EYE_GATING_ANGULAR_RADIUS_RAD`/`NAKED_EYE_GATING_TIER_NAME` untouched this commit), so the
`_achieved_tier` helper's `"lowres"` branch was unreachable code this stage -- verified by running
the full suite and confirming no test could reach it, exactly as the plan predicted.

**Stage 7** (`479067a`): one-line calibration change -- `NAKED_EYE_GATING_ANGULAR_RADIUS_RAD` moved
from `MEDRES_ANGULAR_RADIUS_RAD` to `LOWRES_ANGULAR_RADIUS_RAD`, `NAKED_EYE_GATING_TIER_NAME` from
`"medres"` to `"lowres"`. This alone made Stage 6's already-built `_achieved_tier` `"lowres"` branch
reachable for the first time -- no other code changed. Rewrote the two `test_visibility.py`
assertions whose boundary was the old `medres` gate (see "Notable Discoveries" for exactly which
and why), and added a new end-to-end presence-tier test in `test_naked_eye_source.py`.

**Stage 1** (`381e745`): moved `_op_class_of`/`class_compatibility` out of
`association_over_time.py` into a new `belief/classification.py`, pure move, zero behaviour
change. `association_over_time.py` imports both names so `test_association_over_time.py`'s
existing import path kept working unchanged.

**Stage 2** (`8a3c343`): added the lattice/fusion mechanism to `classification.py`
(`SpecificityLevel`, `ClassificationBelief`, `PRESENCE_CLASS`, `parent_class_of`,
`new_classification_belief`, `fold_classification`, `CLASSIFICATION_CONTRADICTION_LOCKOUT_S`).
`Observation`/`Percept` gained `classification_level: int` (default 2 = class level, so every
existing construction site keeps compiling). `hybrid_source.py` now declares `classification_level=3`
(type -- indication text is type-specific by channel); `naked_eye_source.py` declares
`classification_level=2` explicitly (unchanged behaviour -- Stage 6 will vary it by tier).
`Contact.classification` now folds via `fold_classification` instead of being overwritten;
`Contact.last_class_raw` keeps its exact original meaning and stays the association gate's input.

**Stage 3** (`06b3ea8`): `EventKind` gained `CONTACT_CLASSIFICATION_CHANGED`; `Event` gained
three optional fields (`previous_classification`, `classification`, `direction`), all
defaulting to `None`. `events.classification_event()` is the pure before/after comparison
(fires on refine -- level increased -- or contradict -- level decreased, or equal level with a
different value -- never on reinforce/hold/decay). `Contact.last_emitted_classification` mirrors
`last_emitted_certainty`; `ContactStore.tick()` mints the classification event after that tick's
own lifecycle event, per contact.

**Stage 4** (`0e305ea`): `tools._contact_facts`'s `classification` key moved from
`{"value": last_class_raw}` to `{"value", "level", "confidence"}`, reading `Contact.classification`
(the folded best claim) instead of `last_class_raw`. `_contact_summary` and `find_contact` also
read `Contact.classification` now. `console.format_event_for_overlay` renders a
`"<id>: CONTACT_CLASSIFICATION_CHANGED, <previous> -> <current>, <summary>"` transition line for
that one event kind only; every other kind's rendering is byte-for-byte untouched (per BL-2.5's
rejected restyle).

### Files Changed

- `body-layer/src/belief/classification.py` -- new. Stage 1's re-homed `_op_class_of`/
  `class_compatibility`; Stage 2's `SpecificityLevel`, `ClassificationBelief`, `PRESENCE_CLASS`,
  `parent_class_of`, `new_classification_belief`, `fold_classification`, `FoldOutcome`,
  `CLASSIFICATION_CONTRADICTION_LOCKOUT_S`.
- `body-layer/src/belief/association_over_time.py` -- Stage 1: removed the moved functions,
  imports `class_compatibility` from `classification.py`.
- `body-layer/src/belief/contacts.py` -- Stage 2: `Contact.classification`,
  `classification_lockout_until_sim`; `record()`/`from_percept()` fold instead of overwrite.
  Stage 3: `Contact.last_emitted_classification`; `tick()` mints `CONTACT_CLASSIFICATION_CHANGED`
  after the lifecycle event.
- `body-layer/src/belief/events.py` -- Stage 3: `CONTACT_CLASSIFICATION_CHANGED` kind, `Event`'s
  three new optional fields, `classification_event()`.
- `body-layer/src/belief/tools.py` -- Stage 4: `_classification_facts()` (new), `_contact_facts`,
  `_contact_summary`, `find_contact` read `Contact.classification` instead of `last_class_raw`.
- `body-layer/src/belief/console.py` -- Stage 4: `format_event_for_overlay` transition rendering
  for `CONTACT_CLASSIFICATION_CHANGED`.
- `body-layer/src/perception/source.py` -- Stage 2: `Observation.classification_level: int = 2`
  (a bare `int`, not `belief.classification.SpecificityLevel` -- `perception/` must not import
  `belief/`).
- `body-layer/src/belief/percept.py` -- Stage 2: `Percept.classification_level: int = 2`,
  carried through by `percept_of`.
- `body-layer/src/perception/hybrid_source.py` -- Stage 2: `classification_level=3`.
- `body-layer/src/perception/naked_eye_source.py` -- Stage 2: `classification_level=2`.
- `body-layer/tests/test_classification.py` -- new (Stage 2): lattice ordering, `parent_class_of`,
  `new_classification_belief`, and the full refine/reinforce/hold/contradict/lockout table for
  `fold_classification`.
- `body-layer/tests/test_decay.py` -- Stage 2: `_contact()` fixture passes `classification=`
  (new required `Contact` field).
- `body-layer/tests/test_cross_channel_fusion.py` -- Stage 2: `_observation()` gained
  `classification_level`; added a real cross-channel class-to-type refinement test.
- `body-layer/tests/test_contacts.py` -- Stage 2: founding-percept classification-level test.
  Stage 3: tick-minted classification-changed-event test (ordering + idempotence).
- `body-layer/tests/test_events.py` -- Stage 3: `classification_event()` coverage (all
  refine/contradict/no-event cases).
- `body-layer/tests/test_tools.py` -- Stage 4: updated assertions for the new
  `facts.classification` shape.
- `body-layer/tests/test_console.py` -- Stage 4: updated `show <id>` assertion for the new
  shape; added the classification-transition overlay-rendering test.

### Files Changed (Stages 6-7)

- `body-layer/src/perception/visibility.py` -- Stage 6: `VisibilityResult.tier`/`.confidence` now
  computed per-candidate by `_achieved_tier` instead of the flat `NAKED_EYE_GATING_TIER_NAME`/
  `NAKED_EYE_VISIBILITY_CONFIDENCE` constants; added `NAKED_EYE_PRESENCE_CONFIDENCE`,
  `NAKED_EYE_TYPE_CONFIDENCE`. Stage 7: `NAKED_EYE_GATING_ANGULAR_RADIUS_RAD`/
  `NAKED_EYE_GATING_TIER_NAME` moved from medres to lowres.
- `body-layer/src/perception/naked_eye_source.py` -- Stage 6: new `_classification_for_tier`
  helper and `_CLASSIFICATION_LEVEL_CLASS`/`_CLASSIFICATION_LEVEL_TYPE` constants (bare ints
  mirroring `belief.classification.SpecificityLevel`, not imported -- `perception/` must not
  import `belief/`); `_build_observation` now calls it instead of hardcoding `profile.op_class`/
  level 2. Imports `reporting_names.reporting_name_for`. No changes needed in Stage 7 -- the
  mapping already handled `"lowres"` via its `else` branch.
- `body-layer/tests/test_visibility.py` -- Stage 6: two new tests for the `hires` achieved-tier
  branch (`test_infantry_well_inside_hires_tier_range_achieves_hires_tier`,
  `test_infantry_just_outside_hires_tier_range_achieves_medres_tier`). Stage 7 (rewrite, see
  Notable Discoveries): `test_infantry_just_outside_medres_tier_range_is_not_visible` replaced by
  `test_infantry_just_inside_lowres_tier_range_is_visible` +
  `test_infantry_just_outside_lowres_tier_range_is_not_visible`;
  `test_ural_truck_size_curve_binds_below_the_range_cap` renamed/rewritten to
  `test_ural_truck_gate_now_binds_at_the_range_cap_under_lowres`; the ship-cap test's docstring
  comment updated (assertions unchanged).
- `body-layer/tests/test_naked_eye_source.py` -- Stage 6: three new end-to-end tests for the
  hires-reaches-type path, the medres-stays-class path, and the hires-with-no-reporting-name
  fallback path. Stage 7: one new end-to-end presence-tier test.

### Tests Added

- `test_classification.py` (19 tests) -- `SpecificityLevel` ordering; `parent_class_of` for
  type/class/presence/unresolvable values; `new_classification_belief`'s per-level confidence;
  `fold_classification`'s founding/refine/reinforce/hold/contradict rows, including the
  unresolvable-parent-always-refines case, the same-class-different-type collapse-to-class case,
  the different-class collapse-to-presence case, and the contradiction lockout (rejects
  promotion while locked, succeeds again once expired).
- `test_cross_channel_fusion.py::test_naked_eye_class_then_scope_type_refines_the_contact_classification`
  -- end-to-end: naked-eye class-level observation then scope type-level observation of the same
  spatial contact refines `Contact.classification` to type, while `last_class_raw` still reflects
  only the most recent contributor.
- `test_contacts.py::test_founding_percept_seeds_classification_at_its_own_level` -- a
  type-level founding observation founds the contact at type level, not a hardcoded default.
- `test_contacts.py::test_tick_mints_classification_changed_after_the_lifecycle_event` --
  founding tick emits only `CONTACT_DETECTED` (no synthetic classification event); a later
  refining percept mints `CONTACT_CLASSIFICATION_CHANGED` on the next tick, after that tick's
  lifecycle event; idempotent on a repeated `tick()` at the same `now_sim`.
- `test_events.py` classification cases -- `previous is None` emits nothing; higher level is
  `"refined"`; lower level and same-level-different-value are both `"contradicted"`; same
  level+value emits nothing (covers reinforce and hold alike, since the comparison ignores
  confidence/established_sim).
- `test_console.py::test_format_event_for_overlay_renders_classification_transition` -- the new
  `"<previous> -> <current>"` line, distinct from the unchanged rendering of every other kind.

### Checks

- `ruff format --check body-layer/src body-layer/tests`: pass
- `ruff check body-layer/src body-layer/tests`: pass
- `mypy body-layer/src` (run as `cd body-layer && mypy src`, per `body-layer/CLAUDE.md`'s CWD note): pass
- `pytest body-layer/tests -q`: pass -- 238 passed (baseline before this branch was 210; net +28)

**Update (Stages 6-7)**: same three checks, run after each stage.
- After Stage 6: 243 passed (238 + 5 new tests; no rewrites -- the gate stayed `medres` so nothing
  existing changed behaviour).
- After Stage 7: 245 passed (243 + 2 net new -- one `test_visibility.py` test split into two
  boundary tests, plus one new end-to-end presence-tier test in `test_naked_eye_source.py`).

### Notable Discoveries (Stages 6-7)

- **Stage 7's gate move changed which of two things binds a truck-sized object's range threshold.**
  Under the old `medres` gate, Ural's threshold (3000 m) sat comfortably below
  `NAKED_EYE_RANGE_CAP_M` (5000 m) -- the size curve did the discriminating, which is what the old
  test's name asserted. Under `lowres`, Ural's threshold is `6 / 0.0043 * 4.0 = 5581.4` m, which now
  *exceeds* the cap -- so the cap itself becomes the binding constraint, exactly the "flattened size
  curve at the cap" risk the plan's Risks section names for truck-sized-and-up objects. This is why
  that test's premise, not just its numbers, needed rewriting (renamed to
  `test_ural_truck_gate_now_binds_at_the_range_cap_under_lowres`), and why the ship-cap test's
  comment ("This is now the cap's only job") needed correcting -- it was already wrong the moment
  the gate moved, since the cap now binds two classes of object, not one.
- **The `_achieved_tier` helper's `"lowres"` branch was written in Stage 6 but provably dead code
  until Stage 7** -- confirmed by running the full suite after Stage 6 and finding no test (old or
  new) could reach it, since every candidate that got that far had already been dropped by the
  `medres` gate. This is the intended shape from the plan ("mechanism first, unreachable; gate
  second, reachable") rather than an oversight -- noted here so a future reader doesn't mistake the
  one-line diff in Stage 7 for "also adding the lowres logic."
- **`NAKED_EYE_TYPE_CONFIDENCE` was picked at 0.55, not higher**, specifically to preserve the
  existing invariant (stated in `visibility.py`'s own module docstring before this change) that
  *any* naked-eye visibility-filter pass, even the closest/most-confident one, stays below
  `association.CONFIDENT_ASSOCIATION_CONFIDENCE = 0.6` -- a naked-eye pass is still not a real
  HelperAI detection-existence signal, however close the range.
- **The `hires`-tier reporting-name fallback (to class, not to `None`) was an implementation
  decision not spelled out numerically in the plan's worked table**, inferred from the plan's own
  stated invariant ("Petrovich can never mis-identify, only fail to identify") -- since not every
  `object_type` has an exact entry in the 595-row reporting-name table (confirmed directly: the
  bare `"Infantry"` string used throughout the existing fixtures has no exact match, only compound
  entries like `"Infantry AK"` do), silently emitting `classification_raw=None` at `hires` range
  would have been a soft crash for observation-formatting/belief code downstream, not a coarser-but-
  valid claim. Falling back to `op_class` (class level) for an unresolved `hires`-tier candidate
  keeps every emitted `Observation` a valid claim at *some* level, consistent with the lattice's own
  "unresolvable parent yields unknown comparability, never contradiction" rule from Stage 1-4.

### Notable Discoveries (Stages 1-4)

- **`Contact.classification` is a new required dataclass field** (no default, since every
  contact must have *some* classification belief from the moment it's founded). This broke the
  one test file that constructs `Contact` directly (`test_decay.py`'s `_contact()` fixture) --
  fixed with a one-line addition, not a rewrite of any assertion. No other test file constructs
  `Contact` directly (`grep -rl "Contact(" tests/` confirmed only that one file).
- **`refine` vs. `contradict` turned out to be derivable purely from before/after level+value**,
  with no need to thread a separate "direction" flag out of `fold_classification` into the event
  layer: `fold_classification`'s `_collapse` helper always produces a *lower* level than either
  input (a genuine same-level disagreement always collapses downward), so
  `events.classification_event` can compare `Contact.last_emitted_classification` against
  `Contact.classification` exactly the way `lifecycle_event_kind` already compares certainties --
  same shape, no new plumbing. This also means `fold_classification`'s own `FoldOutcome.
  contradicted` bit is used only for the lockout timestamp in `contacts.py`, not for event minting.
- **`class_compatibility`/`_op_class_of`'s existing test coverage in
  `test_association_over_time.py` was left untouched and still passes unmodified** -- Stage 1's
  move changed only the import path, confirming it really was behavior-preserving.
- The plan's own worked example (`OP_ARMORED` -> `T-72` via `reporting_name_for`) was used almost
  verbatim as the primary cross-channel and event-ordering test fixture, since it is the
  document's own canonical scenario and made the tests read as a direct check of the design
  section rather than an invented case.
