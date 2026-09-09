### Review Summary

Reviewed commits `e237ee4`, `ba6493c`, `2635bf5`, `e382ee4` against `plans/pb1.5-naked-eye-
detection/plan.md` (including the "Decisions — resolved 2026-09-09" section), scoped to stages
1, 2, 3, 6 only (4, 5, 7 correctly untouched; `hybrid_source.py`'s multi-contact gap correctly
left alone). Format/lint/type/test all pass per the user's independent run (79 passed); not
re-run here. Read in full: `plan.md`, `object_model.py`, `visibility.py`, `naked_eye_source.py`,
the `source.py`/`logger.py`/`test_logger.py` diffs, `test_object_model.py`, `test_visibility.py`,
`test_naked_eye_source.py`, `docs/concept/PETROBRAIN_RUNTIME.md`'s new section, and
`implementation.md`'s decision log. `hybrid_source.py` read for comparison (provenance/confidence/
`derived_world_position` precedent).

The implementation is careful, well-documented, and matches the plan's stated design closely —
the FOV/angular-radius/LOS composition, the debounce/cap logic, and the output quantisation are
all correctly built and meaningfully tested (tier-boundary, FOV-boundary, cap-boundary, and
quantisation-regression cases all present, not decorative). The binocular premise is stated
plainly and repeatedly in exactly the place Decision #6 was worried about (`visibility.py`'s
module docstring, explicit "do not re-derive... and 'correct' them" warning). Confidence/
provenance are correctly distinct from and weaker than Hybrid's.

Two things need fixing before this is done, one of which is the concrete finding flagged for
review: a real defect in `object_model.py`'s ship-keyword vocabulary (not just thin coverage),
and a broken documented run path (`body-layer/CLAUDE.md` was not updated for the new required
`--world-model-db` argument). Everything else — the four implementer-flagged ambiguities, and
the general thinness of the vocabulary table — is a defensible judgment call or an
already-plan-licensed risk, not a blocker.

### Required Fixes

