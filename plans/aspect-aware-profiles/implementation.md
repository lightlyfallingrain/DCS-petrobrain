### Implementation Summary

Implemented the plan as written: `ObjectTypeProfile` gained optional `length_m`/`width_m`/
`height_m` (default `None`, `size_m` unchanged and still required), a new
`object_model.apparent_extent_m(profile, aspect_deg)` formula, real sourced dimensions on the two
S-300 rows only, `heading_true_deg` on `WorldObjectCandidate` following `is_ownship`'s tri-state
precedent, and `visibility.check_visibility` wired to compute aspect and use the new formula for
both the range-threshold gate and `_achieved_tier`. `clustering.py` untouched per the plan's
explicit scope cut. `LOWRES`/`MEDRES`/`HIRES_ANGULAR_RADIUS_RAD` untouched.

### Files Changed
- `body-layer/src/perception/object_model.py` — `ObjectTypeProfile` gains
  `length_m`/`width_m`/`height_m: float | None = None`; new `apparent_extent_m()` function; two
  new keyword rows for the real DCS `object_type` strings `"S-300PS 40B6M tr"` and
  `"S-300PS 64H6E sr"` with real dimensions and `op_class="OP_LRSAM"` (ED's long-range SAM
  bucket, distinct from the existing `OP_SRSAM`/`OP_MRSAM` rows). Module docstring updated.
- `body-layer/research/2026-09-21-s300-radar-dimensions.md` — new. Sourcing/citations for both
  rows' dimensions (see "Notable Discoveries" below for what was and wasn't found).
- `body-layer/tests/fixtures/object_type_coverage_sample.json` — the two S-300 entries'
  `expected_op_class` changed from `null` to `"OP_LRSAM"`, matching the new keyword rows (this
  fixture's own mismatch-detection test would otherwise fail now that these two types resolve to
  a real class instead of the fallback).
- `body-layer/src/perception/association.py` — `WorldObjectCandidate` gains
  `heading_true_deg: float | None = None`; `from_dict` populates it from the wire's
  `heading_true_rad` (radians → degrees, converted once at the same boundary lat/lon already
  convert).
- `body-layer/src/perception/visibility.py` — new private `_aspect_deg(candidate_heading_true_deg,
  candidate_bearing_deg) -> float | None` helper (wrap-to-`[0,180]`, same delta-wrap pattern
  `association._within_forward_hemisphere` already uses); `check_visibility` computes it once and
  calls `object_model.apparent_extent_m(profile, aspect_deg)` once, using the result
  (`candidate_extent_m`) for both the size-curve range threshold and the `_achieved_tier` call —
  replacing the two separate `profile.size_m` reads. Module docstring's gate-#3 section updated.
- `body-layer/tests/test_object_model.py` — new tests for `apparent_extent_m` (nose-on, broadside,
  45°, 135°, no-dimensions-at-any-angle including 45° via `pytest.mark.parametrize`,
  dimensions-but-unknown-aspect, and a full sweep of real un-migrated table rows at 45°), plus two
  tests pinning the S-300 rows' real dimensions and `op_class`.
- `body-layer/tests/test_visibility.py` — `_candidate` helper gains an optional
  `heading_true_deg` parameter; new tests: broadside vs. nose-on resolve to different
  tiers/thresholds, `heading_true_deg=None` reproduces the pre-aspect scalar behaviour exactly
  (regression guard), and a synthetic monkeypatched tall-mast profile (independent of the real
  S-300 sourcing) pins the radar fix directly. Uses a `dimensioned_profile_lookup` fixture that
  monkeypatches `object_model.profile_for` for two private test-only `object_type` strings.

### Tests Added
- `test_apparent_extent_nose_on_is_the_narrow_width` / `..._broadside_is_the_long_length` — the
  two axis-aligned angles, for orientation.
- `test_apparent_extent_at_45_degrees_is_the_true_trig_projection` — the plan's mandated
  non-axis-aligned check; asserts against the real trig value, not a naive average or the
  un-projected `size_m`, either of which a broken formula could coincidentally produce.
