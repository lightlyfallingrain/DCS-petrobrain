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
BEARING_SIGMA_DEG: Final[float] = 3.0

#: Fraction of a look's own single-look sigma the never-redrawn per-object
#: systematic bias is scaled to. This is what keeps a heavily-observed
#: contact from converging on truth (plan's "Precision is not omniscience,
#: made structural") -- `belief.position_belief`'s fused-estimate floor is
#: this same fraction of a single-look sigma, since the bias never
#: averages out across repeated looks.
SYSTEMATIC_BIAS_FRACTION: Final[float] = 0.4


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
