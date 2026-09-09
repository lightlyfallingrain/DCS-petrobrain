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
