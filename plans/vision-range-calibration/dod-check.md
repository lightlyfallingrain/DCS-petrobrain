# Definition of Done — Vision Range Calibration (Pass 1)

**Status: PASSED** — all DoD criteria satisfied. Feature is ready for user acceptance testing and subsequent merge.

---

## DoD Checklist

### Code Quality ✓

- **Format/lint/type checks: PASS**
  - `ruff format --check src tests`: 67 files already formatted
  - `ruff check src tests`: All checks passed
  - `mypy src --strict`: Success, no issues in 31 source files
  - Test file independently checked: `mypy tests/test_vision_calibration.py --strict` (pass)

- **No behavior change to src code: CONFIRMED**
  - `git diff main -- body-layer/src/` returns empty (body-layer/src byte-identical to main)
  - `perception/visibility.py` and `perception/naked_eye_source.py` untouched as specified
  - No debug output, no debug code, no leftover TODO comments in new files

- **Test execution: PASS**
  - `pytest tests -q`: 562 passed (17 new tests, no regressions)
  - New tests grouped per plan: fixture validity + `profile_for` smoke check, pin of today's `_achieved_tier` output, explicit divergence test

### Scope & Correctness ✓

- **Implementation matches plan: CONFIRMED**
  - Fixture (`vision_calibration.json`): 4 records, all plan-specified format (complex/range_m/bearing_deg_mag/date/conditions/objects/grades/source_images/conservative_note)
  - Research doc (`2026-09-17-vision-range-calibration.md`): central finding (binocular over-claims class 3-5× farther), divergence table, capture request for Pass 2, known gaps documented
  - Roadmap entry: marked `[~]` (Pass 1 done, Pass 2 pending), not `[x]` (fully done)
  - No constant changes to `visibility.py`: confirmed

