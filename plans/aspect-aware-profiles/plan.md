### Goal

Replace `object_model.ObjectTypeProfile`'s single scalar `size_m` with real length/width/height
dimensions and an aspect-corrected apparent extent, so a target's detection/classification range
depends on how it is presented (broadside vs. nose-on) and on its tallest dimension when that
exceeds its silhouette width — fixing both the S-300 tall-mast bug and the aspect confound flagged
in the 2026-09-21 sortie, without touching the `LOWRES`/`MEDRES`/`HIRES` thresholds themselves.

### Investigator check (process step 2)

No unverified DCS-internals claim underlies this plan. `heading_true_rad` on `WorldObjectSample`
is already a **required, non-nullable** wire field (`aircraft-layer/src/schema/world_objects.py`,
`_REQUIRED_OBJECT_FIELDS`) — confirmed by reading the schema, not assumed. The only new factual
claims this plan introduces (real-world S-300 40B6M/64H6E physical dimensions) are not DCS
internals; they are ordinary domain research and are scoped out of this plan's own implementation
(see "S-300 dimensions are not fabricated here" below) rather than handed to `investigator`, which
exists specifically for DCS file/API/coordinate unknowns.

### Existing-mechanism check (process step 3a)

Read `object_model.py`, `visibility.py`, `association.py`, `clustering.py`, and
`naked_eye_source.py` in full before drafting this. Findings that shaped the design below:

- `ObjectTypeProfile` is a frozen dataclass with exactly two fields (`size_m`, `op_class`) and
  ~150 keyword-table rows across two tables (`_KEYWORD_PROFILES`, raw `object_type`;
  `_REPORTING_NAME_KEYWORD_PROFILES`, resolved reporting name). Every row is constructed with the
  same two-argument literal `ObjectTypeProfile(size_m=X, op_class=Y)`.
- `profile.size_m` has **two live consumers**, not one: `visibility.check_visibility`/
  `_achieved_tier` (the detection-range formula this plan targets), and
  `clustering.ClusterCandidate.size_m` (an angular-unit-width proxy for cluster separability,
  populated from `profile.size_m` in `naked_eye_source.py:426`). Both must keep working; only the
  first is in scope for aspect-correction (see "Scope cut: clustering stays scalar" below).
- `WorldObjectCandidate` (`association.py`) already has one tri-state-by-convention optional
  field, `is_ownship: bool | None`, with an explicit rule never to coerce `None` to a guessed
  value. This is the precedent step 3a asked to find and it is followed directly: the new
  `heading_true_deg` field is `float | None`, and "unknown aspect" is handled as its own case,
  never defaulted to 0° (nose-on) or 90° (broadside) — either would fabricate a fact.
- `check_visibility`'s docstring records a live merge-integration lesson (BL-9 vs. cones-slice-1
  parallel development: a hardcoded multiplier silently diverging from the value actually used).
  The same discipline applies here: every place that currently reads `profile.size_m` for a
  detection-range computation must be swapped to the new apparent-extent call, not left as a
  second, now-stale scalar path.
- No `IDENTITY_HALF_LIFE_S`-shaped decay/expiry constant is touched by this plan — this is a
  perception-layer geometry change, not a belief-layer temporal one. Confirmed by scope: nothing
  in `belief/` is edited (see Seam check below).

### Affected Modules / Files

- `body-layer/src/perception/object_model.py` — `ObjectTypeProfile` keeps `size_m: float` exactly
  as it is today, and gains three new *optional* fields: `length_m: float | None = None`,
  `width_m: float | None = None`, `height_m: float | None = None`. Because they default to `None`,
  **none of the ~150 existing table rows needs to change at all** — every current
  `ObjectTypeProfile(size_m=X, op_class=Y)` literal keeps compiling and keeps meaning exactly what
  it means today. New function `apparent_extent_m(profile, aspect_deg: float | None) -> float` —
  the one piece of real logic this file gains (see "The formula" below): it returns `profile.
  size_m` unchanged whenever any of the three dimension fields is `None`, and only computes the
  aspect projection when all three are set. Two rows get real measured dimensions: the S-300PS
  40B6M tr and 64H6E sr entries (see "S-300 dimensions" below) — every other row is, by design,
  simply never touched by this change.
