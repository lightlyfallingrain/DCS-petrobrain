## Review: BL-2.6 Stages 1-4 (classification-refinement)

Commits reviewed: `381e745` (Stage 1), `8a3c343` (Stage 2), `06b3ea8` (Stage 3), `0e305ea` (Stage 4).
Scope: mechanism only (lattice, fusion, event, surfacing) — no calibration (Stages 6/7/9 out of
scope for this pass, confirmed not touched).

### Review Summary

This is a clean, well-scoped implementation. Each commit does exactly what its stage promises,
docstrings are precise about *why* (not just what), and the plan's explicit decisions (naked-eye
reaching type at Stage 6, not this pass; `last_class_raw` staying the gate's input; events minted
in `tick` not `ingest`) are all honored correctly in code, not just in prose.

Verified directly against the code (not just the implementer's log):

- **Fold table matches plan §3 exactly.** Traced `fold_classification`/`_fold_higher`/
  `_fold_same_level`/`_collapse` by hand against refine/reinforce/hold/contradict, including the
  edge cases: unresolvable-parent always refines (never contradicts), same-class-different-type
  collapses to class, different-class collapses to presence, lower incoming level is a pure hold
  (held survives untouched, no confidence/established_sim mutation).
- **`last_class_raw` untouched in meaning** — still set unconditionally in `record()`/
  `from_percept()` from the raw percept string, still the sole input to
  `association_over_time`'s gate. `Contact.classification` is the new, separate folded field.
  `tools.py`/`console.py` read `classification`, never `last_class_raw`, per plan.
- **`classification_level` defaults preserve every existing construction site.**
  `Observation.classification_level: int = 2` and `Percept.classification_level: int = 2` both
  default to `SpecificityLevel.CLASS`'s value; `mypy --strict` and the full suite confirm nothing
  broke.
- **No `perception/` → `belief/` import introduced.** Grepped `src/perception/` for `from belief`/
  `import belief` — zero hits. `classification_level` is a bare `int` on `Observation`/`Percept`,
  exactly as the plan requires; the enum only appears once the value crosses into `belief/`.
- **Event minted in `tick()`, not `ingest()`, after the lifecycle event** — read `ContactStore.tick`
  directly: lifecycle event appended and `last_emitted_certainty` updated first, *then*
  `classification_event()` compared and appended, per contact. Matches plan §4's ordering
  requirement.
- **`Event` fields default to `None`** — `previous_classification`, `classification`, `direction`
  are all `X | None = None` on the frozen dataclass; every pre-existing `Event(...)` construction
  site in the three lifecycle-event tests still compiles unchanged.
- **`format_event_for_overlay` only branches on the new kind** — the `if event.kind ==
  CONTACT_CLASSIFICATION_CHANGED:` branch is additive; the fallthrough line for every other kind is
  byte-for-byte what it was before this branch, confirmed by reading the diff (no lines touched
  outside the new `if`).
- **Stage 6 boundary respected.** `naked_eye_source.py` declares `classification_level=2`
  unconditionally (one call site, no tier branching); `perception/visibility.py`,
  `tests/test_visibility.py`, and `tests/test_naked_eye_source.py` all show a zero-line diff across
  the whole Stage 1-4 range (`git diff --stat 1dd2d54..0e305ea` on those three paths is empty).
  Tier thresholds are genuinely untouched, as the plan's "mechanism and calibration never share a
  commit" rule requires.
- **Test coverage matches the plan's Affected Modules list** — `test_classification.py` (new,
  19 tests: lattice ordering, `parent_class_of`, fold table including lockout),
  `test_contacts.py`, `test_events.py`, `test_tools.py`, `test_console.py`,
  `test_cross_channel_fusion.py`, `test_decay.py` all extended as listed; nothing extra, nothing
  missing from that list.

### Verification commands (run directly, body-layer venv)