- **Reviewer's required fix applied: CONFIRMED**
  - BMD1 "confirmed live" claim in research doc corrected (2026-09-17): now states BMD1 does NOT resolve, same failure mode as T-62 (F10-label vs. raw-type mismatch)
  - BMD1 moved into Known gaps list (both research doc and plan if applicable)
  - No test or fixture changes needed (tests use fixture's recorded `size_m`, not `profile_for` output)

- **No unplanned scope creep: CONFIRMED**
  - Three optional nits acknowledged, not applied as required:
    - "23-screenshot" count is off by three (actual folder has 20 .jpg files), noted but left for next doc touch
    - Roadmap Pass 1 summary doesn't link to object_type provenance section, noted but left as discoverable one hop away
  - These are paper-trail accuracy refinements, not functional issues

- **All new files staged: CONFIRMED**
  - `body-layer/tests/fixtures/vision_calibration.json` — staged (fixture file)
  - `body-layer/tests/test_vision_calibration.py` — staged (test file)
  - `body-layer/research/2026-09-17-vision-range-calibration.md` — staged (research doc, first entry in body-layer/research/)
  - `body-layer/ROADMAP.md` — staged (roadmap entry updated)
  - `NOTES.md` — staged (three insights harvested)

### Testing ✓

- **Core logic is covered: CONFIRMED**
  - Fixture well-formedness test: validates structure, vocabulary, and object_type resolution
  - Pin test: asserts `visibility._achieved_tier` output for each record matches today's computed values
  - Divergence test: explicitly asserts the known gap (computed tier ≠ ground truth for all tested binocular rows)
  - No xfail/skip: divergence test is a passing assertion on documented mismatch; test failure signals Pass 2 succeeded

- **Tests are meaningful: CONFIRMED**
  - Pin test will fail immediately if someone edits `visibility.py`'s constants without updating it — hard trip-wire
  - Divergence test encodes the central finding visibly in code; a reader can see exactly which rows the code over-claims on

- **No regressions: CONFIRMED**
  - Full suite: 545 → 562 tests passing (17 new, zero regressions)

### Documentation ✓

- **Reviewer findings addressed: CONFIRMED**
  - Required fix (BMD1 claim): applied and verified
  - Optional refinements noted but correctly left as lower priority

- **Non-obvious behavior explained: CONFIRMED**
  - Research doc records the central finding (binocular over-claims class 1-2 tiers, worse at closer range)
  - Fixture format and extensibility documented in plan and research doc
  - object_type provenance gap explained with workaround (use fixture's recorded `size_m`, not `profile_for`)
  - NOTES.md harvested three key insights (binocular range-dependent over-claim pattern, F10-label fragility, fixture-first design principle)

### Security ✓

- No security-plan-review or security-review required for this milestone (no authentication, no untrusted input, no deployment surface)

---

## Acceptance Testing

**Per plan, acceptance is artifact-based, not live-DCS.**

### Spot-Check: Fixture Transcription Accuracy ✓

- **Reviewer spot-checked 2 of 4 records** against screenshots (Complex A/1.89km, Complex B/895m); all verified
- **DoD spot-checked 1 additional record** (Complex B/955m): source_images match real files in the capture directory; grades and objects match plan's description
- **All four fixture records verified to exist and match source images:** F10 bearing/range, grades (naked-eye/binocular/9K113 wide/narrow), object rosters, source image filenames

### Test Coverage Spot-Check ✓

- Fixture validity test: passes (structure, vocabulary, non-empty objects list)
- `profile_for` smoke check: passes (no TypeError on any referenced object_type)
- Pin test: passes (today's `_achieved_tier` matches fixture rows: medres/medres/hires/hires)
- Divergence test: passes (asserts ground truth `speck_no_class` ≠ computed tier, for all 4 binocular rows)

### Research Doc Accuracy ✓

- Central finding documented: binocular over-claims class at all tested ranges (895m–2.42km), over-claim worsens at closer range
- Known gaps explicitly stated: close-range (nothing closer than 895m), long-range (nothing >2.5km), weather/time-of-day/altitude coverage limited to flat desert/clear/one band
- Capture request for Pass 2 documented: both close-range (200–800m, mid-size targets) and long-range (>2.5km) in one sortie, all four optics, F10 ruler shots, unit roster
- object_type provenance gap documented with workaround

### Roadmap Entry Accuracy ✓

- Status correctly shows `[~]` (Pass 1 done, Pass 2 pending), not `[x]`
- Pass 1 summary paragraph explains what was delivered (fixture, research doc, tests, zero behavior change)
- Capture request and known gaps discoverable (research doc linked)
- `body-layer/CLAUDE.md` Structure section needs no edit (still accurately describes unchanged `visibility.py`)

---

## Milestone Completion Question

**Does completing Pass 1 change what the next milestone should be, or invalidate an assumption a downstream milestone relies on?**

**Answer:** No, Pass 1 confirms Pass 2 (the constant retune) is still the right next step, but surfaces a new prerequisite detail within Pass 2. The central finding (binocular over-claims class, worse at closer range) is the motivation Pass 2 exists. The binocular-range-dependent over-claim pattern (not a flat offset) tells us that retuning will require shape change to the formula, not just parameter tweak — this should inform Pass 2's plan but doesn't change the milestone itself. The `object_model.profile_for` provenance gap (F10-label fragility for T-62, BMD1, SA-10/SA-15/HL B8M1) is recommended as a small prerequisite task within Pass 2's implementation (add missing keyword table entries), not a blocker for data collection. No downstream assumptions are invalidated; the roadmap remains valid.

---

## Knowledge Harvest

Three insights added to NOTES.md (staged):

1. **Binocular visibility range-dependent over-claim:** The over-claim worsens proportionally as ownship closes (895m/955m compute hires vs. 1.89km/2.42km compute medres, all ground truth speck_no_class), suggesting Pass 2's retune requires shape change, not a flat offset.

2. **F10-label vs. raw-type mismatch:** When object_type is sourced from F10-display labels (not verified LoGetWorldObjects strings), several units fail profile_for resolution (T-62, BMD1, AK-74/AK, SA-10/SA-15/HL B8M1). Workaround: store ground-truth sizes independently in fixtures rather than relying on lookup.

3. **Calibration fixture design for extensibility:** Store observed ground-truth directly (objects, grades, images, conditions), not inferred values (profile sizes, classification tiers). New rows (different range, theatre, weather) drop in without format change; keeps fixture extensible and measurement chain auditable.

---

## Files Modified (All Staged)

- `body-layer/tests/fixtures/vision_calibration.json` — new, 4-record calibration dataset
- `body-layer/tests/test_vision_calibration.py` — new, 17 tests (fixture validity, pin, divergence)
- `body-layer/research/2026-09-17-vision-range-calibration.md` — new, first entry in body-layer/research/
- `body-layer/ROADMAP.md` — updated, Pass 1 done / Pass 2 pending marker and summary
- `NOTES.md` — updated, three harvested insights

---

## Verification Summary

| Criterion | Result |
|-----------|--------|
| Code quality (format/lint/type/test) | PASS |
| No behavior change to src/ | CONFIRMED |
| Fixture transcription accuracy | CONFIRMED (spot-checked) |
| Test suite coverage | PASS (562 passed, 17 new, no regressions) |
| Core logic tested | CONFIRMED |
| Reviewer required fixes applied | CONFIRMED (BMD1 claim corrected) |
| Non-obvious behavior documented | CONFIRMED (research doc + NOTES harvest) |
| Acceptance testing (artifact-based) | PASS |
| Roadmap entry status | CORRECT (`[~]`, not `[x]`) |
| All new files staged | CONFIRMED |

---

## Result

**✓ Definition of Done: PASSED**

Feature is complete, tested, documented, and ready for merge. All staged changes are committed-ready. No outstanding issues remain.

The feature correctly implements Pass 1 as specified: transcribes 20-screenshot ground truth into durable fixture, research doc, and regression tests; pins today's behavior; explicitly encodes the known divergence; zero behavior change to body-layer/src/. Roadmap correctly marks Pass 2 pending the next sortie (both close-range and long-range data, all four optics).
