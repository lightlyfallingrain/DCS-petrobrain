### Review Summary

Reviewed `feature/aspect-aware-profiles` (6 commits, `bc0f6bb`..`8d87b28`) against
`plans/aspect-aware-profiles/plan.md` (full read, including the coordinator-review correction) and
`implementation.md`. Full diff read for `object_model.py`, `association.py`, `visibility.py`,
`test_object_model.py`, `test_visibility.py`, the fixture edit, and the research doc.

**The caught defect has not returned.** `apparent_extent_m` returns `profile.size_m` verbatim
whenever any of `length_m`/`width_m`/`height_m` is `None`, checked independently of `aspect_deg`
(the `None`-dimensions branch is evaluated first and returns before the trig runs at all — there
is no code path where a dimensionless profile's return value depends on the angle). The ~148
un-migrated `_KEYWORD_PROFILES`/`_REPORTING_NAME_KEYWORD_PROFILES` rows are untouched source text —
confirmed by `git diff main...feature/aspect-aware-profiles -- object_model.py`, which shows only
insertions (module docstring, the new function, the two S-300 rows) and zero deletions/modified
lines elsewhere in the table. Only the two S-300 rows carry real L/W/H.

**The mandated non-axis-aligned test rule is genuinely satisfied.** `test_object_model.py` has an
explicit 45°/135° trig-projection test asserting against the actual computed `sin`/`cos` value
(not a naive average, not the un-projected `size_m`), a parametrized no-dimensions regression guard
swept over 7 angles including 45°, and a parametrized sweep of 7 real unmigrated table rows through
`apparent_extent_m` at those same 7 angles. I hand-verified the formula and its inverse-wrap case
independently (`_aspect_deg(10, 350) == 20`, `_aspect_deg(350, 10) == 20`) — correct. Re-introducing
the cubic fallback (`length_m=width_m=height_m=size_m`) would fail
`test_apparent_extent_without_dimensions_returns_size_m_unchanged` at every non-0/90 angle in the
parametrize list, and would fail `test_every_unmigrated_table_row_is_unaffected_by_aspect` the same
way — both are real, not decorative, regression guards for the specific defect.

**S-300 sourcing is honest at the research-doc level** — mast height (24 m) and 64H6E footprint
(13.2×3.0 m) are cited to named sources; the 40B6M footprint and the 64H6E erected height are both
explicitly flagged as estimates in `body-layer/research/2026-09-21-s300-radar-dimensions.md`,
including the circularity point (64H6E height reuses the same sortie's own visual estimate this
model will later be validated against). **This honesty does not survive into the code** — see
Required Fixes below.

`heading_true_deg` plumbing matches the `is_ownship` tri-state precedent exactly: `float | None`,
never coerced, converted once (radians→degrees) at the `from_dict` wire boundary. `_aspect_deg` is
called once per `check_visibility` invocation and its result reused for both the range-threshold
gate and `_achieved_tier` — no per-gate recomputation.

Scope is clean: `LOWRES`/`MEDRES`/`HIRES_ANGULAR_RADIUS_RAD` untouched (grep + diff confirm no
edits to those constants), `clustering.py` has zero diff, `test_vision_calibration.py` has zero
diff (confirmed by running it standalone: 46 passed, part of the 769).

Fixture edit (`object_type_coverage_sample.json`, two rows `expected_op_class: null` →
`"OP_LRSAM"`) is exactly the two migrated `object_type` strings and reflects the two new keyword
rows resolving to a real, pre-documented ED op-class bucket (`OP_LRSAM` already appears in
`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`'s op-class
table, independently confirmed) — not a test loosened to force a pass.

Ran the full body-layer verification sequence myself (`body-layer/.venv/bin/{ruff,mypy,pytest}`,
from `body-layer/`, per that subproject's `CLAUDE.md` Commands section and its mypy-CWD note):
`ruff format --check` clean, `ruff check` clean, `mypy src` (strict) 0 errors, `pytest tests -q` —
**769 passed**, confirming the implementation notes' claim exactly.

### Required Fixes

- **The estimate flag does not reach the code, only the research doc.** The plan's own S-300
  section and this review's priority 3 both require estimated figures to be "flagged loudly" where
  a future reader will see them. `object_model.py`'s table comment for the two S-300 rows says only
  "Sourcing/citations... see research doc" and the two trailing inline comments say "see research
  doc for sourcing" — undifferentiated for every field. A reader of `object_model.py` alone (which
  is the file anyone touching detection ranges will actually open) cannot tell that `length_m=10.0,
  width_m=3.0` on the 40B6M row and `height_m=10.0` on the 64H6E row are estimates while the other
  four numbers on those two rows are cited real-world figures. Add a per-row (or per-field) inline
  comment naming which specific values are estimated, e.g. `# length_m/width_m: estimated
  footprint, no published figure found — see research doc` and `# height_m: sortie's own in-game
  visual estimate ("~10 m"), not a published figure — see research doc`, so the estimate is visible
  without a doc hop.
- **The circularity in the 64H6E height estimate is invisible outside the research doc.** The
  64H6E `height_m=10.0` was derived from the 2026-09-21 sortie's own in-game visual estimate — the
  same sortie whose data this aspect-aware model will be checked against in the deferred threshold
  recalibration. The research doc states this plainly, but nothing in `object_model.py` or
  `visibility.py` carries the warning forward to whoever runs that recalibration and might
  otherwise read "S-300 detection now works right" as independent confirmation. A one-line comment
  on the 64H6E row (e.g. "height_m sourced from the same 2026-09-21 sortie this fix will later be
  validated against — not independent evidence") would close this without new process.

Both fixes are comment-only, low-risk, and do not touch behavior, tests, or the formula — safe to
apply directly without another Architect/Implementer round.

### Optional Refinements

- `test_broadside_and_nose_on_headings_resolve_to_different_visibility` and the two neighbouring
  aspect tests hardcode the expected threshold arithmetic in comments (e.g. "lowres threshold = 6 /
  0.003 * 1.0 = 2000 m") rather than computing it from the module's own constants. Harmless today,
  but if `NAKED_EYE_GATING_ANGULAR_RADIUS_RAD` or a tier boundary ever changes, these tests would
  need their comments (not just assertions) re-derived by hand. Not a blocker — the assertions
  themselves (`is None` / `tier == "lowres"`) don't depend on the hardcoded numbers being kept in
  sync, only the explanatory comments would go stale.
- The `dimensioned_profile_lookup` fixture monkeypatches `object_model.profile_for` module-wide for
  the duration of each test that uses it. Works correctly (verified `visibility.py` calls it via
  module attribute access, so the patch takes), but a docstring note that this only works because
  `check_visibility` calls `object_model.profile_for(...)` rather than an imported-by-name
  `profile_for` would save a future reader a few minutes if the import style in `visibility.py`
  ever changes.

### Verdict

APPROVED WITH MINOR FIXES

### Review Confidence

Full read — plan (including the coordinator-review correction), implementation notes, research
doc, full diff of every changed file, fixture diff, and the four priority-specific formulas
(apparent_extent_m branch order, `_aspect_deg` wraparound at two wraparound cases, the
`heading_true_rad` wire-schema requiredness, the `OP_LRSAM` pre-existing-vocabulary claim) each
independently verified rather than taken from the implementation notes. Full verification suite
(format/lint/mypy/pytest) re-run myself from `body-layer/.venv`, not assumed from the notes: 769
passed, matching.