- `test_apparent_extent_at_135_degrees_mirrors_45` — a second oblique angle.
- `test_apparent_extent_without_dimensions_returns_size_m_unchanged` (parametrized over 7 angles
  including 45°) — the regression guard for the original cubic-fallback defect.
- `test_apparent_extent_with_dimensions_but_unknown_aspect_returns_size_m` — `aspect_deg=None`
  case.
- `test_every_unmigrated_table_row_is_unaffected_by_aspect` (parametrized) — sweeps 7 real,
  currently-shipped `object_type`s through `profile_for` + `apparent_extent_m` at a real oblique
  angle, confirming the ~150 unmigrated rows really carry no dimensions.
- `test_s300_40b6m_tr_has_real_dimensions_and_op_lrsam` / `test_s300_64h6e_sr_...` — pin the two
  migrated rows' sourced figures and class.
- `test_broadside_and_nose_on_headings_resolve_to_different_visibility` — same profile/range, two
  headings, two different gate outcomes.
- `test_unknown_heading_reproduces_the_pre_aspect_scalar_behaviour` — regression guard, mirrors
  cones-slice-1's own "must not change the default" pattern.
- `test_tall_mast_shaped_profile_is_visible_past_its_old_scalar_threshold` — synthetic profile
  (not the real S-300 keyword row) pins the fix mechanically.

### Checks
(body-layer/ only — no other subproject touched)
- ruff format --check: pass
- ruff check: pass
- mypy src (strict): pass, 0 errors (tests/ is not `--strict`-checked per this subproject's own
  convention/CLAUDE.md Commands section; pre-existing tests/ errors unrelated to this change were
  confirmed present before touching anything and left alone)
- pytest -q: pass, 769 passed (745 before this change + 24 new), including
  `test_vision_calibration.py` (46 passed) run standalone to confirm the plan's "no code change
  expected" claim directly, not assumed

### Notable Discoveries
- **The plan's "four test files construct `WorldObjectCandidate` directly" claim was half right.**
  Only `test_association.py` and `test_detection_trace.py` actually construct it via a literal
  call; `test_naked_eye_source.py` and `test_mock_flight_chain.py` go through `.from_dict`
  (dicts/JSON fixtures) instead. None of the four needed editing in the end — `heading_true_deg`'s
  `None` default made every existing call site (literal or `from_dict`) keep passing unchanged, as
  the plan's own "everywhere else" clause predicted, so this discrepancy had no practical
  consequence, but it's worth recording that the plan's own file inventory wasn't quite accurate on
  *why* each file needed checking.
- **S-300 dimension sourcing came up short on two figures, exactly as the plan anticipated.** No
  published figure was found for the 40B6M mast trailer's own stowed footprint, or for the 64H6E
  antenna's erected (not stowed) height — both are explicitly flagged as rough estimates in the
  research doc rather than presented as sourced fact. For 64H6E's height specifically, the sortie's
  own in-game visual estimate ("~10 m") was used per the plan's own explicit fallback instruction,
  and is arguably more directly relevant than a real-world figure would be, since
  `apparent_extent_m` governs detectability of the DCS-rendered asset, not the physical original.
  Both estimates are low-consequence: height dominates the 40B6M row's formula output at every
  aspect regardless of the footprint estimate's precision (24 m vs. a few metres), and length/width
  for 64H6E did get a real citation (Army Recognition, 13.2 m × 3.0 m).
- **`OP_LRSAM` is an existing, documented-but-previously-unused ED class bucket** — the full
  vocabulary (`OP_SRSAM`/`OP_MRSAM`/`OP_LRSAM`) was already recorded in
  `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`, but no
  keyword row had used `OP_LRSAM` before this pass — the two S-300 (SA-10, a long-range system)
  rows are its first real use.
- Confirmed, not just assumed: the `object_type_coverage_sample.json` fixture needed its two S-300
  entries' `expected_op_class` updated from `null` to `"OP_LRSAM"` — without this the fixture's
  mismatch-detection test would have failed (a real, expected consequence of the two rows leaving
  the fallback bucket, not a bug).

### Correction (2026-09-21, post-DoD): aspect feeds recognition only, never detection