- **`object_model.py`'s `OP_SHIP` keyword list is a domain-mismatch bug, not merely thin
  coverage.** The six keywords (`cruiser`, `frigate`, `corvette`, `destroyer`, `boat`, `ship`)
  are English hull-*class* descriptors, but `object_type` (from `LoGetWorldObjects`) carries
  DCS's literal unit-*type* identifiers — for ships, these are hull/proper-noun model names
  (`Slava`, `leander-gun-achilles`, `CastleClass_01`, per the 595-real-type validation against
  `HelperAI_reporting_names.lua` cited in this review's prompt). None of those strings contain
  an English hull-class word, so `OP_SHIP` is effectively unreachable against real data — this
  is a wrong assumption about what `object_type` looks like, not an incomplete-but-working
  vocabulary. It is masked in the test suite: `test_object_model.py::test_ship_keyword` asserts
  against the fabricated string `"Grisha corvette"`, which is not a real DCS type name and would
  pass even if every real ship type fell through to fallback (which, per the validation, they
  do). Two mechanically small changes needed: (1) replace or supplement the `OP_SHIP` keywords
  with real DCS ship type-name substrings (informed by `HelperAI_reporting_names.lua`, cited via
  the research doc — see next item, not the local sync-only file path), enough to cover the hull
  classes actually shipped in this project's theatres; (2) replace `test_ship_keyword`'s fixture
  string with a real DCS type name (or add a second case using one) so the test would actually
  fail if this regresses. Scope this narrowly — fixing the demonstrated-broken `OP_SHIP` category
  (and spot-checking the SAM/SPAAG keywords the same way, since they're keyed on `sa-3`/`sa-6`-
  style shorthand that may or may not match real type strings either), not rebuilding the whole
  table. The broader coverage question (88% overall fallback) is a backlog item, below, not part
  of this fix.

- **`body-layer/CLAUDE.md`'s documented run command is now broken.** `logger.py main()` (commit
  `2635bf5`) added `--world-model-db` as `required=True`, but `body-layer/CLAUDE.md`'s "Running
  the live logger" section (the `PYTHONPATH=... python -m logger --aircraft-layer-url ...
  --theatre ...` example, appearing twice — once in the "Commands" section, once in the
  "Structure" section's `src/logger.py` bullet) was not updated on this branch (confirmed: no
  `body-layer/CLAUDE.md` entry in the branch's diffstat). Anyone following the documented command
  verbatim now gets an argparse "the following arguments are required: --world-model-db" error.
  Add `--world-model-db <path>` to both example commands, and a short note (mirroring the
  existing `PYTHONPATH` callouts) that `NakedEyePerceptionSource` requires a built world-model
  region `.sqlite` to run at all now, per `docs/concept/PETROBRAIN_RUNTIME.md`'s new section and
  the world-model seam note already in this file.

- **Record the coverage finding.** The 595-real-DCS-type validation of `object_model.py` against
  `HelperAI_reporting_names.lua` (`OP_GROUPSOMETHING` fallback 525/595 = 88%; `OP_ARMORED` 23,
  `OP_TRUCK` 19, `OP_INFANTRY` 13, `OP_ZU23` 8, `OP_SHIP` 6, `OP_SPAAG` 1) exists only in this
  review's prompt right now — nowhere in the repo. Per this project's established pattern for
  DCS-internals verification findings (`aircraft-layer/research/*.md`, the same directory
  Investigator has been filing PB-1/PB-1.5 findings in), write a short dated entry recording the
  method (validated against `HelperAI_reporting_names.lua`, ED's own DCS-type → reporting-name
  mapping, cited via that filename rather than the gitignored local sync path) and the numbers
  above. This is cheap and prevents the finding from being lost once this conversation ends; it
  is not, by itself, a fix to the table (see Optional Refinements for that).

### Optional Refinements

- **Backlog, not blocking: derive a broader `object_model.py` table from
  `HelperAI_reporting_names.lua`.** The plan explicitly licenses "a hand-authored starting
  vocabulary, same unvalidated posture as `association.py`'s `_type_match_score`" — thin coverage
  by itself is within that accepted risk, and `world-model` seam / PB-1.5's own live acceptance
  test (stage 5, explicitly out of scope for this pass) is the intended place this gets exercised
  against reality. Worth noting for sizing, though: the practical consequence of the 88% fallback
  is smaller for the *detection gate* than it looks at first glance — `DEFAULT_SIZE_M = 5.0`
  computes to `5.0 / 0.008 * 4.0 = 2500.0`, exactly `NAKED_EYE_RANGE_CAP_M`, so any fallback-
  classified object at or above ~5 m (which covers most vehicles/ships in the missed set) gets
  the same effective detection range the cap would have given it anyway had it matched correctly
  — the fallback mainly costs classification-label fidelity (`OP_GROUPSOMETHING` instead of
  `OP_ARMORED`/`OP_SHIP`/etc.), not detection range, for anything ship/vehicle-sized. It matters
  more for anything genuinely smaller than 5 m that falls through unclassified (e.g. light
  utility vehicles) — those get bumped up to the 2500 m cap instead of a shorter true-size
  threshold, an over-*generous* risk in the opposite direction from the plan's stated main
  concern ("over-strict... more likely outcome"). Recommend a proper backlog item — "derive
  `object_model.py`'s table from `HelperAI_reporting_names.lua`'s full type list" — sized as its
  own small Architect/Implementer pass (nontrivial: mapping ~595 type strings is real work, not a
  quick keyword add), referencing the research entry above.
- **Range-bucket "snap up to containing bucket's ceiling" vs. literal nearest-of-24** (flagged by
  Implementer as ambiguous, e.g. 549 m → `OP_D600M` rather than `OP_D500M`). The research doc
  doesn't specify a rounding direction for `OP_D...` either — the plan's "snapped to the nearest"
  wording is genuinely underspecified here. The implemented reading (bucket-containment, named by
  upper bound, monotonic) is a defensible interpretation of ED's own naming convention and is
  correctly tested as such. Not a required fix. Recommend a one-line addendum to `plan.md` or
  `implementation.md` formally recording ceiling-snap as the canonical semantics, so a future
  reader doesn't "fix" it toward literal-nearest without realizing it was a deliberate choice.
- **`derived_world_position` left un-quantised (exact ground-truth x/z).** Consistent with
  `HybridPerceptionSource`'s own existing precedent (confirmed: Hybrid's `derived_world_position`
  is also exact `result.candidate.x/z`, not fuzzed) — this isn't a new pattern PB-1.5 invented,
  it's the field's established role across both channels: internal bookkeeping for future
  fusion/contact-memory work, not a crew-facing report field. `code owns facts, never
  fabricated` also argues for keeping it exact rather than degrading real DCS ground truth.
  Acceptable as implemented; nothing downstream reads it as a crew-facing claim today (BL-2
  doesn't exist yet). Worth one forward-looking note (in `PETROBRAIN_RUNTIME.md`'s "Contact
  identity" section, when BL-2 is actually planned) that any future layer surfacing "what
  Petrovich knew" from an `Observation` must read the quantised `bearing_deg`/`range_m`/
  `classification_raw` fields, never `derived_world_position`, for anything crew-facing — the
  anti-omniscience boundary this plan built depends on that discipline being followed by a later,
  different author who didn't see this plan's reasoning.
- Bearing quantisation (snap relative-to-heading, convert back to true bearing before storing) is
  correct and consistent with `geometry.py`'s stated true-bearing convention, and is directly
  tested (`test_quantise_bearing_is_relative_to_heading`). No issue.
- Confidence/provenance distinctness verified: `NAKED_EYE_VISIBILITY_CONFIDENCE = 0.4` is
  correctly below Hybrid's `CONFIDENT_ASSOCIATION_CONFIDENCE = 0.6`, and
  `PROVENANCE_VISIBILITY_FILTER_ONLY = "world_objects/visibility_filter_only"` reads distinctly
  from both of Hybrid's provenance strings. Matches the plan's Invariant Check requirement
  exactly.
- Binocular premise (Decision #6) is stated plainly in the one place a future reader is most
  likely to go "correct" the numbers downward: `visibility.py`'s module docstring leads with it,
  names `BINOCULAR_RANGE_MULTIPLIER` for what it is rather than as a transcription of
  `extra_eyesight_ratio`, and explicitly says not to re-derive from an unaided-eye assumption.
  `naked_eye_source.py` cross-references it. Satisfies the specific failure mode Decision #6 was
  guarding against.
- No `CompositePerceptionSource` was introduced (per the plan's explicit decision) —
  `logger.py`'s `sources: list[PerceptionSource]` is the right-sized amount of abstraction; no
  scope drift here.
- No debug/TODO leftovers found in the new/modified files (grepped for `TODO`/`FIXME`/`print`/
  `pdb`; the one `print()` hit is `logger.py`'s intentional log-line output, pre-existing PB-1
  behavior, not new debug code).
- Working tree is clean, all new files are committed (confirmed via `git status --porcelain`).

### Verdict

APPROVED WITH MINOR FIXES

The two required fixes (the `OP_SHIP` keyword domain-mismatch bug plus its masking test, and the
stale `body-layer/CLAUDE.md` run command) are both small, mechanical, and don't touch the design
— no rework of `visibility.py`'s gating logic, the debounce/cap machinery, or the quantisation
scheme is needed. Recording the coverage finding is a documentation-only action. Nothing here
rises to a redesign or a plan violation.

### Review Confidence

Full read. All new source files (`object_model.py`, `visibility.py`, `naked_eye_source.py`) and
all new/modified tests were read in full, not sampled; `source.py`/`logger.py`/`test_logger.py`
diffs were read in full; `hybrid_source.py` was read for direct comparison on
provenance/confidence/`derived_world_position` precedent; `docs/concept/PETROBRAIN_RUNTIME.md`'s
new section and `implementation.md`'s decision log were read in full. Did not re-run
format/lint/type/test (user independently confirmed all pass; no changes were made that would
invalidate that). Did not re-verify the 595-type/`HelperAI_reporting_names.lua` validation
numbers directly (the file is gitignored and outside this review's access pattern) — taken as
given from the task prompt, consistent with how the module's own keyword list reads against a
real ship-type naming convention.

---

## Pass 2 — review-fix commits + reporting-name lookup + cap raise (2026-09-09)

Reviewed `4ca7bcb`, `b5b5021`, `e22f67e`, `90c569a`, `abca037` against this file's Pass-1
required fixes, `plan.md`, and `aircraft-layer/research/2026-09-09-object-model-keyword-
coverage.md`. Read in full: `object_model.py`, `reporting_names.py`, `visibility.py`'s diff,
`body-layer/CLAUDE.md`'s diff, `test_object_model.py`, `test_reporting_names.py`, `test_visibility.py`'s
diff, the coverage-sample fixture, the committed TSV, and the research doc (including its two
addenda). Independently reproduced the coverage numbers and audited every reporting-name keyword
against the full 595-row real-type catalogue with a script (not just trusted the commit messages)
— reported below rather than taken on faith, since that is the whole point of this pass.

All three of Pass 1's required fixes are done and hold up: `OP_SHIP`/SA-*-keyword domain mismatch
fixed against real type strings, `body-layer/CLAUDE.md`'s run commands fixed in both places
(Commands section and the Structure section's `src/logger.py` bullet), and the coverage finding
is recorded at `aircraft-layer/research/2026-09-09-object-model-keyword-coverage.md`, later
extended in-place with two well-labelled addenda documenting the reporting-name-lookup work
rather than losing that history. `90c569a`'s bare-`"tank"` removal is exactly the class of fix
the research doc's own Finding 4 called for — correctly typed as a perception defect (a fuel
truck read as armour), not tidiness, with a real regression test using the 6 real type names that
falsely matched.

### Required Fixes

- **The new "coverage floor" test in `test_object_model.py` cannot fail independently of the
  per-entry check next to it — it is mathematically guaranteed to read 1.0 given how the fixture
  was built, which defeats the stated purpose of restructuring it.** Every one of the fixture's
  100 `"ground"`-bucket entries has a non-null `expected_op_class` (confirmed:
  `entry["expected_op_class"] is None` count is 0 across all 100), i.e. the bucket was populated
  exclusively from types already known to classify correctly — not a representative or random
  sample of the true "ground" population, where real coverage is measured at 64.5% (196/304) in
  the same research doc this test cites. Because `assert not mismatches` runs *before* the
  coverage-floor assertion and would already fail on any entry whose actual class diverges from
  its expected class, by the time `ground_coverage = ground_classified / ground_total` is computed
  every "ground" entry has, by construction, already been proven to match its expectation — so
  `ground_classified == ground_total` always holds whenever the test reaches that line at all.
  `_MIN_GROUND_COVERAGE_FRACTION = 0.9` can never independently trigger; it is strictly subsumed
  by the stronger per-entry check and is dead code dressed up as a coverage metric. This is the
  same failure mode Pass 1 required a fix for (a test that reads as "validated against real data"
  but cannot actually catch the regression it claims to guard against) — reintroduced here in a
  different shape: instead of one fabricated string, it's a curated set of only-passing real
  strings. Fix: either (a) rebuild the `"ground"` bucket as an honest sample of the full 304-type
  ground population — including a fair share of the ~108 real, currently-unclassified ground
  types (the ones that are neither `"ground_deferred"`'s deliberately-out-of-scope set nor
  currently covered) — with `expected_op_class: null` for those, and set the floor meaningfully
  below the measured 64.5% so it can move and actually catch a regression; or (b) if the intent
  really is "don't let today's 100 known-good classifications silently break," rename/redocument
  the assertion honestly as a per-entry regression guard (which it already effectively is via
  `mismatches`) and stop presenting `ground_coverage` as a coverage measurement, since it isn't
  one as currently built. (a) is preferable — it is what the docstring and commit message already
  claim this test does.

### Optional Refinements

- **The `_WWII_REPORTING_NAME_PREFIX = "old "` guard's docstring over-claims completeness, and
  the gap is real (though currently harmless).** Grepping the committed TSV for WWII-flavoured
  types turns up at least two reporting names that are WWII units but do *not* start with `"Old
  "`: `M4_Sherman`/`M4A4_Sherman_FF` both resolve to `"M4 Sherman"` (no prefix), and
  `soldier_wwii_br_01`/`soldier_wwii_us` both resolve to plain `"Soldier"`. Checked against every
  keyword in `_REPORTING_NAME_KEYWORD_PROFILES` (script, not inspection) — none currently matches
  `"sherman"`, so `profile_for("M4_Sherman")` still correctly falls back today, and `"soldier"`
  matching the bare `"Soldier"` reporting name is harmless anyway (a WWII soldier is physically
  the same size as a modern one, so `OP_INFANTRY`/1.8 m is accurate regardless of era — and that
  raw-table `"soldier"` keyword predates this session's work, not a new regression). So this is
  not a live bug. But the guard's docstring claim ("every one of these 56+ reporting names starts
  with this literal prefix") is not accurate, and the mechanism is one un-lucky future keyword
  addition (e.g. a broad tank keyword that happens to also read "sherman") away from silently
  reclassifying a WWII unit as modern armour — exactly the failure class this guard exists to
  prevent. Recommend either tightening the docstring's claim (it holds for the 56 reporting names
  the "Old " scan was run against, not literally every WWII unit in the table) or adding the two
  Sherman reporting names to an explicit exclusion supplementing the prefix check, next time this
  table is touched.
- **`ground_deferred` bucket assignments spot-checked and are honest.** All 17 entries (towed
  AA/mortar pieces, standalone SAM-system radars/launchers beyond IRIS-T, static structures,
  airfield support equipment) genuinely have no correct ED ground-vehicle bucket, matching the
  docstring's own reasoning — not a dumping ground for real misses dressed up as "deliberately
  out of scope." No issue here; noted because it's the natural place a coverage-floor fixture
  could be gamed in the *other* direction (hiding real gaps as "deferred" rather than as
  "already-passing"), and it wasn't.
- **Reporting-name-pass audit against the full 595-row catalogue found no aircraft/ship
  false positives.** Ran every `_REPORTING_NAME_KEYWORD_PROFILES` keyword against all 376 distinct
  real reporting names independently (not just the curated fixture) — every match list is exactly
  the intended real type(s), nothing unexpected (no aircraft, no unrelated ground/support type).
  Confirms the research doc's "checked against all 595 real reporting names for collisions" claim
  for this table. `"cobra"` (→ `OP_ARMORED`, the VBL Cobra 4x4) was worth checking by name given
  Bell's AH-1 Cobra shares the word — no collision, because this table (`HelperAI_reporting_names.lua`)
  doesn't carry aircraft reporting names for AH-1 in the first place.
- **The committed TSV, its loader, and the drift story are sound.** No duplicate keys under
  case-insensitive folding (checked programmatically, 0 of 595). `reporting_names.py`'s two-pass
  fallback (unmapped type → raw-table pass, not a crash) is correctly documented and tested
  (`test_reporting_names.py::test_unmapped_type_returns_none`,
  `test_object_model.py::test_unmapped_type_still_falls_back_to_raw_table_behaviour`).
  Regeneration steps are concrete and actionable (file location, extraction method, format,
  re-test command). Committing it is the right call and consistent with `body-layer/CLAUDE.md`'s
  own existing convention (`tests/fixtures/` is committed directly, unlike `world-model/data/`) —
  this is small (16 KB), derived, static reference data next to the code that consumes it, not
  the kind of raw/generated bulk dataset the root invariant about `world-model/data/` is aimed at.
  Correctly placed under `body-layer/src/perception/data/` (runtime data) rather than
  `aircraft-layer/research/` (dated findings) — the research doc records the *investigation*,
  the TSV is the *data*, and both are where this project's conventions say they should be.
- **`NAKED_EYE_RANGE_CAP_M`'s raise to 5000 m is well-documented and honestly labelled as
  un-tuned.** The doc comment no longer claims to be ED's `scan_rad_around_point` — it now says
  plainly what it replaced and why, cites the live-probe finding that motivated the raise, and
  states outright that it's a starting point for live-tuning per the user's own instruction, not
  a settled number. Both rewritten tests changed what they actually assert rather than just
  changing numbers to keep passing: `test_ural_truck_size_curve_binds_below_the_range_cap` now
  proves the size curve (not the cap) is the binding constraint for a truck at the new cap value,
  and `test_range_cap_binds_only_for_objects_the_size_curve_would_let_run_away` uses a real ship
  type (`"MOLNIYA"`) with both an at-cap and a beyond-cap case, genuinely exercising the cap as
  the ship's binding constraint rather than asserting a value that would pass regardless. Verified
  the boundary semantics directly in `visibility.py`: `candidate_range_m > range_threshold_m`
  fails closed, so exactly-at-cap is correctly still visible, matching the test.

### Verdict

APPROVED WITH MINOR FIXES

One required fix, and it is test-only: the coverage-floor assertion in
`test_coverage_floor_against_real_type_sample` needs a fixture built from an honest sample of the
real "ground" population (not exclusively already-passing entries) before it does what its
docstring and this project's own review history says it should do. Nothing here touches
`object_model.py`'s actual keyword tables, `reporting_names.py`'s loader, or `visibility.py`'s
gating logic — all of that is sound, well-tested against real data (independently re-audited this
pass, not just trusted), and the two-pass lookup, the WWII guard's *current* behaviour, and the
cap raise are all correctly implemented. Given the user's stated direction (naked-eye becomes the
*primary* detection mechanism, not a fallback), this fixture fix is worth doing before that
transition raises the stakes on this table's coverage claims being trustworthy — but it does not
block anything else in this pass, and the un-tuned cap constant is honestly labelled as such,
which is what "raise it, we'll fine-tune later" calls for at this stage.

### Review Confidence

Full read. All five commits' diffs read in full; `object_model.py` and `reporting_names.py` read
in full (not diffed against Pass 1's versions, since both were substantially rewritten);
`visibility.py`'s and `body-layer/CLAUDE.md`'s diffs read in full; every new/changed test file
read in full. Independently reproduced the coverage-floor test's mechanics by hand (not just read
the assertion) and independently scripted the full-catalogue false-positive audit for both keyword
tables rather than trusting the research doc's claim of having done so. Did not re-run
format/lint/type/test (user independently confirmed all pass; no source changes were made during
this review that would invalidate that).

---

## Pass 3 — ownship-echo bug fix, commit `549aee6` (2026-09-09)

Reviewed the single fix commit against `plans/pb1.5-naked-eye-detection/debug.md`'s report.
Read in full: `debug.md`, the commit's diff (`association.py`, `hybrid_source.py`,
`naked_eye_source.py`, all three test files), `geometry.py`'s `range_m`/`bearing_deg`,
`visibility.py` in full (to hand-check the FOV/range-threshold gates against the test
fixtures' actual numbers), and `association.py`'s `associate()`/`_type_match_score` in full.
Format/lint/type/test independently verified by the user before this pass (102 passed); not
re-run, except as below. Empirically verified test discrimination rather than reasoning about it
in the abstract: temporarily stripped the `exclude_ownship()` call from both channels' `poll()`
and re-ran the six new tests against the unfixed code, then restored both files and confirmed a
clean tree and a full green suite (102 passed) afterward.

### Required Fixes

- **One of the six regression tests does not actually test the fix it documents itself as
  testing.** `test_hybrid_source.py::test_ownship_echo_does_not_prevent_a_real_candidate_from_
  associating` passes whether or not `exclude_ownship()` runs — confirmed empirically, not just
  by inspection: with the `exclude_ownship()` call removed from `hybrid_source.py`, this specific
  test still passes, while its sibling
  (`test_ownship_echo_is_excluded_and_detection_drops_with_no_other_candidate`) correctly fails.
  Root cause: the fixture gives the echo `object_type="Mi-24P"` and the real target
  `object_type="Ural-4320"` against classification text `"Ural truck"`. Without the fix, both
  candidates survive `associate()`'s plausibility filter (range ~3.6 m and 1000 m are both under
  `RANGE_CAP_M`; both bearings are inside the forward hemisphere), so the function falls through
  to `_type_match_score` tie-breaking — `"ural"` scores 1 against the real target and 0 against
  `"Mi-24P"`, so the echo is discarded by the *pre-existing* type-match logic regardless of
  `exclude_ownship`. The test therefore provides no regression protection for the claim its own
  comment makes ("ownship echo does not prevent a real candidate from associating") — this is the
  same failure mode this project's review history has already required fixes for twice (Pass 1's
  fabricated-string fixture, Pass 2's coverage-floor fixture built only from already-passing
  entries): a test that reads as verifying a real-data scenario but would pass unchanged if the
  fix under test were deleted. Fix: change the fixture so type-match scoring alone cannot
  discriminate the two candidates — e.g. give the echo an `object_type` that also scores against
  `"Ural truck"` (or matches the real target's type exactly), so that without `exclude_ownship`
  the two candidates tie in score and the *nearer* one (the echo, at ~3.6 m) would incorrectly win
  the ambiguous-tie-break, giving a test that only passes when the exclusion actually ran. The
  naked-eye channel's equivalent test
  (`test_ownship_echo_does_not_suppress_a_real_nearby_target`) does not have this problem — it has
  no type-match step to coincidentally rescue it, and was empirically confirmed to fail correctly
  without the fix.

- **`association.py`'s module docstring should be updated to acknowledge `exclude_ownship` as a
  second, distinct responsibility.** Not a request to move the function — see Question 2 below,
  the current placement is the pragmatic and arguably only sensible one given the module
  dependency graph (`WorldObjectCandidate` is defined in `association.py`; `geometry.py`, the
  more obviously "shared by every tier" module, cannot import it without an `association.py` ->
  `geometry.py` -> `association.py` cycle, since `association.py` already imports `GeoPosition`/
  `bearing_deg`/`range_m` from `geometry.py`). But the module's own "Scope note" currently states
  flatly that "this is a *disambiguator*, not a *gate*" — true of `associate()`, and no longer
  true of the module as a whole now that it also owns an unconditional drop-candidates gate called
  by both channels before their own filtering. Left as-is, a future reader skimming that scope
  note (exactly the kind of reader this project's docstrings are written for, per its own
  established style) could reasonably conclude `exclude_ownship` doesn't belong here or is
  unaware of the constraint that put it here. A one- or two-line addition to the docstring noting
  the module now also hosts a shared candidate-sanitization step, and why (type ownership,
  avoiding a circular import with `geometry.py`), closes the gap cheaply.

### Optional Refinements

- **`OWNSHIP_ECHO_EXCLUSION_RADIUS_M = 50.0` is a reasonable starting value, honestly labelled as
  un-tuned, and shipping the heuristic now rather than blocking on an `Export.lua`-based identity
  fix is the right call** — confirmed there is in fact no cheaper identity-based shortcut
  available today: `OwnshipState` (from `LoGetSelfData`/telemetry) carries no `object_id` field
  comparable to `LoGetWorldObjects`'s per-object id, so an exact fix genuinely requires an
  aircraft-layer/`Export.lua` change, not just a body-layer code change, matching the debug
  report's own framing. Given the alternative was a continuous stream of fabricated contacts
  (pinned range, wrong classification, meaningless bearing — a direct violation of "code owns
  facts, models never invent them"), the proximity heuristic is a clear net improvement, reversible,
  and bounded well inside both channels' real range caps. Worth a one-line addition to the already-
  filed backlog item, though, that isn't in `debug.md`'s "Needs live DCS" section as currently
  written: 50 m is roughly 3x the Mi-24P's own physical extent, which is a comfortable margin in
  general, but the Mi-24P's core mission profile (troop insertion/extraction, hovering directly
  over or landing beside dismounted troops) is exactly the scenario most likely to put a *real*
  contact inside that radius — worth flagging explicitly as the concrete case to check for when the
  live-tuning capture happens, not just "some real object closer than 50 m" in the abstract.
- **Pass restraint on the debounce/`object_id`-instability question (Question 4) is correct and the
  reasoning holds up on inspection.** Evidence 5's repro isolates exactly one variable (position/
  bearing jitter with a *stable* `object_id` held fixed across 20 polls) and reproduces an
  irregular 5/20 emission pattern in the right ballpark to explain the live log's "7 emissions over
  ~23 s" — which is sufficient to explain the observed symptom without invoking `object_id`
  instability, and the report is careful to claim only sufficiency ("not needed to explain"), not
  that instability was ruled out ("remains genuinely unconfirmed either way" is stated plainly,
  twice). That is the correct epistemic posture for a claim about `LoGetWorldObjects`'s Lua
  `pairs()`-iteration key stability, which is a live-DCS-internals question this project's own
  conventions route through Investigator/a live capture, not through speculative code changes in a
  debugging session. No speculative patch to the debounce mechanism was made, consistent with the
  Debugger role's own restraint principle. Filing it as a backlog item requiring a live capture
  (rather than another synthetic repro) is the right next step, not a shortcut being taken.
- Exclusion is confirmed correctly placed ahead of both channels' own filtering with no bypass
  path: grepped for every `WorldObjectCandidate.from_dict` call site in `src/perception/` (exactly
  two, one per channel) and both route straight into `exclude_ownship()` before
  `visibility.check_visibility()` (naked-eye) or `associate()` (hybrid) ever sees the list. No
  third construction path exists.
- `range_m`'s slant-range (including altitude) is the correct distance metric for this exclusion —
  a ground-only range would understate the real echo residual for a helicopter whose own
  altitude differs from its `LoGetWorldObjects` self-entry's reported altitude by rotor-height-
  scale amounts, still comfortably inside 50 m either way.
- The strict `>` boundary semantics (drops a candidate exactly at 50.0 m) is correctly tested and
  matches the constant's own stated intent (a sanity margin, not a hard physical cutoff) — no
  issue, just confirming the boundary test is not itself vacuous (verified it exercises the
  intended branch, not an off-by-one that happens to read the same either way).
- Type hints and docstring cross-references in the new code are complete and consistent with this
  project's established style; no debug/TODO leftovers found in the diff.

### Verdict

APPROVED WITH MINOR FIXES

The fix's core mechanism is sound, correctly placed ahead of each channel's own filtering with no
bypass, and directly addresses the confirmed root cause — 5 of the 6 new regression tests were
empirically confirmed (not just read) to fail without `exclude_ownship()`, including the one that
matters most (the single-candidate self-association case in the hybrid channel). The one required
fix is test-only and narrow in scope: one fixture in `test_hybrid_source.py` needs its `object_type`
values changed so type-match scoring can't coincidentally do the excluding function's job for it —
mirrors, in miniature, the exact test-integrity failure mode this project's review history keeps
surfacing, so it's called out explicitly rather than let slide as "close enough." The second
required fix (a docstring addendum to `association.py`) is documentation-only and does not touch
behavior. Neither required fix touches `exclude_ownship()`'s logic, its placement, the 50 m
constant, or the debounce-restraint decision — all four of those hold up under direct scrutiny.

### Review Confidence

Full read. `debug.md`, the full commit diff, and all three touched test files read in full,
not sampled. Verified the test-discrimination question empirically rather than by reasoning
alone: disabled the fix in both channels' source files one at a time, ran the affected tests
against the unfixed code, confirmed which tests correctly failed and which did not, then restored
both files and reconfirmed a clean tree and a full green run (102 passed). Hand-verified the
`visibility.py` FOV/range-threshold/LOS gate arithmetic against the naked-eye test fixtures'
actual coordinates (bearing ~326.3 deg, range ~3.6 m, threshold 2500 m for the `OP_GROUPSOMETHING`
fallback size) rather than trusting the test's own pass/fail alone. Confirmed via grep that
`OwnshipState` carries no `object_id` field, supporting the finding that an identity-based fix is
genuinely unavailable today without an `Export.lua` change (Question 1). Did not re-verify the
debug report's live-sortie log transcript or the underlying DCS-internals claim about
`LoGetWorldObjects` including ownship in single-player — that remains explicitly open per
`debug.md`'s own "Needs live DCS" section, and re-litigating it was out of this pass's scope.
