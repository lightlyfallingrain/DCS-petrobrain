### Implementation Summary

Stages 1-4 of `plans/classification-refinement/plan.md` (BL-2.6), fully offline, one commit
per stage per the plan's "mechanism and calibration never share a commit" rule. Stages 5-10
(live acceptance, tier-derived confidence, gate calibration, tuning, docs) are not started --
out of scope for this pass.

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

### Notable Discoveries

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