- `body-layer/src/perception/association.py` — `WorldObjectCandidate` gains `heading_true_deg:
  float | None`. `from_dict` populates it from the wire dict's `heading_true_rad` (converted to
  degrees, matching this module's existing degree convention for bearings), defaulting to `None`
  only if the key is literally absent (defensive; the wire schema guarantees it, so this path is
  unreachable from the real pipeline and exists only so a malformed/synthetic dict degrades safely
  rather than raising). `filter_ownship`/`associate()` do not need the field and are unchanged —
  aspect is a `visibility.py`-only concern.
- `body-layer/src/perception/visibility.py` — `check_visibility` computes the aspect angle between
  the candidate's heading and the observer→candidate bearing (both already horizontal-plane
  bearings in this module's existing convention — no new elevation term), calls
  `object_model.apparent_extent_m(profile, aspect_deg)` once, and uses that single value for both
  the range-threshold gate and the `_achieved_tier` call (replacing the two separate
  `profile.size_m` reads). `_achieved_tier`'s `size_m` parameter is unchanged in type (still a
  plain `float`) — only what its caller passes in changes, so its own signature and the
  fixture-driven calibration tests below need no edit.
- `body-layer/tests/test_object_model.py` — new tests: `apparent_extent_m` at several aspect
  angles (not just 0°/90° — the coordinator review below is exactly why intermediate angles like
  45° must be exercised, since 0°/90° alone would have hidden the original cubic-fallback bug)
  against a known L/W/H triple with `L != W`; a profile with any of `length_m`/`width_m`/`height_m`
  left `None` returns `profile.size_m` unchanged at *every* aspect tested, including 45° — this is
  the regression guard, and it must assert against several angles, not just the two that happen to
  be fixed points of `sin`/`cos`; a parametrized sweep over every existing (unmigrated) table row
  confirming `apparent_extent_m(profile, angle) == profile.size_m` for `angle` in e.g.
  `{0, 30, 45, 60, 90, 135, 180}`.
