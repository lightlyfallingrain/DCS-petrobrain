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


def naked_eye_sigma_m(true_range_m: float) -> tuple[float, float]:
    """`(sigma_cross_m, sigma_down_m)` for a naked-eye look at
    `true_range_m` -- see module docstring's "The model"."""
    sigma_cross_m = math.radians(BEARING_SIGMA_DEG) * true_range_m
    sigma_down_m = RANGE_FRACTIONAL_SIGMA * true_range_m
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
