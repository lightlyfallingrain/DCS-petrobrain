"""The perception-side error model and perturbation -- `plans/
precise-position-belief/plan.md`. Replaces `naked_eye_source.py`'s
reporting-vocabulary quantisation (the deleted `_quantise_bearing`/
`_quantise_range_m`), which snapped every estimate onto one of a small
number of buckets and, worse, snapped range onto the bucket's *upper
bound* -- a systematic long bias of up to a full bucket width, not a
conservative coarsening (plan's "The diagnosis, verified").

**The model.** A look's error ellipse is elongated along its own line of
sight: `sigma_down_m = RANGE_FRACTIONAL_SIGMA * true_range_m` (derived from
ED's own `OP_D*` range-bucket ladder, which coarsens as range grows -- the
signature of a fractional estimation error), `sigma_cross_m =
radians(BEARING_SIGMA_DEG) * true_range_m` (a declared judgement constant,
see that name's own docstring). Both scale with range, so the model
behaves sensibly at every distance without a lookup table.

**Per-optic, as of `BL-B64` Stage 1b (`BL-B55`, folded into that entry --
`plans/9k113-sight/plan.md` §14).** `look_sigma_m` (renamed from
`naked_eye_sigma_m` -- it is no longer naked-eye-only) takes the active
`perception.optics.Optic` and scales both axes by it. `UNAIDED_OPTIC` and
`BINOCULAR_OPTIC` are unaffected by construction (both scales are 1.0,
pinned by `test_estimation.py`) -- only the two sight optics get tighter
numbers, because that is what is sourced/judged so far; the live asymmetry
`BL-B55`'s own roadmap entry flags for binoculars (seeing further while
believed no more precisely) is not fixed for binoculars in this pass,
deliberately: there is no sourced figure to assign it, and fixing the
9K113 case first is what this entry exists to do. **Down-range and
cross-range scale differently, because they come from different
instruments** (direction §2/§11): down-range from the sight's stadiametric
aid (`_RANGE_SIGMA_SCALE_BY_OPTIC`, one judgement constant per
sight optic, tunable), cross-range from the sight's own field of view
relative to the binocular FOV `BEARING_SIGMA_DEG` is itself calibrated
against (`_SIGHT_BEARING_SIGMA_SCALE_BY_OPTIC`, derived from the FOV
ratio, not an independent judgement call). **Never derived from
`UNAIDED_OPTIC`'s own `fov_half_angle_deg`** -- that field is a
peripheral-vision envelope as of direction §14, not a measure of pointing
precision, so it has no bearing on this scale at all.

**A group is ranged once, with a shared draw, by construction, not by a
special case here** (direction §11). `naked_eye_source._build_observation`
calls `look_sigma_m`/`perturbed_bearing_range` exactly once per cluster
already (one `Observation` per group), so threading the active optic
through that one existing call is what makes a group's position error a
single shared draw -- nothing in this module has to know what a "group"
is for that to hold.

**Perturb, don't just declare** (plan Decision 1, user-approved): stating
an uncertainty on an exact-truth number would make `belief/percept.py`'s
no-omniscience boundary a comment, not a mechanism -- a heavily-observed
contact would converge exactly onto truth. Every reported bearing/range is
therefore perturbed by a draw from its own declared error ellipse, in two
parts, both computed here and combined by `perturbed_bearing_range`:

- **Per-look noise**, drawn deterministically from a hash of the
  observation's own id -- reproducible under replay (no global RNG, no
  cross-run divergence). This is what averages down across repeated looks
  (`belief.position_belief`'s covariance fusion).
- **A per-object systematic bias**, drawn once from a hash of the *object*
  id and never re-drawn, scaled to `SYSTEMATIC_BIAS_FRACTION` of the
  single-look sigma. This never averages out: a heavily-observed contact
  converges to a position that is precisely and confidently *wrong* by
  this amount -- the deliberate point (plan's "Precision is not
  omniscience, made structural"). The object id itself never leaves
  `perception/`; only the perturbed bearing/range numbers and the declared
  sigmas cross into `belief/`.

No `belief` import anywhere in this module -- `perception` must not import
`belief` (project invariant)."""

from __future__ import annotations

import hashlib
import math
from typing import Final