- `body-layer/tests/test_visibility.py` — new tests: two candidates at the same range and profile
  but different `heading_true_deg` (broadside vs. nose-on) resolve to different tiers/range
  thresholds; `heading_true_deg=None` reproduces today's pre-aspect scalar behaviour exactly
  (the regression guard, mirroring cones-slice-1's own "must not change the default" pattern);
  one S-300-shaped synthetic profile (tall/thin) at a range between the old and new thresholds to
  pin the radar fix directly, independent of real DCS data.
- `body-layer/tests/test_vision_calibration.py` — **no code change expected, re-derived here
  rather than carried over from the (corrected) object_model.py design above, since this claim
  was flagged for re-checking.** Traced independently: `test_computed_tier_matches_ground_truth`
  and `test_gate_admits_every_photographed_range` call `visibility._achieved_tier`/replicate its
  arithmetic using `_largest_size_m(record)`, which reads the fixture JSON's own hardcoded
  `"size_m"` numbers directly (`vision_calibration.json`) — neither test ever calls
  `object_model.profile_for` or `apparent_extent_m` for these numbers, and the fixture objects
  (T72B, SA-10C2/TR/SR, BM-27, BMD1, etc.) are not the two S-300 rows that get real dimensions in
  this pass, and even if they were, `apparent_extent_m` returns `size_m` unchanged for a profile
  with no measured dimensions or no aspect — both hold here (no heading in the fixture, and no
  migrated dimensions for these object types). `test_object_model_resolves_every_object_type` only
  asserts `profile.size_m > 0`, which is untouched since `size_m` is not being removed or
  redefined. So this file's assertions are unaffected by construction, not by the accident that
  sank the original cubic-fallback design — this is the one part of the original claim that
  survives the correction below intact. Still confirmed by actually running the suite (step 6),
  not assumed.
- `body-layer/tests/test_naked_eye_source.py`, `test_mock_flight_chain.py`,
  `test_association.py`, `test_detection_trace.py` — the four test files that construct
  `WorldObjectCandidate` directly (three via a literal call, one via `.from_dict`) need
  `heading_true_deg` added to their fixtures wherever a test's outcome should now depend on it;
  everywhere else, the new field's `None` default keeps them passing unchanged. Confirmed by
  reading: production code builds every `WorldObjectCandidate` through `.from_dict` only — no
  other call site exists in `src/`.
- **Not touched**: `clustering.py`, `naked_eye_source.py`'s `ClusterCandidate` construction,
  anything under `belief/`.

### The formula

`apparent_extent_m(profile, aspect_deg)`:

```
if profile.length_m is None or profile.width_m is None or profile.height_m is None:
    return profile.size_m               # no measured dimensions -- untouched by this feature
if aspect_deg is None:
    return profile.size_m               # dimensions exist, but aspect is unknown -- don't guess
theta = radians(aspect_deg)
projected_width_m = profile.length_m * abs(sin(theta)) + profile.width_m * abs(cos(theta))
return max(projected_width_m, profile.height_m)
```

**Correction, coordinator review, 2026-09-21.** The first draft of this plan proposed giving
every un-migrated row a "cubic fallback" (`length_m = width_m = height_m = size_m`) and claimed
this reproduced today's exact detection range "at any aspect" because "`sin`+`cos` of a cube's
equal sides collapses back to the same constant." That claim is false and was caught before
implementation, not after: for `L = W = s`, the formula gives `s·(|sinθ| + |cosθ|)`, which equals
`s` only at θ = 0° and 90° and rises to `s·√2` (a **41% increase**) at θ = 45°, verified
numerically. Checking only the two angles that happen to be fixed points of `sin`/`cos` is exactly
the kind of proof-by-convenient-example this project's own conventions warn against, and the
consequence would have been serious: a silent, across-the-board range increase at every oblique
aspect, on the heels of the 2026-09-21 sortie finding the model already sees *too little* at
presence — it would have read as evidence aspect modelling works, and been baked into the very
threshold recalibration this plan explicitly says to defer. **Fixed by making the dimension fields
optional and `None` by default** (see "Affected Modules" above) rather than deriving them from
`size_m` — this is not merely a bug fix but a better fact-honesty story: `None` says "this unit's
real dimensions are not known," where the cube claimed a specific (false) shape for a 6 m truck.
It also makes the set of aspect-corrected types **explicit and growable** rather than "all rows,
degraded" — a real, visible boundary a later pass can extend one profile at a time, and a natural
control group (corrected vs. uncorrected types) for the eventual threshold recalibration to check
its own work against.

`aspect_deg` is the angle between the candidate's heading and the observer→candidate bearing,
wrapped to `[0, 180]` (0° = viewed from directly ahead or astern, 90° = broadside) — computed in
`check_visibility` from values it already has (`candidate.heading_true_deg`,
`candidate_bearing_deg`), no new geometry module needed.

**This is the formula from the brief, evaluated rather than accepted on faith, as instructed.**
It matches the user's own "fairly linearly" framing (`sin`/`cos` are the correct linear-in-angle
projection of a rectangular footprint, not an approximation reached for convenience) and it is the
right shape for the specific bug it fixes: `max(projected_width, height)` means a mast's `height_m`
term dominates at every aspect, so the S-300 case requires no special-casing — exactly the
"subsumes the radar bug" framing in the 2026-09-21 research doc's own follow-up section. One
deliberate simplification, stated rather than silently assumed: this ignores the observer's own
look-down angle when foreshortening `height_m` (a mast viewed from steeply above presents less of
its height than one viewed level) — correct at the shallow depression angles typical of level
cruise, wrong in the limit of looking straight down. Not fixed here: adding an elevation term
couples this formula to `body_relative_direction`'s pitch/bank math for a refinement the brief did
not ask for and the current data cannot validate (the fixture and the one sortie both used
roughly level flight). Flagged as a known simplification, not a silent gap.

### Backward compatibility: `size_m` stays exactly as it is, a real field, not derived

