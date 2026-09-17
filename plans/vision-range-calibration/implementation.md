### Implementation Summary

Pass 1 of the vision range calibration plan: transcribed the 23-screenshot ground-truth dataset
into a durable fixture, wrote the research doc recording the central finding and divergence
table, and added regression tests that pin what `visibility.py` computes today against that
dataset. **No behaviour change** — `perception/visibility.py` and `perception/naked_eye_source.py`
are unmodified (confirmed via `git diff --stat`, zero lines changed in either file), per the
plan's "No constant changes this pass" decision.

Every screenshot referenced in the plan's dataset table was read directly (not transcribed
blind) to verify the grades before writing them into the fixture. All four rows (Complex A/1.89
km, Complex B/2.42 km, Complex B/0.955 km, Complex B/0.895 km) matched the plan's table exactly —
no grade was found to disagree with the images.

### Files Changed
- `body-layer/tests/fixtures/vision_calibration.json` (new) — the 4-record calibration dataset,
  in the plan's exact fixture format. `size_m` per object is recorded as independently-known
  real-world size (matching the plan's dataset table), not `object_model.profile_for`'s resolved
  value — see "Notable Discoveries" below for why those two differ for several units in this
  roster.
- `body-layer/tests/test_vision_calibration.py` (new) — three test groups per the plan's
  "Regression tests" section: fixture well-formedness + `profile_for` smoke check,
  `_achieved_tier` pin (using each record's largest recorded `size_m`), and an explicit,
  non-`xfail` divergence test (`test_known_divergence_binocular_overclaims_class`) asserting the
  documented gap between computed tier and ground truth.
- `body-layer/research/2026-09-17-vision-range-calibration.md` (new) — first entry in
  `body-layer/research/` (didn't exist before this pass). Records the graded dataset, the
  `object_type` provenance finding, the central finding's divergence table, the "no constant
  changes" rationale, the Pass 2 capture request, and known gaps.
- `body-layer/ROADMAP.md` — the "Vision range calibration" entry changed from `[ ]` (not started)
  to `[~]` (Pass 1 done, Pass 2 pending the next sortie), with a summary paragraph of what Pass 1
  delivered and a pointer to the research doc for the capture request. Per the plan's acceptance
  criteria, `body-layer/CLAUDE.md`'s Structure section needed no edit this pass — it still
  accurately describes `visibility.py`'s unchanged current behaviour.

### Tests Added
- `test_fixture_loads_and_has_records` — the fixture file loads and is non-empty.
- `test_fixture_record_is_well_formed` (×4, parametrized) — every record has the plan's required
  keys, a non-empty `objects` list with valid `object_type`/`size_m`, `grades` using only the
  defined vocabulary (or `null`), and a non-empty `source_images` list.
- `test_object_model_resolves_every_object_type` (×4, parametrized) — `profile_for` doesn't raise
  on any referenced `object_type` (smoke check against a typo, not a correctness claim — see
  Notable Discoveries).
- `test_pin_todays_achieved_tier` (×4, parametrized, non-null-binocular rows) — pins
  `visibility._achieved_tier(range_m, largest_size_m)` to today's actual output
  (`medres`/`medres`/`hires`/`hires` for the four rows).
- `test_known_divergence_binocular_overclaims_class` (×4, parametrized) — asserts every tested
  row's binocular ground truth (`speck_no_class`) diverges from the computed tier
  (`medres`/`hires`), encoding the plan's central finding as a passing, explicitly-named test.

17 new tests total; full suite went from 545 to 562 passing, no regressions.

### Checks
(body-layer/)
- ruff format --check: pass
- ruff check: pass
- mypy --strict (`cd body-layer && mypy src`): pass, 31 source files (test file also independently
  checked clean with `mypy tests/test_vision_calibration.py --strict`, though the project's
  Commands section only requires `src`)
- pytest -q: pass, 562 passed (17 new)

### Notable Discoveries

- **`object_type` provenance gap beyond what the plan already flagged.** The plan documents that
  SA-10SR/SA-10C2/SA-10TR/SA-15/HL B8M1 fall back to `object_model.DEFAULT_SIZE_M`/`DEFAULT_OP_CLASS`
  because they have no keyword-table entry. Verifying the fixture's object types against
  `profile_for` directly found the same failure mode hits two more units the plan's prose
  describes as correctly resolving: `"T-62"` (plan says "armored, 7 m") and `"AK-74"`/`"AK"` (plan
  says "1.8 m infantry") both actually resolve to the 5.0 m default today, because the only
  `object_type` strings available from these screenshots are DCS F10-map display labels, not
  verified raw `LoGetWorldObjects` strings — and the keyword table's second (reporting-name) pass
  only fires when the *raw* type string is a literal key in `dcs_type_to_reporting_name.tsv`
  (`"T-62M"`, not `"T-62"`). `"BMD1"` (no hyphen) *does* resolve correctly, by contrast, since it
  literally contains the raw-table's `"bmd"` substring keyword. Full writeup in the research doc's
  "`object_type` provenance" section. This does not affect the pin/divergence tests (which use the
  fixture's independently-recorded `size_m`, not `profile_for`'s output), but is a real accuracy
  gap for any future caller running these F10-style labels through the real pipeline — flagged as
  a Pass-2-adjacent fix, not blocking, mirroring the plan's own disposition for the SA-10/HL B8M1
  gap it already found.
- **All four tested divergence rows go the same direction and worsen at closer range** — the two
  closest rows (955 m, 895 m) compute `hires` (type claimed), two tiers past the `speck_no_class`
  ground truth, while the two farther rows (1.89 km, 2.42 km) only compute `medres` (one tier
  over). This is worth Pass 2's attention: the over-claim is not a flat offset, it's proportionally
  worse as ownship closes.