import tuning
from perception.optics import (
    BINOCULAR_OPTIC,
    SIGHT_NARROW_OPTIC,
    SIGHT_WIDE_OPTIC,
    Optic,
)
from perception.visibility import NAKED_EYE_RANGE_CAP_M

#: Down-range (along line-of-sight) 1-sigma error as a fraction of true
#: range. Derived, not invented, from ED's own `OP_D*` range-bucket ladder
#: (`perception.naked_eye_source`'s former `_RANGE_BUCKETS_M`, now
#: deleted) -- the ladder steps 100m to 1km, then 500m, then 1000m, which
#: as a fraction of range is 10-33%, clustered ~15-20%. The ladder
#: *coarsens as range grows*, the signature of an estimation error that
#: grows with range -- the vocabulary carries information about the
#: underlying ability even though this module no longer reads the table
#: itself.
RANGE_FRACTIONAL_SIGMA: Final[float] = 0.17

#: Cross-range (perpendicular to line-of-sight) 1-sigma bearing error,
#: degrees. **Not measured, cannot be** -- it is the crewman's own pointing
#: precision, not anything DCS reports. Bounded on both sides by measured
#: things (above the optical resolution floor,
#: `perception.clustering.RESOLUTION_ANGULAR_RADIUS_RAD`; well below the
#: 15deg clock half-bucket) but the exact value is a declared judgement
#: constant (plan Decision 3, user-approved at 3.0). **This is what sets
#: the binocular sweep width in `belief.optic_policy`** (Stage 5) -- if a
#: live sortie says Petrovich's callouts point at the wrong place, this is
#: the number to move. The load-bearing claim is the *ratio* to `RANGE_
#: FRACTIONAL_SIGMA`-derived down-range error (cross-range is several times
#: smaller), not the exact value.
BEARING_SIGMA_DEG: Final[float] = tuning.real(
    "perception.estimation.BEARING_SIGMA_DEG", 3.0, lo=0.1, hi=14.0, status="judgement"
)

#: Fraction of a look's own single-look sigma the never-redrawn per-object
#: systematic bias is scaled to. This is what keeps a heavily-observed
#: contact from converging on truth (plan's "Precision is not omniscience,
#: made structural") -- `belief.position_belief`'s fused-estimate floor is
#: this same fraction of a single-look sigma, since the bias never
#: averages out across repeated looks.
SYSTEMATIC_BIAS_FRACTION: Final[float] = 0.4

#: The ownship-relative observation channel's own noise term
#: (`plans/attack-run/plan.md` Decision 16 item 5, settled by the user's
#: own §20, 2026-10-14: *"Relative direction while he's looking at it ->
#: exact."*). `0.0` makes `perturbed_relative_direction` below an identity
#: function -- present as a parameter, not a structural property, so a
#: future non-zero value is a one-line change rather than a rewrite
#: (Decision 11 REVISED). **Not the same error model as `BEARING_SIGMA_
#: DEG` above, and must never be set from it**: that constant models
#: *stating* a bearing from memory, this one models *pointing* at a
#: target while looking straight at it -- the plan's own "two mechanisms"
#: argument (§18). At 1 km, 1 degree of pointing error is 17 m against
#: the proposed 5-degree lined-up band, which is why a non-zero value
#: would be felt as chatter near the band edge rather than being free.
RELATIVE_DIRECTION_SIGMA_DEG: Final[float] = 0.0

#: Down-range fractional-sigma coefficient for a 9K113 wide look --
#: `BL-B64` Stage 1b (`plans/9k113-sight/plan.md` §14). Mirrors
#: `RANGE_FRACTIONAL_SIGMA`'s own shape (a fraction of true range), with a
#: smaller coefficient reflecting the stadiametric aid the sight carries
#: that the naked eye does not -- the Mi-24P manual's own reticle
#: calibration (5000 m / 2.5 m, 1000 m / 2.5 m; `body-layer/research/
#: 2026-09-20-9k113-sight-optics-from-manual.md`). **A stated assumption,
#: not a measurement** -- the plan's own phrase -- tuned from flying like
#: every perception constant before its first sortie.
SIGHT_WIDE_RANGE_SIGMA_SCALE: Final[float] = tuning.real(
    "perception.estimation.SIGHT_WIDE_RANGE_SIGMA_SCALE",
    0.5,
    lo=0.05,
    hi=1.0,
    status="judgement",
)

