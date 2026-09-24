### Debug Report

### Observed Issue

Live sortie on `main` (`a04eec8`, first flight of `precise-position-belief`,
merged `c398675`) produced two impossible callouts:

- `"couple contacts, 4 o'clock, 87.5 kilometres."` -- 87.5 km is ~9x the
  naked-eye detection cap (`perception/visibility.py`'s
  `NAKED_EYE_RANGE_CAP_M`, 10,000 m).
- `"truck 5 o'clock, 79.5 kilometres is KrAZ truck."` -- same range-runaway
  symptom, plus "truck" said twice.

### Hypothesis

`belief/position_belief.py`'s `fold_position` (the information-form 2x2
covariance fusion `Contact.record`/`from_percept` use for every believed
position) had no protection against two failure modes, and nothing anywhere
checked a fused position against what could physically have been detected.
Separately, `belief/speech.py`'s `_identification_lead` stutter guard only
matched an *exact* string, not a class word appearing as one word inside a
longer type name.

### Evidence

**Reproduced the given numeric case** (`fold_position(None, x=0, z=3000,
uncertainty=(60,800), bearing=0, t=0)` then folded with `x=350, z=5000,
bearing=5, t=1`): fused mean `(-5308.1, 3790.7)`, range 6522.7m -- outside
both inputs' own ranges (3000m, ~5012m), confirming the report.

**Root cause, mechanism 1 -- ill-conditioned triangulation.** Each look's
covariance is a long thin ellipse (tight cross-range, loose down-range).
Intersecting two near-parallel ellipses that *disagree* along their shared
imprecise axis is arbitrarily sensitive to that disagreement -- the
intersection point can land far outside either input. Initially tried
gating this purely on bearing separation between the new look and the
prior covariance's dominant axis; this broke a real, important case
(`tests/test_optic_policy.py::test_a_well_refined_contact_collapses_the_
look_to_a_single_step`, same-bearing *repeated identical* looks, which must
keep tightening -- ordinary averaging, not ill-conditioned triangulation).
Bearing separation alone cannot distinguish "near-parallel and consistent"
(safe) from "near-parallel and disagreeing" (dangerous). Replaced with a
residual-sanity test: after computing the ordinary fused mean, require it
to sit within `FUSION_SANITY_SIGMA` (5) sigma of *at least one* input,
judged against that input's own individual covariance (not the sum the
pre-existing `association_over_time.passes_gate` already gates on --
summed variances are deliberately generous, since fusion *intersects*
rather than sums, and a residual that easily passes that generous
outer gate can still be nonsense post-intersection). Verified: the bug's
own numbers score ~14 sigma from both inputs (fails); a repeated-identical
look scores 0 (passes, tightens correctly); a 100m near-parallel residual
scores <1 (passes); a genuinely well-conditioned perpendicular pair is
numerically unaffected (pinned exact pre-fix numbers in a regression test).

