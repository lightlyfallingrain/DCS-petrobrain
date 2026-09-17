### Review Summary (see Required Fixes — the `object_type` provenance finding contains a reproducible factual error)

Pass 1 of vision range calibration (`0c0b03a..af2f58b`, branch `feature/vision-range-calibration`)
does what the plan asked: transcribe the 23-screenshot ground truth into a durable fixture,
research doc, and regression tests, with **zero behaviour change**. Verified directly, not on
trust:

- `git diff main -- body-layer/src/` is empty — `visibility.py`/`naked_eye_source.py` genuinely
  untouched.
- Spot-checked two fixture records against the actual screenshots (Complex A/1890m, Complex
  B/895m): F10 ruler bearing/range (`274°/1.89km`, `059°/0.895km`), naked-eye grade (`nothing`,
  `marginal_speck`), and binocular grade (`speck_no_class` both rows) all match the images exactly.
- Ran `body-layer`'s full verification sequence myself: `ruff format --check` (67 files
  formatted), `ruff check` (all checks passed), `mypy src --strict`-equivalent config (31 files,
  no issues), `pytest -q` — **562 passed**, matching the implementation log's reported count.
- `git status` clean for this feature's files; only unrelated `world-model/` artifacts are
  untracked (not part of this diff).
- Grade vocabulary matches the plan exactly (`nothing`/`marginal_speck`/`speck_no_class`/
  `class_recognizable`/`type_recognizable`, `null` for unphotographed optics). Fixture record
  shape (complex/range_m/bearing_deg_mag/date/conditions/objects/grades/source_images/
  conservative_note) is generic enough that a new row — closer range, different theatre/weather/
  altitude — drops in without a format change, as the plan requires.
- The three required tests are present and do what the plan specified: fixture well-formedness +
  `profile_for` smoke check, a pin test on today's `_achieved_tier` output, and an explicitly-named,
  non-`xfail` divergence test (`test_known_divergence_binocular_overclaims_class`). The pin test's
  inline comment ("Pinned today, 2026-09-17, against visibility.py as it stands...") and the
  module docstring's explanation of why a future failure here is *expected* and *good* (Pass 2
  succeeded) make a future assertion failure self-explaining rather than a mysterious regression —
  this reads as Pass-2-friendly.
- The `object_type` provenance finding (units falling through to `object_model.DEFAULT_SIZE_M` via
  F10-label lookup, beyond the SA-10/SA-15/HL B8M1 gap the plan already flagged) is real for T-62
  and AK-74/AK, reproduced directly (`profile_for("T-62")` → `5.0/OP_GROUPSOMETHING`). **But the
  research doc's BMD1 claim is wrong — see Required Fixes.** The workaround itself — recording
  `size_m` as independently-known ground truth in the fixture rather than `profile_for`'s resolved
  value — is sound regardless, not a laundered bug: the fixture's own `_comment` field states this
  explicitly, and the pin/divergence tests consume the recorded `size_m` directly, never
  `profile_for`'s output, so this doesn't affect test correctness.
- Scope: nothing beyond Pass 1 crept in. The roadmap `[~]` entry accurately separates what Pass 1
  delivered from what Pass 2 still needs (the capture request, both gaps).

### Required Fixes

- **Research doc's BMD1 "confirmed live" claim is factually wrong — reproduced, not just doubted.**
  `body-layer/research/2026-09-17-vision-range-calibration.md` lines 67-72 state: *"`profile_for
  ("BMD1")` in fact returns `OP_ARMORED`/7.0 correctly"* and cites this as the reason BMD1 is
  omitted from the "Known gaps" list (only SA-10SR/SA-10C2/SA-10TR/SA-15/HL B8M1/T-62/AK-74/AK are
  listed as unresolved). I ran it directly against the code on this branch:
  ```
  profile_for("BMD1") -> size_m=5.0, op_class='OP_GROUPSOMETHING'
  ```
  The doc's own two-pass description of `profile_for` (lines 358-393 of `object_model.py`) explains
  why: `"bmd"` is a keyword only in `_REPORTING_NAME_KEYWORD_PROFILES` (the *second*-pass table,
  matched against the resolved reporting name), not in `_KEYWORD_PROFILES` (first-pass, matched
  against the raw string directly) — so pass 1 never matches `"bmd1"`, and pass 2 requires
  `reporting_name_for("BMD1")` to succeed first. It doesn't: `reporting_name_for("BMD1")` returns
  `None` (the raw-type table's key is `"BMD-1"`, hyphenated; the F10 label used in this fixture,
  `"BMD1"`, has no hyphen and isn't a recognized key). `reporting_name_for("BMD-1")` does resolve —
  confirming the doc's own diagnosis of the T-62 case (F10-label vs. raw-type-string mismatch)
  applies identically to BMD1, contradicting its stated conclusion for that one unit.
  **Fix**: correct the research doc's BMD1 paragraph to state it does *not* resolve (same failure
  mode as T-62), and move `BMD1` into the "Known gaps" list in both the research doc and the plan's
  cross-reference if one exists. This doesn't touch any test (the pin/divergence tests use the
  fixture's recorded `size_m`, not `profile_for`'s output, so nothing here is masked from Pass 2's
  actual behaviour) — it's a correctness fix to a documented-as-verified claim, not a fixture or
  test change. Research docs in this project are the durable, trusted record of verified-against-
  the-code findings; an incorrect "confirmed live" claim undermines that record for whoever reads
  it next (a future Pass 2 planner deciding whether BMD1's size needs fixing).

### Optional Refinements

- **"23-screenshot" claim is off by three.** The plan, research doc, and roadmap entry all say
  "23 screenshots," but `win-mac-sync/from-windows/target acquisition screenshots/` contains 20
  `.jpg` files (verified directly: `find ... -type f` returns 20 images + one `.DS_Store`). The
  "23" figure originates in the Architect's plan (pre-existing), and neither the implementer's
  direct image-reading pass nor the research doc's own restatement caught the discrepancy. Doesn't
  affect any test or fixture correctness — purely a paper-trail accuracy nit worth a one-line fix
  next time either doc is touched.
- **Object_type provenance gap isn't visible from the roadmap entry itself.** The roadmap's Pass 1
  summary paragraph doesn't mention the T-62/AK-74/BMD1 finding — a reader following only the
  roadmap (not opening the plan or research doc) won't see it. It is discoverable one hop away (the
  roadmap entry links both the plan and, implicitly via the research doc's existence, the finding),
  so this isn't required, but a future Pass-2 planning session would find it faster with one added
  clause in the roadmap's Pass 1 paragraph pointing at the research doc's "`object_type`
  provenance" section specifically (it currently only points at "Capture request for Pass 2").

### Verdict
APPROVED WITH MINOR FIXES — the one required fix is a documentation correction (research doc's
BMD1 claim), not a code, fixture, or test change; nothing here needs re-review of `src/` or the
test suite once corrected.

### Review Confidence
Full read — plan, implementation log, roadmap entry, fixture, test file, and research doc all read
in full; ran the complete verification sequence myself rather than trusting the reported numbers;
spot-checked 2 of 4 fixture records directly against the source screenshots (F10 ruler + naked-eye
+ binocular frames for both), including a live re-derivation of the `profile_for("T-62")` /
`profile_for("BMD1")` provenance claim.