#: Same role as `SIGHT_WIDE_RANGE_SIGMA_SCALE` above, for the narrow (x10)
#: setting -- smaller, because the x10 magnification reads the same
#: stadiametric marks at finer resolution.
SIGHT_NARROW_RANGE_SIGMA_SCALE: Final[float] = tuning.real(
    "perception.estimation.SIGHT_NARROW_RANGE_SIGMA_SCALE",
    0.3,
    lo=0.05,
    hi=1.0,
    status="judgement",
)

#: Down-range scale per optic for `look_sigma_m` below -- `1.0` (no
#: change) for every optic not named here, which is both `UNAIDED_OPTIC`
#: and `BINOCULAR_OPTIC` today (module docstring's "unaffected by
#: construction"). Keyed by `Optic.name`, not by identity, so a synthetic
#: test `Optic` sharing a sight's name picks up its scale too -- the same
#: reasoning `Optic.name` is a plain string for elsewhere in this
#: codebase.
_RANGE_SIGMA_SCALE_BY_OPTIC: Final[dict[str, float]] = {
    SIGHT_WIDE_OPTIC.name: SIGHT_WIDE_RANGE_SIGMA_SCALE,
    SIGHT_NARROW_OPTIC.name: SIGHT_NARROW_RANGE_SIGMA_SCALE,
}

#: Cross-range scale per optic -- **derived from the FOV ratio against
#: `BINOCULAR_OPTIC`, not an independent judgement constant**
#: (`BEARING_SIGMA_DEG`'s own docstring: "this is what sets the binocular
#: sweep width," i.e. that is the regime it is already calibrated
#: against). A narrower field is a tighter bearing read (direction §11);
#: the 9K113's wide setting has a *wider* true field than compact
#: binoculars despite its magnification (11.5 deg full vs. ~8.5 deg --
#: `optics.py`'s own docstring), so its scale is honestly > 1.0, while
#: narrow's tighter field gives < 1.0. Computed once at import, from the
#: optics' own sourced `fov_half_angle_deg` values, not duplicated as a
#: separate literal that could drift from them.
_SIGHT_BEARING_SIGMA_SCALE_BY_OPTIC: Final[dict[str, float]] = {
    SIGHT_WIDE_OPTIC.name: (SIGHT_WIDE_OPTIC.fov_half_angle_deg or 1.0)
    / (BINOCULAR_OPTIC.fov_half_angle_deg or 1.0),
    SIGHT_NARROW_OPTIC.name: (SIGHT_NARROW_OPTIC.fov_half_angle_deg or 1.0)
    / (BINOCULAR_OPTIC.fov_half_angle_deg or 1.0),
}


#: How noisy Petrovich's sense of looking angle (up/down) is, which feeds
#: a surface unit's estimated range once fused against the size/terrain
#: judgement cue -- raising it widens the depression cue's own spread,
#: which the fusion below weighs against cue A automatically, so
#: Petrovich firms up on a ground unit's range more slowly while closing;
#: lower it for the opposite effect. `plans/
#: bl-b104-ground-contacts-on-ground/plan.md` Stage 3: the default (3.0,
#: the bearing error's own value) is not applied naively -- fused in
#: inverse distance against cue A, it reconciles the user's *"same range
#: as the azimuth angular error"* to the ground error he confirmed as
#: sensible (~700 m at 300 m AGL / 4 km) rather than the several-kilometre
#: error a naive metre-domain application of the same angle would give at
#: that geometry (`alignment.md` finding 1).
DEPRESSION_SIGMA_DEG: Final[float] = tuning.real(
    "perception.estimation.DEPRESSION_SIGMA_DEG",
    3.0,
    lo=0.1,
    hi=14.0,
    status="judgement",
)


def _deterministic_unit_gaussian_pair(seed_text: str) -> tuple[float, float]:
    """Two independent, deterministic standard-normal draws from
    `seed_text`, via the Box-Muller transform over a hash-derived uniform
    pair. Deterministic and stateless (no global RNG, no mutable seed) --
    the same `seed_text` always yields the same pair, which is what makes
    replay reproducible and lets `test_estimation.py` pin exact offsets."""
    digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
    u1_int = int.from_bytes(digest[:8], "big")
    u2_int = int.from_bytes(digest[8:16], "big")
    # Keep u1 off exactly 0.0 (log(0.0) is undefined) by mapping onto
    # (0, 1] rather than [0, 1).
    u1 = (u1_int + 1) / (2.0**64)
    u2 = u2_int / (2.0**64)
    radius = math.sqrt(-2.0 * math.log(u1))
    angle = 2.0 * math.pi * u2
    return radius * math.cos(angle), radius * math.sin(angle)


