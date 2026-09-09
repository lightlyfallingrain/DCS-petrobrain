### Implementation Summary

Implemented Implementation Plan stages 1, 2, 3, and 6 of
`plans/pb1.5-naked-eye-detection/plan.md`: the naked-eye (binocular-aided) visual-spotting
`PerceptionSource`, built as a second, independent channel alongside `HybridPerceptionSource`, and
wired into `logger.py`'s poll loop. Stage 4 (aircraft-layer Lua distance cap), stage 5 (live
acceptance test), and stage 7 (live probe) were explicitly out of scope for this pass, per the
task's instructions -- stage 7 was already delivered separately this session as
`aircraft-layer/dcs-export/Export.probe-pb15.lua` and was not touched.

Followed the plan's repeated "same pattern as `association.py`" guidance closely: pure,
fixture-testable modules with no network I/O until the concrete `PerceptionSource`, hand-authored
keyword vocabularies with an explicit "unvalidated starting vocabulary" caveat, named/tunable
`Final` constants instead of inline literals, and absence-over-fabrication on every gate failure.

### Files Changed

- `body-layer/src/perception/object_model.py` -- **NEW.** `ObjectTypeProfile` (`size_m`,
  `op_class`) plus `profile_for(object_type)`, a hand-authored keyword-to-profile lookup shared by
  `visibility.py` (angular-radius numerator) and `naked_eye_source.py` (output classification).
  Uses case-insensitive substring containment rather than `association.py`'s word-tokenized
  overlap -- a deliberate deviation, documented in the module docstring, since DCS unit-type
  identifiers are frequently hyphenated compounds (`"ZU-23"`, `"T-72"`) that a `[a-z0-9]+`
  tokenizer would split apart.
- `body-layer/src/perception/visibility.py` -- **NEW.** `check_visibility()` composes an FOV cone
  (`NAKED_EYE_FOV_HALF_WIDTH_DEG = 60.0`), an angular-radius recognition-tier range threshold
  derived from `HelperAI.lua`'s `min_angular_radius[medres]` times `BINOCULAR_RANGE_MULTIPLIER`
  (named/documented as a binocular-aided-observation modeling choice per Decision #6, not a
  transcription of `extra_eyesight_ratio`), capped at `NAKED_EYE_RANGE_CAP_M = 2500.0`
  (`scan_rad_around_point`), and `geometry.line_of_sight_clear` (its first real consumer -- dead
  code since PB-1). Returns `VisibilityResult | None`; any failing gate returns `None`, no
  fabricated weak-confidence guess.
- `body-layer/src/perception/naked_eye_source.py` -- **NEW.** `NakedEyePerceptionSource`, a second
  concrete `PerceptionSource` (not a `HybridPerceptionSource` subclass). `poll()`: fetch
  `/world_objects/latest` only, run every candidate through `check_visibility()`, quantise the
  surviving geometry to ED's ambient-callout vocabulary (bearing to the nearest of 12 `OP_A1H`...
  `OP_A12H` clock positions relative to heading then expressed back as true bearing; range to the
  nearest of 24 `OP_D...` buckets, snapped to each bucket's upper bound), debounce on
  object-id visible-set membership (reset on a missing snapshot, mirroring Hybrid's debounce-reset-
  on-gap), and cap newly-appearing detections per poll at `NAKED_EYE_MAX_NEW_PER_POLL = 3`
  (nearest-first, by exact un-quantised range).