Decided, not left open: `size_m: float` remains a plain required field on `ObjectTypeProfile`,
completely unchanged — it is not replaced by a `@property` computed from the new dimension fields.
This is the corrected version of the design above (see "Correction, coordinator review" in "The
formula"). Reasons this beats a derived property:

- `clustering.ClusterCandidate.size_m` and both calibration-test smoke checks
  (`test_object_model_resolves_every_object_type`, `test_computed_tier_matches_ground_truth`) read
  `.size_m` today and are explicitly out of scope for this pass (see "Scope cut" below) — with
  `size_m` untouched, those consumers see *zero* behavioural change, not merely a computed value
  that happens to match.
- The ~148 un-migrated rows are **not edited at all** — no bulk substitution, no factory function,
  no mechanical find/replace step. `length_m`/`width_m`/`height_m` default to `None` on the
  dataclass, so every existing `ObjectTypeProfile(size_m=X, op_class=Y)` literal in the table is
  untouched source text. This is a stronger no-regression guarantee than "the derived value happens
  to equal the old one" — there is no derivation to get subtly wrong, because those rows carry no
  new fields with meaningful values at all.

### S-300 dimensions: real values, sourced, not fabricated

The two known-broken rows (`S-300PS 40B6M tr`, `"tall-mast" TR`; `S-300PS 64H6E sr`, "low-trailer"
SR) are the only rows this pass gives real measured `length_m`/`width_m`/`height_m` — matching the
brief's "at minimum" scope and the sortie research doc's own framing that this is a data bug, not a
calibration error. Each of these two rows also keeps a `size_m` value (still required, per the
corrected design above) — set to `max(length_m, width_m, height_m)` by hand at authoring time (a
literal number in the source, not a computed property), so the row behaves sensibly for the
consumers that only ever read `.size_m` (clustering, the calibration-test smoke check) and matches
what `apparent_extent_m` would fall back to if aspect were ever unknown for this row. **This plan
does not invent the L/W/H numbers themselves.**
Implementer's job: source real-world published dimensions for these two vehicle/radar systems
(publicly available specification data, not a DCS file — this is ordinary hardware, not a DCS
internal) and record the sourced figures with citation in a dated file under
`body-layer/research/`, following the same "cite, don't guess" discipline `object_model.py`'s own
docstring already demands for its keyword-vocabulary claims. If good sourced numbers cannot be
found for one of the two, use a documented rough estimate (e.g. mast height clearly ~10 m per the
sortie's own visual description) rather than blocking the whole change on it — but say so
explicitly in the profile's own inline comment, the same way every other estimated figure in this
file is already flagged.

### Scope cut: clustering stays scalar

`clustering.ClusterCandidate.size_m` (fed by `naked_eye_source.py:426`,
`size_m=profile.size_m`) is **left reading the plain `size_m` field, unchanged, in this pass.**
Threading aspect into clustering would require per-member aspect (each cluster member has its own
heading) feeding an angular-unit-width average that the separability math was not designed around,
and the brief's own scope (detection-range formula, S-300 bug, aspect plumbing) does not ask for
it. Left as a named follow-on, not silently dropped: a tall/thin object's cluster-separability
"unit width" is still its old scalar `max(L,W,H)` today, so a mast could still be
over/under-counted relative to a neighbour in a mixed cluster. Low-value to fix now — clustering
only matters once multiple objects are close enough to angularly compete, which is rarer for a
single skyline-breaking SAM radar than for a `check_visibility` at-range detection.

### Implementation Plan

1. `object_model.py`: add the three optional dimension fields (default `None`) to
   `ObjectTypeProfile` and add `apparent_extent_m()`. The ~150 existing rows need no edit — confirm
   this with a diff review (the table's own source lines should be untouched), not a script,
   since there is nothing to derive-and-compare against.
2. Source and add real `length_m`/`width_m`/`height_m` for the two S-300 rows, with a dated
   research-doc citation.
3. `association.py`: add `heading_true_deg` to `WorldObjectCandidate` and `from_dict`.
4. `visibility.py`: compute aspect in `check_visibility`, swap both `profile.size_m` reads for
   `apparent_extent_m(profile, aspect_deg)`.
5. Tests: `test_object_model.py` (formula + regression guard), `test_visibility.py` (aspect
   changes tier, `None` reproduces old behaviour, synthetic S-300-shaped case), fixture additions
   in the four candidate-constructing test files where a test's intent now needs a heading.
6. Confirm `test_vision_calibration.py` passes unedited by actually running it (not assumed on
   paper) — this is the check that the "no code change expected" claim above is true, not a hope.
7. Update `visibility.py`'s and `object_model.py`'s module docstrings to describe the new formula
   and the S-300 fix, matching this codebase's convention of a load-bearing module docstring.

No performance/scale stage: this adds one trig computation per `check_visibility` call, on top of
an already more expensive terrain-LOS SQL check in the same function — not a hot-path concern.

### Risks & Unknowns

- **Test blast radius is likely wider than the four files named above**, per the cones-slice-1
  plan's own precedent ("the test blast radius went well beyond the one named test... confirmed by
  running the pipeline, not computed on paper"). Treat that as the standing expectation here too —
  run the full body-layer suite, don't assume the affected-file list above is exhaustive.
- **`LOWRES`/`MEDRES`/`HIRES_ANGULAR_RADIUS_RAD` are explicitly not touched by this plan**, per the
  brief and per the sortie research doc's own reasoning: recalibrating the tier thresholds now,
  before aspect exists, would fit constants to an error aspect is about to partly explain, and
  unpicking that later is harder than waiting. With the corrected `None`-dimensions design, this
  plan changes detection-range behaviour for **exactly two profiles** (the S-300 rows) and leaves
  every other type's range calculation byte-for-byte identical to today at every aspect — there is
  no longer a "most vehicles change slightly" case to reason about, which is a direct consequence
  of the coordinator-caught correction above, not a re-derivation of the original (wrong) claim.
- **A parametrized-only-at-fixed-points test is a real failure mode, worth naming generally, not
  just as history.** The original cubic-fallback bug would have passed a test that only checked
  aspect 0° and 90°, because those are exactly the two angles at which the wrong formula happens to
  agree with the right one. Any future test of `apparent_extent_m` (or of anything trigonometric)
  must include at least one non-axis-aligned angle, or it proves nothing about the general case —
  stated here as a standing rule for this plan's own tests (see the `test_object_model.py` bullet
  above), not only as a postmortem note.
- **Real-world S-300 dimensions are the one piece of new "fact" this plan introduces.** If the
  Implementer cannot find good sourced figures, the profile risks becoming another
  guessed-and-uncited entry of exactly the kind `object_model.py`'s own docstring elsewhere warns
  against (the OP_SHIP/SA-* keyword rework was explicitly a correction of that failure mode). Flag
  loudly in review if the sourcing step gets skipped under time pressure.
- **`heading_true_deg=None` behaviour is a real design choice, not a formality**: for a profile
  with measured dimensions but unknown aspect, `apparent_extent_m` falls back to `profile.size_m`
  — a value the two S-300 rows author by hand as `max(length_m, width_m, height_m)` (see "S-300
  dimensions" above), so in practice this is "fall back to the largest of the three axes," a
  generous default. An alternative (e.g. falling back to `width_m` alone, assuming a "typical"
  partial-broadside view) would be less generous but would be inventing a specific aspect
  assumption with no more basis than the one being avoided. `size_m`-as-`max(L,W,H)` was picked
  because it exactly reproduces current behaviour for these profiles (nothing regresses when
  heading is unknown), not because it is independently the "most correct" unknown-aspect estimate
  — flagged so the user can override if a different default is wanted.
- **Aspect ignores observer look-down angle** (see "The formula" above) — correct at level flight,
  increasingly wrong the steeper the dive. Not fixed here; no data exists yet to calibrate it.

### Second-order effect

This is the plumbing (`heading_true_deg` on the wire-to-candidate path, `apparent_extent_m` as a
named, callable formula) that the deferred `LOWRES`/`MEDRES` tier-threshold recalibration will
depend on to separate "genuine threshold error" from "aspect-confound error" in the next
calibration sortie's data — without it, that recalibration pass would have no way to tell the two
apart and would risk baking the aspect confound into new constants, which is exactly the outcome
the sortie research doc flags as the reason to defer. It also removes one contaminating data
source (the S-300 rows) from every future calibration sortie's readings.

### Decisions Requiring User Input

- **S-300 dimension sourcing** — real-world published figures should be found and cited, not
  estimated from the sortie's own visual description alone; if the user has a preferred reference
  (a manual, a known-good spec sheet) for the 40B6M/64H6E, naming it now saves the Implementer a
  research detour.
- **The `heading_true_deg=None` fallback (`max(L,W,H)`)** — recommended above for the
  no-regression property it has, but it is a real modelling choice (most-generous-of-three-axes)
  and not the only defensible one; flagged rather than silently picked, per this role's mandate on
  local-but-visible decisions.