def look_sigma_m(true_range_m: float, optic: Optic) -> tuple[float, float]:
    """`(sigma_cross_m, sigma_down_m)` for a look through `optic` at
    `true_range_m` -- see module docstring's "The model" and its
    "Per-optic" section. Renamed from `naked_eye_sigma_m` (`BL-B64` Stage
    1b) -- it was never structurally naked-eye-only, only unconditionally
    so until this entry.

    `UNAIDED_OPTIC`/`BINOCULAR_OPTIC` (any `optic.name` not in either
    per-optic dict below) reproduce the pre-`BL-B64` formula exactly --
    both scales resolve to `1.0` via `dict.get`'s default, so this is a
    behaviour-preserving rename for every caller that existed before this
    entry, pinned by `test_estimation.py`."""
    bearing_scale = _SIGHT_BEARING_SIGMA_SCALE_BY_OPTIC.get(optic.name, 1.0)
    range_scale = _RANGE_SIGMA_SCALE_BY_OPTIC.get(optic.name, 1.0)
    sigma_cross_m = math.radians(BEARING_SIGMA_DEG * bearing_scale) * true_range_m
    sigma_down_m = RANGE_FRACTIONAL_SIGMA * range_scale * true_range_m
    return sigma_cross_m, sigma_down_m


def systematic_bias_m(
    object_id: int, sigma_cross_m: float, sigma_down_m: float
) -> tuple[float, float]:
    """The per-object systematic bias `(cross_offset_m, down_offset_m)`,
    drawn once from a hash of `object_id` alone and never re-drawn --
    `SYSTEMATIC_BIAS_FRACTION` of the *single-look* sigma on each axis.
    Never averages out across repeated looks (unlike `perturb_bearing_
    range`'s per-observation draw), which is the mechanism that keeps a
    heavily-observed contact converging on a wrong, confidently-held
    position rather than truth. `object_id` never leaves `perception/`."""
    z_cross, z_down = _deterministic_unit_gaussian_pair(f"bias:{object_id}")
    return (
        z_cross * SYSTEMATIC_BIAS_FRACTION * sigma_cross_m,
        z_down * SYSTEMATIC_BIAS_FRACTION * sigma_down_m,
    )


def perturbed_relative_direction(
    *, observation_id: str, forward_m: float, right_m: float, up_m: float
) -> tuple[float, float, float]:
    """Perturb one look's ownship-relative offset
    (`perception.source.RelativeDirection`'s three fields) by
    `RELATIVE_DIRECTION_SIGMA_DEG` -- applied to the azimuth/elevation
    angles the offset implies, not to `forward_m`/`right_m`/`up_m`
    directly, since a crewman's pointing precision is an angular
    quantity, the same reasoning `perturbed_bearing_range` above already
    applies to a stated bearing. Deterministic, hashed off `observation_
    id` alone via `_deterministic_unit_gaussian_pair`, same idiom as
    `perturbed_bearing_range`'s own per-look draw.

    **At `RELATIVE_DIRECTION_SIGMA_DEG == 0.0` this is an identity
    function** -- the draw is skipped entirely rather than taken and
    scaled to zero, so §18's "exact while the look holds" (`plans/
    attack-run/plan.md` Decision 16 item 5) is a parameter, not a
    structural property (Decision 11 REVISED): changing the constant is
    what turns this into a real perturbation, no code path changes."""
    if RELATIVE_DIRECTION_SIGMA_DEG == 0.0:
        return forward_m, right_m, up_m
    horizontal_m = math.hypot(forward_m, right_m)
    slant_m = math.hypot(horizontal_m, up_m)
    if slant_m <= 0.0:
        return forward_m, right_m, up_m
    azimuth_rad = math.atan2(right_m, forward_m)
    elevation_rad = math.atan2(up_m, horizontal_m)
    z_azimuth, z_elevation = _deterministic_unit_gaussian_pair(
        f"relative:{observation_id}"
    )
    azimuth_rad += math.radians(z_azimuth * RELATIVE_DIRECTION_SIGMA_DEG)
    elevation_rad += math.radians(z_elevation * RELATIVE_DIRECTION_SIGMA_DEG)
    new_horizontal_m = slant_m * math.cos(elevation_rad)
    return (
        new_horizontal_m * math.cos(azimuth_rad),
        new_horizontal_m * math.sin(azimuth_rad),
        slant_m * math.sin(elevation_rad),
    )