- `ruff format --check src tests` — pass (42 files already formatted)
- `ruff check src tests` — pass, no findings
- `mypy src --strict` — pass, no issues in 21 source files
- `pytest tests -q` — **238 passed**, matching the implementer's reported count exactly
- `git status --short` — clean; all Stage 1-4 files are committed, nothing left unstaged
- No debug prints or TODO/FIXME/XXX markers introduced in the changed files (one pre-existing
  legitimate `print()` in `console.py`'s own output-writing path, unrelated to this change)

### Required Fixes

None.

### Optional Refinements

- `implementation.md`'s "Notable Discoveries" note that `FoldOutcome.contradicted` is used only for
  the lockout timestamp, and `classification_event` re-derives direction independently from
  before/after level+value. This is a reasonable simplification (confirmed correct by hand-tracing
  `_collapse`'s guarantee that a genuine same-level disagreement always produces a strictly lower
  level), but it does mean two different code paths encode "was this a contradiction" using two
  different definitions that happen to agree by construction rather than by shared logic. Worth a
  one-line comment cross-referencing the other, if a future stage ever changes `_collapse`'s
  collapse target — not blocking now, since both are separately tested.
- `_classification_facts` in `tools.py` renders `level` via `classification.level.name.lower()`
  (`"unknown"`/`"presence"`/`"class"`/`"type"`). Fine as-is; just flagging that this string is now
  part of the brought-forward-toward-§3.4 tool surface, so a future rename of `SpecificityLevel`'s
  members would be a silent API break for any brain-facing consumer — not this pass's concern, but
  worth a note when BL-5 freezes the surface.

### Verdict

**APPROVED**

Ready to proceed to Stage 5 (live acceptance) — this needs the user in the cockpit, not another
Implementer pass. No required fixes; the two optional notes above are forward-looking and do not
block.

### Review Confidence

Full read. Read the plan and implementation log in full; read every Stage 1-4 diff hunk directly
(not just the implementer's summary); hand-traced the fold table's edge cases against the code;
independently ran and confirmed all four verification commands and the "Stage 6 boundary" claim via
`git diff --stat`.

---

## Review: BL-2.6 Stages 6-7 (classification-refinement)

Commits reviewed: `6bea387` (Stage 6, mechanism), `479067a` (Stage 7, calibration).
Scope: naked-eye achieved-tier classification (mechanism) + moving the gating tier medres→lowres
(calibration), kept in separate commits per the plan's "mechanism and calibration never share a
commit" rule. Stages 8-10 (live acceptance #2, tuning, docs) explicitly out of scope for this pass.

### Review Summary

Both commits do exactly what their stage promises, and the mechanism/calibration split is real,
not just claimed in prose — verified directly against the diffs, not the implementer's log.

Verified directly against the code:

- **Stage 6 is pure mechanism.** `6bea387`'s diff touches only `perception/naked_eye_source.py`,
  `perception/visibility.py`, and their tests. `NAKED_EYE_GATING_ANGULAR_RADIUS_RAD` and
  `NAKED_EYE_GATING_TIER_NAME` are byte-for-byte unchanged in that commit (confirmed by reading the
  full diff hunk) — the gate stays `medres`, so `_achieved_tier`'s `"lowres"` branch is genuinely
  dead code this commit, as both the plan and implementation.md claim. The Stage 6 test suite (5 new
  tests) passes with no rewrite of any pre-existing assertion, consistent with "the only new
  behaviour is close targets sometimes resolving to type instead of a confidence bump."
- **Stage 7 is pure calibration, cleanly separable and revertible.** `479067a`'s diff to
  `visibility.py` is exactly the two-constant reassignment
  (`MEDRES_ANGULAR_RADIUS_RAD`/`"medres"` → `LOWRES_ANGULAR_RADIUS_RAD`/`"lowres"`) plus its comment;
  no other production line changed. The commit is a one-line semantic revert (as its own comment
  states), matching the plan's Stage 7 description. Test changes are the necessary consequence of
  the moved boundary, not scope creep.
- **`_classification_for_tier`'s hires→type fallback is real, not just claimed.** Confirmed directly
  against `dcs_type_to_reporting_name.tsv`: bare `"Infantry"` has no exact row, only compound entries
  (`Infantry AK`, `Infantry AK Ins`, `Infantry AK ver2/3`), so `reporting_name_for("Infantry")`
  returns `None` and the code falls back to `op_class` at level 2. This exact path is exercised by
  `test_hires_range_candidate_with_no_reporting_name_falls_back_to_class`, which asserts
  `classification_raw == "OP_INFANTRY"` and `classification_level == 2` at hires range (300 m) — a
  real fallback, not an unreached branch.
- **`NAKED_EYE_TYPE_CONFIDENCE = 0.55 < association.CONFIDENT_ASSOCIATION_CONFIDENCE = 0.6`**
  confirmed by direct grep of `perception/association.py`. The invariant ("no naked-eye tier, however
  close, reaches real-detection confidence") holds at the type tier, the closest/highest one, so it
  holds at all three.
- **Presence-tier reachability is genuinely end-to-end.** `test_lowres_range_candidate_reaches_presence_level`
  builds a full `NakedEyePerceptionSource` via `_source(world_objects)` and calls `.poll(...)` — this
  exercises `naked_eye_source.py`'s `poll` → `_build_observation` → `_classification_for_tier` path
  and `visibility.check_visibility`'s gate together, not `visibility.py` in isolation. It asserts
  `classification_raw == object_model.DEFAULT_OP_CLASS` and `classification_level == 1`, genuinely
  proving level-1/PRESENCE_CLASS is emitted through the real pipeline.
- **Worked-table numbers cross-checked against the plan by hand, not trusted from the diff.** Infantry
  (size 1.8 m): hires threshold `1.8/0.02*4.0 = 360 m`, medres `1.8/0.008*4.0 = 900 m`, lowres
  `1.8/0.0043*4.0 = 1674.42 m` — all three match the plan's worked table and the test boundaries
  (1674/1675 m). Ural truck (size 6 m): lowres threshold `6/0.0043*4.0 = 5581.4 m`, which exceeds
  `NAKED_EYE_RANGE_CAP_M = 5000 m` — confirming the premise inversion the rewritten
  `test_ural_truck_gate_now_binds_at_the_range_cap_under_lowres` asserts (cap binds, not the size
  curve) is correct, matching the plan's own Risks section on the flattened size curve at the cap.
- **Nothing in Stages 6-7 touched `belief/`.** `git diff --stat 4ed2526..7160ecc -- body-layer/src/belief/
  body-layer/src/perception/` shows changes confined to `perception/naked_eye_source.py` and
  `perception/visibility.py` only (plus their tests, checked separately) — no BL-2.6 Stage 1-4
  mechanism (`contacts.py`, `classification.py`, `events.py`) was touched.

### Verification commands (run directly, body-layer venv)

- `ruff format --check src tests` — pass (42 files already formatted)
- `ruff check src tests` — pass, no findings
- `mypy src --strict` — pass, no issues in 21 source files
- `pytest tests -q` — **245 passed**. Reconciled independently: 238 baseline (Stages 1-4) → 243 after
  Stage 6 (+5 new tests, no rewrites, gate unchanged) → 245 after Stage 7 (net +2: one pre-existing
  test — the old "infantry just outside medres" boundary test — replaced by two new boundary tests
  (just-inside/just-outside-lowres), plus one new end-to-end presence-tier test in
  `test_naked_eye_source.py`; the Ural-truck and ship-cap tests were rewritten in place, not added).
  Matches the implementer's reported delta exactly.
- `git status --short` — clean; both stages' files (plus the implementation-log and agent-memory
  commits that followed) are committed, nothing left unstaged.

### Required Fixes

None.

### Optional Refinements

- `_CLASSIFICATION_LEVEL_CLASS`/`_CLASSIFICATION_LEVEL_TYPE` in `naked_eye_source.py` are bare-int
  mirrors of `belief.classification.SpecificityLevel`, correctly kept as bare ints per the
  `perception/`-must-not-import-`belief/` boundary. `_classification_for_tier`'s final `return
  object_model.DEFAULT_OP_CLASS, 1` uses a literal `1` instead of a named constant the way the other
  two branches use `_CLASSIFICATION_LEVEL_CLASS`/`_CLASSIFICATION_LEVEL_TYPE` — the docstring above it
  explains why `_CLASSIFICATION_LEVEL_PRESENCE` isn't declared yet (unreachable until Stage 7), but
  Stage 7 has now landed and made it reachable without adding the constant. Purely cosmetic
  inconsistency (the value is correct and tested); worth a one-line follow-up naming it, not blocking.
- The Stage 6/7 split leaves `_achieved_tier`'s `"lowres"` branch and `NAKED_EYE_PRESENCE_CONFIDENCE`
  declared a full commit before they're reachable, which is exactly what the plan asked for
  (independently revertible, mechanism-first) — noting only that a future `git bisect` landing exactly
  on `6bea387` will see unreachable code with no test covering it, which is expected and already
  called out in `implementation.md`, not a gap to fix.

### Verdict

**APPROVED**

Stages 6-7 are correctly scoped, correctly separated (mechanism vs. calibration), and match the
plan's worked table exactly. Per the plan and the task's own instruction, **do not proceed to DoD**
— Stage 8 (live acceptance #2) is required and needs the user in the cockpit, which is unavailable
right now (Windows box down). Stages 9-10 (tuning, docs) also remain outstanding and depend on
Stage 8's feedback. The branch should stop here and wait.

### Review Confidence

Full read. Read both commits' full diffs directly (not just implementation.md's summary); verified
the mechanism/calibration separation by inspecting exactly which lines each commit touches;
hand-computed all worked-table thresholds independently against the plan's numbers rather than
trusting the diff's comments; confirmed the reporting-name fallback against the actual TSV data file;
independently ran and reconciled the full verification suite and test-count delta.