**Root cause, mechanism 2 -- no detection-envelope gate at all.** Nothing
checked a fused mean against the physical range at which the producing
channel could ever detect anything (`perception.visibility.
NAKED_EYE_RANGE_CAP_M` = 10,000m for naked-eye,
`perception.association.RANGE_CAP_M` = 5,000m for the scope/hybrid
channel). Constructed a "slow directional drift" scenario -- 21
consecutive naked-eye polls, each only a small (0.3 deg bearing / 150m
range) step, individually well within `association_over_time.passes_gate`'s
3-sigma spatial gate and within `FUSION_SANITY_SIGMA` at every single step
-- and confirmed the believed range crept past 10,000m by poll ~20 with
mechanism 1's guard never firing once (see `test_slow_directional_drift_
never_reports_a_range_beyond_the_detection_cap`'s own exploration in
`repro8.py`/`repro9.py`, not committed). This is a second, independent
failure mode: a persistent bias that is individually plausible at every
step but not bounded in aggregate.

**Confirmed the association gate is not itself broken.** The task's own
numeric case (5 degree separation, large residual) does not even reach
`fold_position` through `ContactStore.ingest` in production --
`association_over_time.passes_gate`'s pre-existing 3-sigma spatial gate
already rejects that large a disagreement and founds a fresh contact
instead. Confirmed directly (`passes_gate` returns `False` for that exact
pair). The live defect's real path was the "slow drift" shape above, not a
single big jump.

**`_identification_lead` stutter bug** (`belief/speech.py`): the guard
compared `spoken.lower() == unit_type.lower()` exactly. For `value="KrAZ
truck"`, `unit_type="KrAZ truck"`, `spoken="truck"` (`_OP_CLASS_DISPLAY[
"OP_TRUCK"]`) -- `"truck" != "kraz truck"`, so the guard never fired,
producing `"truck ... is KrAZ truck."` Confirmed by reading the function
directly against the reported callout.

**Cardinality finding ("couple contacts").** `association_over_time.
passes_gate` sizes its spatial gate from `contact.position.covariance`
directly (that module's own docstring) -- a covariance the position defect
let run away or blow up would also widen the gate meant to keep unrelated
objects apart, so a genuinely different real object's own count claim
could incorrectly fold onto the wrong contact. Checked `perception.
clustering`: it clusters on each poll's own true `LoGetWorldObjects`
geometry, never on fused belief (module docstring), so a cluster's own
count is never itself position-dependent -- the gate above is the only
place the two defects could interact. **The position fix alone is expected
to restore correct cardinality separation**, since it bounds
`contact.position.covariance` (never a runaway mean, never an unclamped
blow-up), which is what the gate reads. Did not re-run old code to prove
the counterfactual; instead pinned the invariant directly with
`test_position_runaway_does_not_corrupt_a_second_contacts_cardinality`: a
contact driven through the same 21-poll drift sequence still correctly
excludes a well-separated, genuinely different object's plural report from
its own gate, post-fix. **No change was made to `perception.clustering` or
`belief.cardinality`** -- consistent with "if the position fix alone
restores it, change nothing here."

**Separate latent bug found, not fixed (out of scope).** While picking
sigma values for a "repeated identical look" regression test,
`(sigma_cross_m=157.08, sigma_down_m=510.0)` (the exact pair
`test_optic_policy.py`'s pre-existing calibration test uses) exposed that
`Covariance2D.inverse`'s `_MIN_DETERMINANT = 1e-9` floor is calibrated for
covariance-scale determinants (~1e9) but an *information*-matrix
determinant (the inverse of a covariance) can legitimately be as small as
~1e-10 after only one fusion -- below the floor -- silently corrupting the
result (confirmed: `inv.inverse() != cov` for this pair, off by ~6.4x).
This is pre-existing on `main` (unrelated to this defect;
`git show main -- body-layer/src/belief/position_belief.py` shows
`_MIN_DETERMINANT`/`inverse()` unchanged) and not touched here --
`test_optic_policy.py`'s own test only asserts a coarse property (`len(
steps) == 1`) that happens not to be sensitive to it. Worth a follow-up
ticket; not fixed under this task's scope (a different defect, no reported
symptom tied to it).

### Fix Applied

`body-layer/src/belief/position_belief.py`:

1. **`FUSION_SANITY_SIGMA` guard inside `fold_position`.** After computing
   the ordinary information-form fused mean, reject it (hold the prior
   unchanged, inflated for elapsed motion only) unless it sits within 5
   sigma of at least one input's own individual covariance. This is the
   root-cause fix for the single-jump ill-conditioning mechanism.
2. **`clamp_to_detection_envelope(fused, prior, observer, max_range_m)`**,
   a new function, called by `belief/contacts.py`'s `Contact.record`/
   `from_percept` immediately after `fold_position` -- not built into
   `fold_position` itself, since the envelope is a fact about a specific
   look's own observer and the producing channel's own physical detection
   cap, neither of which `fold_position` should need to know (preserves
   its `(estimate, estimate) -> estimate` signature for a future
   non-percept measurement with no envelope to check). Violating the
   envelope **holds the prior** (same policy as the ill-conditioning
   guard) rather than clamping onto the boundary or discarding outright --
   the plan's own reasoning: an out-of-envelope look is evidence the
   fusion went wrong, not evidence of a position. A **no-op for a founding
   look** (`prior is None`) -- in production the channel's own admission
   gate has already range-capped it before it could reach here, and test
   fixtures that deliberately construct an out-of-envelope founding look
   for unrelated reasons (`test_range_crossing_never_fires_beyond_the_
   cap`, `test_engagement_respects_the_altitude_floor`) must not have that
   state silently rewritten.

`body-layer/src/belief/contacts.py`: wires `clamp_to_detection_envelope`
into `record()`/`from_percept()`, with a per-`Percept.source` cap lookup
(`_MAX_DETECTION_RANGE_M`, naked-eye -> `perception.visibility.
NAKED_EYE_RANGE_CAP_M`, scope/hybrid -> `perception.association.
RANGE_CAP_M`, unrecognised source -> the larger of the two, conservative).

`body-layer/src/belief/speech.py`: `_identification_lead`'s stutter guard
changed from an exact-string match to a whole-word containment test
(`re.search(rf"\b{re.escape(spoken.lower())}\b", unit_type.lower())`),
catching "truck" appearing as a whole word inside "KrAZ truck", not just
identical strings.

### Verification

`cd body-layer && .venv/bin/ruff format src tests && .venv/bin/ruff check
src tests && .venv/bin/mypy src && .venv/bin/pytest tests -q` (venv
referenced from the main checkout, `/Users/sg/Code/DCS-petrobrain/
body-layer/.venv`, since the worktree carries no venv of its own):

- `ruff format`: 103 files already formatted (2 files reformatted once
  during the change, then clean).
- `ruff check`: All checks passed.
- `mypy src`: Success, no issues found in 48 source files.
- `pytest tests -q`: **1189 passed, 4 xfailed** (baseline on `main`: 1177
  passed, 4 xfailed -- 12 new tests, no regressions, no new xfails).

New regression tests, all failing against pre-fix code and passing after:

- `tests/test_position_belief.py`: the exact numeric reproduction holds
  the prior; a repeated-identical-look case still tightens (guards against
  a bearing-only guard's own failure mode); a 100m near-parallel residual
  still fuses; a perpendicular pair is bit-for-bit unaffected;
  `clamp_to_detection_envelope`'s no-op/hold/founding-pass-through cases.
- `tests/test_contacts.py`: end-to-end through `ContactStore.ingest` --
  two near-parallel disagreeing naked-eye looks stay near their true
  range; a 21-poll slow directional drift never reports beyond
  `NAKED_EYE_RANGE_CAP_M`; a well-separated genuinely different object's
  plural count never bleeds onto a position-perturbed contact's own
  cardinality.
- `tests/test_speech.py`: `"truck ... is KrAZ truck"` now opens with
  "unit", not "truck" twice.

Manual reproduction also re-run after the fix (`repro2.py`-equivalent,
not committed): the task's own numeric case now returns the prior
unchanged (`x=0.0, z=3000.0, range=3000.0`) instead of `(-5308.1, 3790.7,
range=6522.7)`.

### 2026-09-25 addendum -- required fix from review (`c1cba89`)

**Observed Issue.** Review of `b5b79b8` (`plans/position-belief-runaway/review.md`) found the
"found, not fixed, out of scope" `Covariance2D._MIN_DETERMINANT = 1e-9` floor above is neither
narrow nor safely deferrable: reachable for any same-bearing repeated naked-eye look beyond
~2.7km (well inside the 10km envelope), corrupts the fused *mean* (not just reported
uncertainty), and makes the brand-new `FUSION_SANITY_SIGMA` guard itself misfire on a legitimate
100m near-parallel residual at `naked_eye_sigma_m(3000.0)` -- the same sigma pair
`test_optic_policy.py`'s pre-existing ten-fold calibration test already uses.

**Hypothesis.** `Covariance2D.inverse()` is called on two very different scales of matrix --
covariance-form (real declared sigmas, determinants ~1e7-1e12 m^4) and information-form (their
inverse, determinants ~1e-8 to 1e-12) -- and one absolute floor cannot be "near zero" for both at
once. The floor needs to be relative to each matrix's own scale, not a fixed constant.

**Evidence.** Reproduced all three of the review's findings directly, against the actual
`fix/position-belief-runaway` branch source (not re-derived from the review's numbers): the
floor-reachability table matched (`det(info_sum)` crosses `1e-9` between 2000m and 2700m); the
repeated-identical-look-at-(3000,0) drift matched exactly
(`3000.0 -> 1853.5 -> 2125.3 -> 2293.7 -> 2408.6 -> 2492.0`); the guard misfire matched (the
100m/5deg residual held the prior instead of fusing). Also confirmed mathematically and
numerically that `determinant / trace^2` -- a matrix's own eigenvalue ratio `ab / (a+b)^2` -- is
exactly invariant under `inverse()` (verified: both the naked-eye covariance at 3000m and its own
`.inverse()` report the identical ratio, `0.0791372...`, to full float precision), which is what
makes a relative floor expressed against `trace^2` the correct fix rather than a second
scale-specific constant: it guards genuine near-singularity (an axis's variance collapsed toward
zero relative to the matrix's own other axis) at any scale, covariance or information form alike,
using the one dimensionless quantity that means the same thing in both.

Trap 1 (`test_optic_policy.py::test_a_well_refined_contact_collapses_the_look_to_a_single_step`,
which folds ten times at this exact sigma pair): its assertion is `len(steps) == 1`, a coarse
property, not any of the fold's own numeric intermediate values -- confirmed by reading the test
body directly. It passed before this fix (i.e. against the clamped, corrupted intermediate
covariances) and still passes after (against the corrected ones) with no change to the test
itself required -- the clamping bug happened not to matter to *this* test's specific coarse
assertion, only to the mean and to the new guard's mahalanobis check, both fixed here.

**Fix Applied.** `body-layer/src/belief/position_belief.py`: replaced the absolute
`_MIN_DETERMINANT: Final[float] = 1e-9` with `_MIN_DETERMINANT_RATIO: Final[float] = 1e-9`
(same numeric value, different meaning) applied as `max(_MIN_DETERMINANT_RATIO * trace * trace,
_MIN_DETERMINANT_ABSOLUTE)` inside `Covariance2D.inverse()` -- `_MIN_DETERMINANT_ABSOLUTE = 1e-300`
is a pure backstop for the fully-degenerate `trace == 0` case, where a relative floor would itself
be zero. `body-layer/tests/test_position_belief.py`: added
`test_fold_position_repeated_identical_look_is_exact_at_floor_triggering_sigma` (pins the mean
staying exactly put across six identical folds at the floor-triggering sigma pair -- fails
against the pre-fix absolute floor, confirmed by direct execution before applying the code
change) and
`test_fold_position_moderate_near_parallel_residual_still_fuses_at_floor_triggering_sigma` (pins
the guard-misfire case fusing rather than holding, same pair). Updated
`test_fold_position_repeated_identical_look_still_tightens`'s docstring to point at the new tests
and record that the bug it used to route around is now fixed rather than merely deferred.

**Deliberately not fixed here (logged as a decision, not an oversight):** `Contact.record`
(`body-layer/src/belief/contacts.py`) still bumps `last_seen_sim = percept.t_sim`
unconditionally, even when `fold_position`'s `FUSION_SANITY_SIGMA` guard or
`clamp_to_detection_envelope` holds the prior -- so a held position reads as fresh/confident to
`certainty_of`/`position_confidence` for as long as the hold lasts. Pre-existing field semantics
(review's own finding, not a new regression from either guard), bounded in practice (~20s,
`GATE_GROWTH_RATE_MPS`-driven recovery, per the review's own check), and orthogonal to the
determinant-floor fix above -- left as a follow-up rather than folded into this required fix,
which is scoped to the floor and its direct consequences.

**Verification.** `cd body-layer && .venv/bin/ruff format src tests && .venv/bin/ruff check src
tests && .venv/bin/mypy src && .venv/bin/pytest tests -q` (main checkout's venv, worktree has
none of its own): `ruff format` -- 103 files left unchanged; `ruff check` -- all checks passed;
`mypy src` -- success, no issues found in 48 source files; `pytest tests -q` -- **1191 passed, 4
xfailed** (this branch's own prior baseline was 1189/4 -- 2 new tests, no regressions, no new
xfails). Both new regression tests independently confirmed to reproduce the review's exact
numbers when run against the pre-fix source before the code change was applied (not merely
asserted to fail -- executed).