def perturbed_bearing_range(
    *,
    observation_id: str,
    object_id: int,
    true_bearing_deg: float,
    true_range_m: float,
    sigma_cross_m: float,
    sigma_down_m: float,
) -> tuple[float, float]:
    """One look's perturbed `(bearing_deg, range_m)` estimate: the true
    geometry plus a per-look noise draw (hashed off `observation_id` alone
    -- same id in, same offset out) plus the per-object systematic bias
    (hashed off `object_id` alone, never re-drawn) -- see module docstring.

    The cross-range offset is turned into a bearing delta at the *true*
    range, not the perturbed one -- using the perturbed range there would
    make the angular offset diverge at short range for no physical reason.
    Range is floored at 0.0 (a look can perturb short of a target that is
    very close, never negative)."""
    look_cross_m, look_down_m = _deterministic_unit_gaussian_pair(
        f"look:{observation_id}"
    )
    look_cross_m *= sigma_cross_m
    look_down_m *= sigma_down_m
    bias_cross_m, bias_down_m = systematic_bias_m(
        object_id, sigma_cross_m, sigma_down_m
    )
    total_cross_m = look_cross_m + bias_cross_m
    total_down_m = look_down_m + bias_down_m

    perturbed_range_m = max(0.0, true_range_m + total_down_m)
    if true_range_m > 0.0:
        bearing_offset_deg = math.degrees(math.atan2(total_cross_m, true_range_m))
    else:
        bearing_offset_deg = 0.0
    perturbed_bearing_deg = (true_bearing_deg + bearing_offset_deg) % 360.0
    return perturbed_bearing_deg, perturbed_range_m


#: Floor for cue A's own down-range draw before it is inverted into
#: `1/D_A` below -- never 0.0 the way `perturbed_bearing_range`'s general
#: floor is, because this value is about to be the denominator of a
#: division (`plans/bl-b104-ground-contacts-on-ground/plan.md` Stage 3).
_CUE_A_MIN_RANGE_M: Final[float] = 1.0