- `body-layer/src/perception/source.py` -- added `SOURCE_NAKED_EYE_VISUAL_FILTERED: Final[str] =
  "naked_eye_visual_filtered"` (per the plan's Affected Modules section, this constant lives here
  rather than in `naked_eye_source.py`, unlike Hybrid's own `SOURCE_PETROVICH_DETECTION_ASSOCIATED`)
  and updated the module docstring's now-stale "neither concrete tier exists yet" framing.
- `body-layer/src/logger.py` -- `PerceptionLogger.source: PerceptionSource` (singular) became
  `.sources: list[PerceptionSource]`; `run_once()` polls every source and concatenates their
  `Observation`s in `sources` order before formatting/printing, per the plan's "no
  `CompositePerceptionSource` abstraction" decision. `format_observation_line()` now includes
  `source=...` in the flat-text line. `main()` gained a required `--world-model-db` argument
  (opens a read-only connection via `geometry.open_world_model`, needed by
  `NakedEyePerceptionSource`'s LOS gate) and now constructs both concrete sources.
- `body-layer/tests/test_object_model.py`, `test_visibility.py`, `test_naked_eye_source.py` --
  **NEW**, hand-authored fixtures mirroring `test_association.py`'s pattern (see Tests Added).
- `body-layer/tests/test_logger.py` -- the three existing tests using `source=FakeSource(...)`
  were updated to `sources=[FakeSource(...)]` to match the field rename (an unavoidable mechanical
  consequence of the plan's own logger.py change, not a scope-driven test rewrite); added
  `source=` to the format-line assertion and a new multi-source concatenation test.
- `docs/concept/PETROBRAIN_RUNTIME.md` -- added a "Second channel: naked-eye (binocular-aided)
  visual spotting" subsection under Perception adapter, per stage 6.

### Tests Added

- `test_object_model.py` (9 tests) -- default-fallback behavior; the four worked-example-table
  entries (infantry/truck/tank/SA-3) as a regression anchor against the plan's Proposed Defaults
  table; case-insensitivity; a dedicated test proving hyphenated identifiers (`"ZU-23"`) aren't
  split by a word tokenizer; keyword-precedence (shilka before the generic class).
- `test_visibility.py` (10 tests) -- tier-boundary cases at the infantry threshold (899 m visible,
  901 m not, using the uncapped 900 m `medres`×4 threshold so the outer cap doesn't mask the tier
  math); the range-cap-binds-before-the-uncapped-threshold case for a Ural truck (2400 m visible,
  2600 m not, though the formula alone would allow up to 3000 m) plus an at-exactly-the-cap case;
  FOV edge/outside/relative-to-heading cases; a LOS-blocks-an-otherwise-visible-candidate case
  (LOS math itself is `test_geometry.py`'s job, not re-tested here).
- `test_naked_eye_source.py` (17 tests) -- no-snapshot/no-visible-candidate absence cases; a single
  emission's full field shape (`source`, quantised `classification_raw`, provenance,
  un-quantised `derived_world_position`); debounce (still-visible not re-emitted, leaving-and-
  re-entering re-emits, a missing snapshot resets state); the emission cap (5 simultaneously-new
  candidates emits only the nearest 3, and capped-out candidates are not retried on the next poll
  since they're already "previously visible"); direct regression-anchor tests on the private
  `_quantise_bearing`/`_quantise_range_m` helpers (nearest-clock-position snapping, dead-ahead as
  12 o'clock, relative-to-heading correctness, bucket-upper-bound snapping, exact-boundary
  handling).

### Checks

- `ruff format --check body-layer/src body-layer/tests`: pass
- `ruff check body-layer/src body-layer/tests`: pass
- `mypy body-layer/src` (run from `body-layer/`, per that subproject's CLAUDE.md CWD-only caveat): pass, 0 issues across 11 source files
- `mypy body-layer/tests` (bonus, not in the mandated command list but run anyway): pass, 0 issues across 10 source files
- `pytest body-layer/tests -q`: pass, 79 passed

No `body-layer/.venv` existed on this machine before this session (world-model's and
aircraft-layer's don't either) -- created it ad hoc (`python3 -m venv body-layer/.venv`, then
`pip install ruff mypy pytest pyproj`) to run the mandated checks, matching the M1-era pattern
noted in `.claude/agent-memory/implementer/project_worldmodel_no_dep_tooling.md`. It is
gitignored (`body-layer/.gitignore`'s `.venv/`) and was not committed.

### Notable Discoveries

- **`geometry.line_of_sight_clear` had zero real callers before this plan.** `HybridPerceptionSource`
  never used it -- `association.py` has no DB access at all. `visibility.py` is the first code in
  the repo to actually exercise the world-model LOS seam `geometry.py`'s own docstring anticipated.
  This also means `NakedEyePerceptionSource` is the first `PerceptionSource` that needs a
  `sqlite3.Connection` to a built world-model region `.sqlite` at construction time, which is why
  `logger.py --world-model-db` had to be added as a new, required CLI argument -- the plan's
  Affected Modules section doesn't call this out explicitly as a `main()` wiring change, but it's
  an unavoidable consequence of stage 2's `visibility.py` design.
- **The plan leaves `derived_world_position`'s quantisation status unstated.** Whether the
  anti-omniscience output quantisation should also apply to `Observation.derived_world_position`
  (not just `bearing_deg`/`range_m`/`classification_raw`) isn't addressed in the plan text. I kept
  it as exact ground-truth x/z (matching `HybridPerceptionSource`'s own posture, and reasoning that
  it's internal bookkeeping for future fusion work rather than a crew-facing report field) --
  documented as a judgment call in `naked_eye_source.py`'s module docstring. Worth confirming this
  reading is what was intended, since it's the one place this implementation had to interpret
  rather than follow the plan literally.
- **Bearing quantisation direction was underspecified and required a design decision.** The plan
  says bearing snaps to "the nearest of the 12 `OP_A1H`...`OP_A12H` clock positions" but doesn't
  say whether the stored `Observation.bearing_deg` should become a heading-relative clock angle or
  stay a true bearing. Chose to compute the clock bucket relative to ownship heading (matching
  ED's own crew-relative "H o'clock" semantics) but convert the *quantised* result back to a true
  bearing before storing it, so `Observation.bearing_deg`'s existing true-bearing convention
  (`geometry.py`'s module docstring, and `HybridPerceptionSource`'s own usage) stays uniform across
  both channels. Flagging this because a different, equally defensible reading (store the raw
  heading-relative clock angle) was available and not ruled out by the plan text.
- **Range-bucket "snap to nearest" was implemented as "snap up to the bucket's upper bound,"** not
  true nearest-of-24-values rounding (e.g. 549 m rounds up into `OP_D600M`, not down to `OP_D500M`
  even though 549 is closer to 500). This matches the bucket-containment reading of ED's own naming
  (`OP_D600M` = "up to 600 m") and is simpler/monotonic, but it is a "snap up to containing bucket"
  semantics, not literal nearest-value rounding -- worth confirming that's the intended reading of
  the plan's "snapped to the nearest ... bucket" wording.
- Full range-bucket table (all 24) is kept intact even though `NAKED_EYE_RANGE_CAP_M = 2500`
  means only the first 13 buckets (up to `OP_D2_2p5k`) are reachable in practice -- flagged in the
  module comments rather than truncating the table, so it stays a faithful, cap-independent copy
  of ED's own vocabulary from the research file.

Nothing in the plan was found to be wrong, contradictory, or impossible as written for the stages
implemented here -- the three items above are places where the plan's prose left an implementation
choice open rather than a defect in the plan itself.

### Review fixes (2026-09-09)

Applied the three required fixes from `review.md` plus its one non-blocking recommendation.

**Files Changed**
- `body-layer/src/perception/object_model.py` — replaced the unreachable `OP_SHIP` keyword list
  (English hull-class words: `cruiser`/`frigate`/`corvette`/`destroyer`/`boat`/`ship`) with 57
  real DCS ship `object_type` substrings, and replaced the SA-3/6/8/9/13/15 keywords (NATO
  shorthand: `sa-3`/`sa-6`/...) with real DCS component-identifier substrings (`s-125`, `kub `,
  `osa`, `strela-10`/`strela-1`, `tor 9a331`/`chap_torm2`) — both categories were unreachable
  against real data for the identical reason (`object_type` never carries the guessed word), per
  `aircraft-layer/research/2026-09-09-object-model-keyword-coverage.md`. `"kub "` (trailing
  space) was chosen specifically to avoid a false-positive match on the unrelated real type
  `"Kubelwagen_82"`. Module docstring updated to cite the research doc and state which categories
  have been checked against real data (OP_SHIP, SA-3/6/8/9/13/15) vs. not (armor/truck, still an
  unvalidated hand-authored guess).
- `body-layer/tests/test_object_model.py` — fixed `test_ship_keyword` (was asserting against the
  fabricated string `"Grisha corvette"`, which matched the old table by construction and masked
  the domain-mismatch bug) to use the real DCS type `"MOSCOW"`; added
  `test_ship_keyword_matches_second_real_type_name` (a differently-shaped real type,
  `"leander-gun-achilles"`); fixed `test_sa3_keyword` the same way (`"SA-3 Launcher"` was equally
  fabricated) to use the real type `"5p73 s-125 ln"`; added `test_sa6_keyword_is_mrsam_not_srsam`
  and `test_sa6_keyword_does_not_match_unrelated_kubelwagen` as spot-checks/regression guards for
  the SA-6 fix; added `test_coverage_floor_against_real_type_sample`, which loads the new fixture
  and asserts both per-entry correctness and an aggregate coverage-floor (>= 0.8) so this can't
  silently regress without a test failure.
- `body-layer/tests/fixtures/object_type_coverage_sample.json` (new) — curated sample of 92 real
  DCS `object_type` strings (all 57 real ship types, the fixed SAM/SPAAG entries, existing
  armor/truck/infantry coverage, and ~14 legitimately-out-of-scope types like aircraft/other-SAM/
  buildings that are expected to stay at the fallback) backing the new coverage-floor test.
- `body-layer/CLAUDE.md` — added `--world-model-db <path>` to both documented `python -m logger`
  examples (the "Running the live logger" section and the `src/logger.py` Structure bullet),
  which were broken since `logger.py`'s `main()` made that argument required; the Structure
  bullet was also updated to mention `NakedEyePerceptionSource` (it only named
  `HybridPerceptionSource` before). Checked `body-layer/WORKFLOW.md` (doesn't exist),
  `docs/concept/PETROBRAIN_RUNTIME.md`, and `plans/pb1-perception-logger/implementation.md` for
  the same staleness — none of the others document a runnable command, so no further changes
  needed.
- `aircraft-layer/research/2026-09-09-object-model-keyword-coverage.md` (new) — dated finding
  recording the `HelperAI_reporting_names.lua` resource, the coverage method, and before/after
  numbers (overall fallback 88.2% -> 78.0%; `OP_SHIP` 6 (coincidental) -> 57; `OP_SRSAM`/
  `OP_MRSAM` 0 -> 8/2; armor/truck/infantry/ZU23/SPAAG unchanged). Also records two discoveries
  beyond the review's required scope: the ship category is actually 57 real types, not the 47
  found by an initial hull-class-word-only search of reporting names (10 more found by
  broadening to "vessel"/"craft"/"tug"/"landing"); and `OP_ARMORED`'s existing `"tank"` keyword
  has the identical domain-mismatch bug plus false positives (matches 8 real types, none of them
  armored vehicles — rail tank wagons, a fuel-tanker truck, a tanker aircraft), left unfixed as
  out of this review's scope and flagged as backlog.
- `plans/pb1.5-naked-eye-detection/plan.md` — added Decision 7 recording the Reviewer's
  non-blocking recommendation: range-bucket quantisation snapping *up* to the containing
  bucket's ceiling (549 m -> `OP_D600M`) is the canonical, deliberate semantics, not an
  implementation accident to "fix" toward literal-nearest-of-24 later.

**Judgment calls beyond the review's literal required scope**
- Widened the OP_SHIP fix from the initially-found 47 real ship types to the full 57 once a
  broader reporting-name search surfaced 10 more (`Dry-cargo ship-1`/`-2`, `HandyWind`,
  `HarborTug`, `Higgins_boat`, `Schnellboot_type_S130`, `Seawise_Giant`, `ZWEZDNY`, `atconveyor`,
  `speedboat`) — judged in-scope because it's completing the audit of the exact category the
  review required fixing (bounded, fully enumerable, zero false-positive collisions checked
  against all 595 real types), not new scope.
- Did **not** fix the `"tank"` keyword's false positives (`OP_ARMORED`, matches 8 real
  non-armored types) found while spot-checking — that keyword is outside the ships/SAM-SPAAG
  scope the review named, and the review explicitly treats broader-table work as backlog.
  Recorded as a discovery in the research doc instead.

**Checks**
- `ruff format --check body-layer/src body-layer/tests`: pass
- `ruff check body-layer/src body-layer/tests`: pass
- `mypy body-layer/src` (from `cd body-layer`): pass, no issues in 11 source files
- `PYTHONPATH=src:../world-model/src pytest body-layer/tests -q` (from `cd body-layer`): 83
  passed (was 79 before this pass; net +4 tests — 2 replaced fabricated-string tests kept the
  same name/count, added `test_ship_keyword_matches_second_real_type_name`,
  `test_sa6_keyword_is_mrsam_not_srsam`, `test_sa6_keyword_does_not_match_unrelated_kubelwagen`,
  `test_coverage_floor_against_real_type_sample`)