New flight data (`body-layer/research/2026-09-21-aspect-magnification-and-distinctiveness.md`,
Finding 1) contradicted a premise this branch had already merged and DoD-passed: a four-instrument
BTR-60 measurement found presence identical at every aspect (1.00x ratio, 90° vs. 0/20° AOB, across
binoculars and both 9K113 FOV settings) while class/type moved by 1.33x-2.31x. As merged,
`check_visibility`'s range-admission gate and `_achieved_tier`'s `lowres` tier both used the
aspect-aware `apparent_extent_m`, which the data says is wrong — detection is a contrast event
driven by presented area, not by which silhouette the object turns; recognition is a shape event
and needs the shape.

**Fix, narrow and targeted:**
- `check_visibility`'s range-admission gate now uses `profile.size_m` (aspect-invariant), not
  `apparent_extent_m` — reverted to exactly the formula this branch found before the aspect work.
- `_achieved_tier` gained a second required parameter: `presence_size_m` (drives the `lowres`
  threshold, now computed explicitly rather than left as an implicit "anything left over"
  fallback) and `recognition_extent_m` (drives `medres`/`hires`, where the aspect effect belongs).
  Explicit computation for `lowres` — instead of the previous implicit `else` branch — was the
  deliberate fix for the coherence risk the coordinator flagged: with two different size measures
  now in the same function, an implicit fallback could silently drift out of sync with the gate's
  own arithmetic on a future edit; an explicit threshold, fed the identical value the gate uses,
  cannot.
- `test_vision_calibration.py`'s one direct `_achieved_tier(...)` call site was updated to pass
  the same `_largest_size_m(record)` value for both new parameters — correct, not just
  mechanically necessary: the screenshot ladder carries no aspect data, so this is exactly what
  `apparent_extent_m(profile, None)` itself falls back to.
- Two tests from the original pass tested exactly the now-fixed defect (aspect changing
  admission/`lowres`) and were rewritten, not just patched: gate/`lowres` behaviour is now
  identical across headings by construction, so their assertions were re-pointed at the
  `medres`/`hires` tier difference aspect actually produces. A new
  `test_detection_range_is_invariant_under_aspect` was added — the explicit regression guard for
  this defect, swept across headings including non-axis-aligned ones (45°/135°), mirroring the
  plan's own "no axis-aligned-only test" rule from the other direction.

**Files touched:** `body-layer/src/perception/visibility.py` (gate + `_achieved_tier` + module
docstring gate-#3 section, which had drifted to describe the wrong, now-reverted gate formula),
`body-layer/tests/test_visibility.py` (2 tests rewritten, 1 added), `body-layer/tests/
test_vision_calibration.py` (1 call site updated to match the new required-parameter signature —
this file's numbers/behaviour are unchanged, only the call shape).

**Checks:** `ruff format --check` pass, `ruff check` pass, `mypy src` (strict) pass, `pytest -q`
pass — 770/770 (769 before this correction + net 1: 2 old tests replaced, 3 new/rewritten in
their place... net +1 file-wide after accounting for the parametrized sweep folding into a single
new test rather than N).

**Nothing incoherent found in splitting the two size measures once made explicit.** The one risk
worth naming for a future reader: `apparent_extent_m` is not guaranteed `>= profile.size_m` at
every aspect (for a profile where `size_m` is hand-set to the *largest* of `length_m`/`width_m`/
`height_m`, a nose-on view can project to less than that maximum on the other two axes) — so
`medres`/`hires` thresholds computed from it are not mathematically guaranteed to nest inside the
`size_m`-derived `lowres` threshold the way the single-size-measure version trivially did. In
practice this doesn't bite: `MEDRES_ANGULAR_RADIUS_RAD`/`HIRES_ANGULAR_RADIUS_RAD` are both several
times larger than `LOWRES_ANGULAR_RADIUS_RAD`, so `recognition_extent_m` would have to exceed
`presence_size_m` by a wide margin before a `medres`/`hires` threshold could exceed the `lowres`
one — not observed in any profile in the real table, including the two S-300 rows. Flagged rather
than fixed, since fixing it would mean clamping `apparent_extent_m`'s output against `size_m`,
which is a model-shape decision outside this correction's narrow scope.