def surface_range_estimate(
    *,
    observation_id: str,
    object_id: int,
    true_distance_m: float,
    height_above_unit_m: float,
    optic: Optic,
) -> tuple[float, float]:
    """A surface unit's own ground-range estimate, fused from two cues --
    `plans/bl-b104-ground-contacts-on-ground/plan.md` Stage 3. See that
    plan's "The model in one picture" for the derivation; this is its
    direct translation into code, not a re-derivation.

    `true_distance_m` is the true **horizontal** ground distance to the
    unit (`D` in the plan's picture) -- the caller already has this as
    the flat-projection "true range" naked-eye clustering already computes
    (`centroid.alt_m` pinned to the observer's own altitude). `height_
    above_unit_m` is the true, **signed** height of the observer above the
    unit (`h`): positive when the observer looks down at it, negative when
    the unit is above the observer (a SAM on a ridge) -- the signed
    convention is what lets a unit above the observer work through the
    same formula with an upward-looking ray, rather than a special case.

    **Cue A** is today's per-look down-range draw, hashed off
    `f"look:{observation_id}"` exactly like `perturbed_bearing_range`'s own
    down component -- same draw, so a cue-B-absent result below is
    bit-for-bit what `perturbed_bearing_range` already returns, not a
    second independent estimate that happens to agree.

    **Cue B** is the perceived depression angle: the true depression
    (`atan2(height_above_unit_m, true_distance_m)`) plus a per-look draw
    of its own, hashed off a *different* domain (`f"depression:
    {observation_id}"`) and scaled by `DEPRESSION_SIGMA_DEG` times the
    optic's existing bearing scale (`_SIGHT_BEARING_SIGMA_SCALE_BY_OPTIC`)
    -- the same scale `look_sigma_m`'s cross-range term already uses, so
    the 9K113 narrows this cue the same way it narrows bearing, with no
    new per-optic constant. **This is the no-omniscience fence, made
    testable (E7)**: the perceived depression is drawn independently of
    `RelativeDirection`/`RELATIVE_DIRECTION_SIGMA_DEG` -- nothing here ever
    reads that channel, by construction (it is not even imported into this
    module).

    Cue B is **absent** -- the result is cue A alone, unchanged -- whenever
    the perceived ray does not descend to the unit: `height_above_unit_m`
    is (effectively) zero, or the perceived depression's sign disagrees
    with it (a near-level look, a low hover, noise flipping a shallow look
    level or past it). This is explore-notes Q2's answer: when the
    perceived direction points level or above the horizon, range falls
    back to the size/terrain judgement cue (cue A) alone, exactly as today.

    The two cues are **fused in inverse distance** (measured, not taste --
    see the plan's Monte Carlo comparison), with inverse-variance weights
    taken at the *true* geometry (`PositionUncertainty`'s own "sigmas
    declared at the true range" convention): a cue's weight is
    `(true_distance_m**2 / its own sigma)**2`. The combined `sigma_down_m`
    returned is the ordinary inverse-variance combination of the two
    cues' own sigmas -- the shared `true_distance_m**4` scale cancels out
    of that ratio, so it does not need restating there.

    Finally, one per-object systematic offset is added, hashed off the
    same `f"bias:{object_id}"` domain `systematic_bias_m` already uses
    (its down component), but scaled to the *fused* `sigma_down_m` rather
    than cue A's own -- so a cue-B-absent result's offset is bit-for-bit
    `systematic_bias_m`'s own down offset (same domain, same scale), and a
    fused result's offset shrinks smoothly as cue B's weight grows,
    rather than jumping when the balance crosses some threshold (the plan's
    own concern about a spurious "new contact" during a closing run)."""
    _sigma_cross_m, sigma_a_m = look_sigma_m(true_distance_m, optic)

    _look_cross_m, look_down_m = _deterministic_unit_gaussian_pair(
        f"look:{observation_id}"
    )
    cue_a_range_m = max(_CUE_A_MIN_RANGE_M, true_distance_m + look_down_m * sigma_a_m)
    inverse_a = 1.0 / cue_a_range_m
    weight_a = (true_distance_m**2 / sigma_a_m) ** 2 if sigma_a_m > 0.0 else 0.0

    true_depression_rad = math.atan2(height_above_unit_m, true_distance_m)
    bearing_scale = _SIGHT_BEARING_SIGMA_SCALE_BY_OPTIC.get(optic.name, 1.0)
    sigma_delta_rad = math.radians(DEPRESSION_SIGMA_DEG * bearing_scale)
    z_depression, _unused = _deterministic_unit_gaussian_pair(
        f"depression:{observation_id}"
    )
    perceived_depression_rad = true_depression_rad + z_depression * sigma_delta_rad

    cue_b_present = (
        height_above_unit_m != 0.0
        and perceived_depression_rad != 0.0
        and (perceived_depression_rad > 0.0) == (height_above_unit_m > 0.0)
    )

    if cue_b_present:
        inverse_b = math.tan(perceived_depression_rad) / height_above_unit_m
        slant_sq_m = height_above_unit_m**2 + true_distance_m**2
        sigma_b_m = abs(slant_sq_m / height_above_unit_m) * sigma_delta_rad
        weight_b = (true_distance_m**2 / sigma_b_m) ** 2 if sigma_b_m > 0.0 else 0.0
        fused_inverse = (weight_a * inverse_a + weight_b * inverse_b) / (
            weight_a + weight_b
        )
        sigma_down_m = (1.0 / sigma_a_m**2 + 1.0 / sigma_b_m**2) ** -0.5
    else:
        fused_inverse = inverse_a
        sigma_down_m = sigma_a_m

    range_cap_m = (
        optic.range_cap_m if optic.range_cap_m is not None else (NAKED_EYE_RANGE_CAP_M)
    )
    fused_range_m = (
        min(range_cap_m, 1.0 / fused_inverse) if fused_inverse > 0.0 else (range_cap_m)
    )

    _unused_cross_bias, z_down_bias = _deterministic_unit_gaussian_pair(
        f"bias:{object_id}"
    )
    systematic_offset_m = z_down_bias * SYSTEMATIC_BIAS_FRACTION * sigma_down_m
    final_range_m = max(0.0, fused_range_m + systematic_offset_m)

    return final_range_m, sigma_down_m
