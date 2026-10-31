"""The perception-side error model and perturbation -- `plans/
precise-position-belief/plan.md`, restructured by `plans/
relative-distance-grouping/plan.md` (`BL-B106`) Stage 1. Replaces
`naked_eye_source.py`'s reporting-vocabulary quantisation (the deleted
`_quantise_bearing`/`_quantise_range_m`), which snapped every estimate onto
one of a small number of buckets and, worse, snapped range onto the
bucket's *upper bound* -- a systematic long bias of up to a full bucket
width, not a conservative coarsening (plan's "The diagnosis, verified").

**The model, as of `BL-B106`.** A look's down-range (along line-of-sight)
error is no longer one independent-per-look draw plus a never-redrawn
per-object bias. A real observer judges *relative* distance -- which of two
things is further, whether a sighting is the thing seen before -- far
better than he judges the absolute number, via size, depression angle and
terrain cues that are shared by everything seen from about the same place.
The down-range error is now three parts, as a fraction of a look's own
`sigma_down_m = RANGE_FRACTIONAL_SIGMA * true_range_m * optic_scale`:

    e_range = sigma_down_m * ( s * Z_view(bearing, ln R)
                              + f * Z_near(ln R)
                              + a * z_look )
    s = sqrt(1 - f*f - a*a)

`Z_view`/`Z_near` are deterministic, smooth, zero-mean, approximately
unit-variance realisations of a stationary Gaussian random field over
*perceived look geometry* (true bearing, log true range) -- not keyed by
object id, so two different things seen in the same part of the sky at
about the same distance share almost the same draw, which is what makes
"which of these two is further" precise even though "how far" is not.
`Z_view` decorrelates with line-of-sight rotation or range ratio (closing);
`Z_near` decorrelates only with range ratio, over a much smaller ratio, so
two things at clearly different distances get independent `Z_near` terms
while a tight line's members share theirs. `z_look` is redrawn every poll,
shared by every cluster seen in that poll through the same optic -- it is
what a repeat look from the *same* geometry still varies by, bounded to a
small share (`RANGE_LOOK_SHARE`) of the total, since a repeat look mostly
sees the same cues. Each field is keyed by the active optic's own
`Optic.name` (`optic_class`), so a different optic is a genuinely
independent look (`belief.position_belief`'s correlated fusion must not be
able to infer the field's hidden value exactly by combining two optics'
fully-correlated estimates, which would be omniscience by arithmetic) --
see `stable_range_correlation`'s own docstring for the closed form belief
needs.

`stable_range_correlation` is the **only** place `belief/` learns how two
looks' down-range errors correlate -- it reads these model parameters
(length scales, shares), never a field realisation, and the field
realisation functions below (`_field_value`, `_stable_fraction`) are
private to this module.

**Per-optic range scale, as of `BL-B64` Stage 1b (`BL-B55`).** `look_sigma_
m` scales `sigma_down_m`/`sigma_cross_m` by the active `Optic`.
`UNAIDED_OPTIC` is unaffected by construction (both scales 1.0, pinned by
`test_estimation.py`). `BINOCULAR_OPTIC` now gets a declared range scale
too (`BINOCULAR_RANGE_SIGMA_SCALE`, `BL-B106`, Q3) -- better apparent-size
judgement through glass tightens the absolute number as well as the
relative one, between naked eye (1.0, loosest) and the two sight optics
(0.5/0.3, tightest, stadimeter-aided). Cross-range from the sight's own
field of view relative to binocular `BEARING_SIGMA_DEG` is itself
calibrated against (`_SIGHT_BEARING_SIGMA_SCALE_BY_OPTIC`, derived from the
FOV ratio, not an independent judgement call). **Never derived from
`UNAIDED_OPTIC`'s own `fov_half_angle_deg`** -- that field is a
peripheral-vision envelope as of direction §14, not a measure of pointing
precision, so it has no bearing on this scale at all.

**A group is ranged once, with a shared draw, by construction, not by a
special case here** (direction §11). `naked_eye_source._build_observation`
calls `look_sigma_m`/`perturbed_bearing_range` exactly once per cluster
already (one `Observation` per group), so threading the active optic
through that one existing call is what makes a group's position error a
single shared draw -- nothing in this module has to know what a "group" is
for that to hold. The field model above goes further: it also makes two
*different* clusters seen together share most of their down-range error,
without either call knowing about the other.

**Perturb, don't just declare** (plan Decision 1, user-approved): stating
an uncertainty on an exact-truth number would make `belief/percept.py`'s
no-omniscience boundary a comment, not a mechanism -- a heavily-observed
contact would converge exactly onto truth. Every reported bearing/range is
therefore perturbed by a draw from its own declared error ellipse, computed
here and combined by `perturbed_bearing_range`:

- **Cross-range (bearing)** keeps its own per-observation draw
  (`_deterministic_unit_gaussian_pair`, hashed off the observation id) plus
  a never-redrawn per-object systematic bias (`systematic_bias_m`, hashed
  off the object id). Unchanged by `BL-B106` -- bearing's stable structure
  is out of scope (plan's "Bearing ... is out of scope and unchanged").
- **Down-range (range)** is the three-part draw above. **The per-object
  systematic bias on this axis is retired** (`BL-B106`) -- the correlated
  field model replaces it: a group's down-range error is now stable
  because it is drawn from a geometry-keyed field, not because an
  object-keyed bias never changes.

No `belief` import anywhere in this module -- `perception` must not import
`belief` (project invariant)."""

from __future__ import annotations

import functools
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
#: cross-range (bearing) systematic bias is scaled to. This is what keeps a
#: heavily-observed contact's *bearing* from converging on truth (plan's
#: "Precision is not omniscience, made structural") -- `belief.
#: position_belief`'s fused-estimate floor is this same fraction of a
#: single-look sigma, since the bias never averages out across repeated
#: looks. **`BL-B106`: the down-range half of this bias is retired** -- see
#: module docstring -- so this fraction now governs only the cross-range
#: floor; the down-range floor is `stable_down_sigma_m` below.
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

#: Down-range scale for a binocular look, relative to naked eye --
#: `BL-B106` Q3 (user, 2026-10-31: *"With binoculars you see better and so
#: can judge unit apparent size better. That'd give a better range
#: estimate."*). Between naked eye (1.0, unchanged) and the two sight
#: optics below (0.5/0.3, stadiametric-aided) -- a judgement default, not
#: measured, `#needs-flight`. **This makes absolute binocular range
#: tighter than naked eye for the first time** (the module docstring's
#: "Per-optic range scale" paragraph) -- the live asymmetry `BL-B55`'s own
#: roadmap entry once flagged (seeing further while believed no more
#: precisely) is closed by this value, not left open as that entry
#: originally deferred.
BINOCULAR_RANGE_SIGMA_SCALE: Final[float] = tuning.real(
    "perception.estimation.BINOCULAR_RANGE_SIGMA_SCALE",
    0.7,
    lo=0.1,
    hi=1.0,
    status="judgement",
)

#: Down-range scale per optic for `look_sigma_m` below -- `1.0` (no
#: change) for every optic not named here, which as of `BL-B106` is only
#: `UNAIDED_OPTIC` (module docstring's "unaffected by construction").
_RANGE_SIGMA_SCALE_BY_OPTIC: Final[dict[str, float]] = {
    BINOCULAR_OPTIC.name: BINOCULAR_RANGE_SIGMA_SCALE,
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

#: The look-to-look share `a` of the three-part down-range draw, coupled
#: to `RANGE_RELATIVE_SHARE` below (both bounded `lo=0.0, hi=0.6` keeps
#: `f*f + a*a <= 0.72 < 1`, so `s = sqrt(1 - f*f - a*a)` can never go
#: imaginary from any combination of independently-valid overrides of the
#: two -- the X-T26 cross-key trap, closed by the shared bound rather than
#: a runtime assertion): how much a *repeat* look from the same geometry
#: still varies, even though the scene and terrain cues are the same.
#: Raising it makes repeated looks jitter more; lowering it makes them
#: read as nearly identical (the user's own E4: "getting the same cues
#: ... same estimate"). Judgement default, `#needs-flight` -- "only
#: actual flights will tell" (explore-notes.md, answer 3). `BL-B106`
#: Stage 1.
RANGE_LOOK_SHARE: Final[float] = tuning.real(
    "perception.estimation.RANGE_LOOK_SHARE", 0.2, lo=0.0, hi=0.6, status="judgement"
)

#: The relative share `f` of the three-part down-range draw, coupled to
#: `RANGE_LOOK_SHARE` above (see that constant's own docstring for the
#: shared bound that keeps `f*f + a*a < 1`): how much two *different*
#: things seen in the same look, at about the same distance, still differ
#: in their down-range error. This is the knob the ambiguous "2.0 km vs
#: 2.5 km" case (E6) moves on -- raising it widens the merge zone and the
#: two can read as one group; lowering it narrows it. Judgement default,
#: `#needs-flight`. `BL-B106` Stage 1.
RANGE_RELATIVE_SHARE: Final[float] = tuning.real(
    "perception.estimation.RANGE_RELATIVE_SHARE",
    0.2,
    lo=0.0,
    hi=0.6,
    status="judgement",
)

#: `BL-B106` Stage 1 -- how many degrees of line-of-sight rotation it takes
#: for the `Z_view` field's down-range correlation to fall to about `1/e`
#: (holding range fixed): a smaller value means ownship turning past a
#: group updates its range estimate (via `belief.position_belief`'s
#: correlated fusion/gate) sooner; a larger value means the estimate stays
#: "the same look" longer, e.g. through a shallow orbit. Judgement default,
#: `#needs-flight` -- the user's own "a different angle to look from,
#: triangulation by ownship movement" (explore-notes.md, answer 2) is what
#: this constant makes happen.
RANGE_DECORRELATION_BEARING_DEG: Final[float] = tuning.real(
    "perception.estimation.RANGE_DECORRELATION_BEARING_DEG",
    30.0,
    lo=5.0,
    hi=120.0,
    status="judgement",
)

#: `BL-B106` Stage 1 -- the range *ratio* (closing or opening) at which the
#: `Z_view` field's down-range correlation falls to about `1/e` (holding
#: bearing fixed): raising it makes a closing run keep "the same look"'s
#: error longer before it genuinely updates; lowering it means the estimate
#: tightens sooner as ownship closes. `1.5` means the far:near ratio has to
#: grow by half again before the old look's stable error is treated as
#: mostly gone. Judgement default, `#needs-flight`.
RANGE_DECORRELATION_RANGE_RATIO: Final[float] = tuning.real(
    "perception.estimation.RANGE_DECORRELATION_RANGE_RATIO",
    1.5,
    lo=1.1,
    hi=4.0,
    status="judgement",
)

#: The range ratio at which the `Z_near` field's correlation between two
#: *different* things falls to about `1/e` -- deliberately much smaller
#: than the `Z_view` field's own decorrelation range ratio (declared
#: above this one), so two things ~200 m apart along a line at a few km
#: (ratio close to 1.0) share nearly all of their `Z_near` term (one real
#: group, E3) while two groups at a 1.2-1.5 ratio or more do not (E1/E2).
#: This is the second lever the ambiguous case (E6) moves on, alongside
#: this module's own relative-share constant -- raising it widens the
#: ratio at which two things still read as one group. Judgement default,
#: `#needs-flight`. `BL-B106` Stage 1.
RANGE_NEAR_DECORRELATION_RANGE_RATIO: Final[float] = tuning.real(
    "perception.estimation.RANGE_NEAR_DECORRELATION_RANGE_RATIO",
    1.15,
    lo=1.02,
    hi=1.5,
    status="judgement",
)

#: Number of random-Fourier-feature cosines each field realisation sums --
#: an internal approximation-quality knob, not a behaviour-affecting
#: constant (no value in this range changes what Petrovich does, only how
#: closely the field's *realised* correlation tracks `stable_range_
#: correlation`'s closed form) -- so it stays a bare module literal, not a
#: tuning key, per the X-T26 inclusion test. **256, not the plan's
#: suggested 16-32** -- each field is one fixed, never-resampled
#: realisation (keyed only by `field_name`/`optic_class`, not by any
#: per-call randomness), so its *spatial* variance over the actual flight
#: envelope (bearing 0-360, range ~0.5-10 km) is whatever that one
#: realisation happens to have, not the RFF theorem's ensemble-average
#: guarantee. Measured empirically (`test_estimation.py`'s own RMS
#: property test): 16-32 draws left individual optic classes' realised
#: variance anywhere from 0.5 to 1.5 of the target depending on hash luck;
#: 256 keeps every shipped optic class's realised absolute-RMS property
#: within the plan's own declared +/-10% tolerance. Still cheap -- a few
#: hundred cosines per cluster per poll is not a measurable cost against
#: dozens of clusters at 1 Hz.
_FIELD_FOURIER_K: Final[int] = 256


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


def _deterministic_uniform(seed_text: str) -> float:
    """One deterministic draw, uniform on `[0, 1)`, from `seed_text` --
    `_deterministic_unit_gaussian_pair`'s own hash idiom, for the one place
    this module needs a uniform rather than a Gaussian (`_field_value`'s
    random phase)."""
    digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
    u_int = int.from_bytes(digest[:8], "big")
    return u_int / (2.0**64)


@functools.cache
def _field_frequencies(
    field_name: str, optic_class: str, length_scales: tuple[float, ...]
) -> tuple[tuple[tuple[float, ...], float], ...]:
    """The `_FIELD_FOURIER_K` `(w_per_axis, phase)` pairs for one `(field_
    name, optic_class)` field -- derived once per field and cached, not
    re-derived (via `hashlib.sha256`, a real cost at `_FIELD_FOURIER_K =
    256`) on every `_field_value` call. These depend only on `(field_name,
    optic_class, length_scales)`, never on `coords`, so caching them is
    exactly the "same field realisation evaluated at different points"
    property `_field_value`'s own docstring already relies on -- this is
    a performance change, not a behaviour change: `_field_value`'s output
    is bit-identical before and after."""
    frequencies = []
    for k in range(_FIELD_FOURIER_K):
        seed = f"field:{field_name}:{optic_class}:{k}"
        w_per_axis = []
        for axis, length_scale in enumerate(length_scales):
            z_w, _unused = _deterministic_unit_gaussian_pair(f"{seed}:w{axis}")
            w_per_axis.append(z_w * math.sqrt(2.0) / length_scale)
        phase = _deterministic_uniform(f"{seed}:phase") * 2.0 * math.pi
        frequencies.append((tuple(w_per_axis), phase))
    return tuple(frequencies)


def _field_value(
    *,
    field_name: str,
    optic_class: str,
    coords: tuple[float, ...],
    length_scales: tuple[float, ...],
) -> float:
    """A deterministic, stateless realisation at `coords` of a stationary,
    zero-mean, approximately unit-variance Gaussian random field whose
    kernel is `exp(-sum_i ((u_i - u'_i) / length_scales[i]) ** 2)` --
    i.e. along axis `i` alone, correlation falls to `1/e` at a separation
    of `length_scales[i]`, which is `stable_range_correlation`'s own
    closed form for this field (see that function's docstring for the
    derivation this realisation approximates).

    Random-Fourier-feature construction (Bochner's theorem): the kernel's
    Fourier transform is itself Gaussian, so a field built from `_FIELD_
    FOURIER_K` cosines of frequencies drawn `N(0, 2 / length_scales[i]**2)`
    per axis, each with its own uniform random phase, converges (as `K`
    grows) to a realisation of the target kernel. Frequencies and phases
    are derived purely from `(field_name, optic_class, k)` via the hash
    idiom above, cached by `_field_frequencies` -- **not from `coords`** --
    so this is the *same* field realisation evaluated at different points,
    not an independent draw per call; that is what makes two nearby points
    correlated at all.

    `optic_class` is folded into the seed so a different optic gets a
    genuinely independent field (module docstring: belief must not be able
    to infer this field's value exactly from two fully-correlated optics).
    `field_name` is folded in the same way so the down-range field and the
    depression field (`surface_range_estimate`'s cue A/cue B) never share a
    realisation despite sharing this formula."""
    total = 0.0
    for w_per_axis, phase in _field_frequencies(field_name, optic_class, length_scales):
        w_dot_u = sum(w * coord for w, coord in zip(w_per_axis, coords))
        total += math.cos(w_dot_u + phase)
    return total * math.sqrt(2.0 / _FIELD_FOURIER_K)


def stable_share() -> float:
    """`s = sqrt(1 - f*f - a*a)` -- the `Z_view` field's own share of the
    three-part down-range draw (module docstring). A function, not a
    module-level constant, because `RANGE_RELATIVE_SHARE`/`RANGE_LOOK_
    SHARE` are themselves resolved via `tuning.real`, and this value must
    be recomputed from whatever those two resolved to, not frozen before
    either import-time override is known to have landed (both are declared
    above this function, so in practice they are already final by the time
    this is ever called -- but deriving it fresh, rather than caching it as
    a third `Final`, keeps there from being a third place the `f*f + a*a`
    arithmetic could drift from the other two)."""
    return math.sqrt(max(0.0, 1.0 - RANGE_RELATIVE_SHARE**2 - RANGE_LOOK_SHARE**2))


def stable_down_sigma_m(sigma_down_m: float) -> float:
    """The `s`- and `f`-parts of `sigma_down_m` combined -- `sqrt(s*s +
    f*f) * sigma_down_m` -- the stable (geometry-correlated) portion of a
    look's down-range sigma, as opposed to the `a` (look-to-look) portion
    that genuinely redraws. This is what `perception.source.
    PositionUncertainty.sigma_down_stable_m` carries, and what `belief.
    position_belief`'s revised floor binds to at the same geometry (plan
    Stage 2)."""
    return math.sqrt(RANGE_RELATIVE_SHARE**2 + stable_share() ** 2) * sigma_down_m


def stable_range_correlation(
    d_bearing_deg: float, range_ratio: float, same_optic: bool
) -> tuple[float, float]:
    """The closed-form correlation `(rho_view, rho_near)` between two
    looks' down-range stable terms, given the angular separation of their
    lines of sight (`d_bearing_deg`, unsigned) and the ratio of their true
    ranges (`range_ratio >= 1.0`, i.e. `max(R1, R2) / min(R1, R2)`) --
    **the only place `belief/` learns how errors correlate**; it reads
    these model parameters, never a field realisation (module docstring).

    `rho_view` is `Z_view`'s own kernel: `exp(-(d_bearing_deg /
    RANGE_DECORRELATION_BEARING_DEG) ** 2 - (ln(range_ratio) /
    ln(RANGE_DECORRELATION_RANGE_RATIO)) ** 2)` -- falls to `1/e` when
    *either* term alone reaches 1 (holding the other at zero), matching
    `RANGE_DECORRELATION_BEARING_DEG`'s and `RANGE_DECORRELATION_RANGE_
    RATIO`'s own docstrings.

    `rho_near` is `Z_near`'s own kernel, range-ratio only: `exp(-(ln(
    range_ratio) / ln(RANGE_NEAR_DECORRELATION_RANGE_RATIO)) ** 2)`.

    `same_optic is False` makes both `0.0` -- a different optic class is an
    independent field realisation by construction (`_field_value`'s own
    seed includes `optic_class`), so two looks through different optics
    share nothing of their down-range error, whatever their geometry."""
    if not same_optic:
        return 0.0, 0.0
    ratio = max(1.0, range_ratio)
    ln_ratio = math.log(ratio)
    rho_view = math.exp(
        -((d_bearing_deg / RANGE_DECORRELATION_BEARING_DEG) ** 2)
        - (ln_ratio / math.log(RANGE_DECORRELATION_RANGE_RATIO)) ** 2
    )
    rho_near = math.exp(
        -((ln_ratio / math.log(RANGE_NEAR_DECORRELATION_RANGE_RATIO)) ** 2)
    )
    return rho_view, rho_near


def effective_down_correlation(rho_view: float, rho_near: float) -> float:
    """Combine `stable_range_correlation`'s `(rho_view, rho_near)` pair
    into the single correlation coefficient `belief.position_belief.
    correlated_innovation` applies to the product of two looks' own
    `sigma_down_stable_m`: `(s*s*rho_view + f*f*rho_near) / (s*s + f*f)`,
    where `s`/`f` are `stable_share()`/`RANGE_RELATIVE_SHARE` -- the same
    weights the down-range draw itself uses (module docstring), since the
    `z_look` (`a`-weighted) term never correlates across different polls
    by construction and so contributes nothing here.

    This is `1.0` exactly at identical geometry (`rho_view == rho_near ==
    1.0`, matching `Var(stable term) == sigma_down_stable_m ** 2` when
    both looks share one sigma) and `0.0` whenever `stable_range_
    correlation` already returned `(0.0, 0.0)` (a different optic)."""
    s_sq = stable_share() ** 2
    f_sq = RANGE_RELATIVE_SHARE**2
    denom = s_sq + f_sq
    if denom <= 0.0:
        return 0.0
    return (s_sq * rho_view + f_sq * rho_near) / denom


def _stable_fraction(
    *,
    field_domain: str,
    true_bearing_deg: float,
    true_range_m: float,
    optic_class: str,
    poll_key: float,
) -> float:
    """`s * Z_view + f * Z_near + a * z_look`, dimensionless (in units of
    the caller's own sigma) -- the shared three-part structure behind both
    the ordinary down-range draw and `surface_range_estimate`'s cue B
    (module docstring: "Cue B ... takes the same three-part structure with
    its own seed domain") -- `field_domain` is that seed domain (`"range"`
    for the ordinary draw, `"depression"` for cue B), so the two never
    share a field realisation despite sharing this formula.

    `z_look` is redrawn only by `(field_domain, optic_class, poll_key)` --
    not by observation or object id -- so every cluster seen in the same
    poll through the same optic shares the identical look-to-look term
    (module docstring's "shared by every cluster in that poll")."""
    ln_range = math.log(max(true_range_m, 1.0))
    z_view = _field_value(
        field_name=f"{field_domain}:view",
        optic_class=optic_class,
        coords=(true_bearing_deg, ln_range),
        length_scales=(
            RANGE_DECORRELATION_BEARING_DEG,
            math.log(RANGE_DECORRELATION_RANGE_RATIO),
        ),
    )
    z_near = _field_value(
        field_name=f"{field_domain}:near",
        optic_class=optic_class,
        coords=(ln_range,),
        length_scales=(math.log(RANGE_NEAR_DECORRELATION_RANGE_RATIO),),
    )
    z_look, _unused = _deterministic_unit_gaussian_pair(
        f"zlook:{field_domain}:{optic_class}:{poll_key}"
    )
    return (
        stable_share() * z_view
        + RANGE_RELATIVE_SHARE * z_near
        + RANGE_LOOK_SHARE * z_look
    )


def look_sigma_m(true_range_m: float, optic: Optic) -> tuple[float, float]:
    """`(sigma_cross_m, sigma_down_m)` for a look through `optic` at
    `true_range_m` -- see module docstring's "The model" and "Per-optic
    range scale" sections. Renamed from `naked_eye_sigma_m` (`BL-B64` Stage
    1b) -- it was never structurally naked-eye-only, only unconditionally
    so until that entry.

    `UNAIDED_OPTIC` (any `optic.name` not in either per-optic dict below)
    reproduces the pre-`BL-B64` formula exactly -- both scales resolve to
    `1.0` via `dict.get`'s default."""
    bearing_scale = _SIGHT_BEARING_SIGMA_SCALE_BY_OPTIC.get(optic.name, 1.0)
    range_scale = _RANGE_SIGMA_SCALE_BY_OPTIC.get(optic.name, 1.0)
    sigma_cross_m = math.radians(BEARING_SIGMA_DEG * bearing_scale) * true_range_m
    sigma_down_m = RANGE_FRACTIONAL_SIGMA * range_scale * true_range_m
    return sigma_cross_m, sigma_down_m


def systematic_bias_m(object_id: int, sigma_cross_m: float) -> float:
    """The per-object cross-range (bearing) systematic bias, drawn once
    from a hash of `object_id` alone and never re-drawn --
    `SYSTEMATIC_BIAS_FRACTION` of the *single-look* cross sigma. Never
    averages out across repeated looks (unlike `perturb_bearing_range`'s
    per-observation draw), which is the mechanism that keeps a
    heavily-observed contact's *bearing* converging on a wrong,
    confidently-held value rather than truth. `object_id` never leaves
    `perception/`.

    **`BL-B106`: the down-range half of this bias is retired** -- see
    module docstring. The correlated field model (`_stable_fraction`)
    replaces it for that axis; this function now returns a single float,
    not a pair."""
    z_cross, _unused = _deterministic_unit_gaussian_pair(f"bias:{object_id}")
    return z_cross * SYSTEMATIC_BIAS_FRACTION * sigma_cross_m


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
    optic_class: str,
    poll_key: float,
) -> tuple[float, float]:
    """One look's perturbed `(bearing_deg, range_m)` estimate: the true
    geometry plus the bearing axis's per-look noise and never-redrawn
    per-object bias (unchanged by `BL-B106`), plus the range axis's
    correlated three-part draw (`_stable_fraction`, module docstring) --
    see module docstring.

    `optic_class` and `poll_key` key the down-range field/`z_look` draw
    (`_stable_fraction`) -- `optic_class` is the active optic's own
    `Optic.name` (a different optic is an independent look); `poll_key` is
    a value shared by every cluster observed in the same poll (naked-eye's
    `now_sim`), which is what makes `z_look` "shared within that poll"
    (module docstring) rather than per-observation.

    The cross-range offset is turned into a bearing delta at the *true*
    range, not the perturbed one -- using the perturbed range there would
    make the angular offset diverge at short range for no physical reason.
    Range is floored at 0.0 (a look can perturb short of a target that is
    very close, never negative)."""
    look_cross_m, _unused = _deterministic_unit_gaussian_pair(f"look:{observation_id}")
    look_cross_m *= sigma_cross_m
    bias_cross_m = systematic_bias_m(object_id, sigma_cross_m)
    total_cross_m = look_cross_m + bias_cross_m

    down_fraction = _stable_fraction(
        field_domain="range",
        true_bearing_deg=true_bearing_deg,
        true_range_m=true_range_m,
        optic_class=optic_class,
        poll_key=poll_key,
    )
    total_down_m = down_fraction * sigma_down_m

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
    true_distance_m: float,
    height_above_unit_m: float,
    optic: Optic,
    poll_key: float,
) -> tuple[float, float]:
    """A surface unit's own ground-range estimate, fused from two cues --
    `plans/bl-b104-ground-contacts-on-ground/plan.md` Stage 3, restructured
    by `BL-B106` Stage 1. See that plan's "The model in one picture" for
    cue A/cue B's derivation and fusion; this docstring covers only what
    `BL-B106` changed: both cues now draw from the correlated three-part
    structure (`_stable_fraction`), each its own seed domain, rather than
    one independent-per-look draw plus a never-redrawn per-object bias.

    `true_distance_m` is the true **horizontal** ground distance to the
    unit (`D` in the plan's picture) -- the caller already has this as
    the flat-projection "true range" naked-eye clustering already computes
    (`centroid.alt_m` pinned to the observer's own altitude). `height_
    above_unit_m` is the true, **signed** height of the observer above the
    unit (`h`): positive when the observer looks down at it, negative when
    the unit is above the observer (a SAM on a ridge).

    **Cue A** is the ordinary down-range draw (`_stable_fraction` with
    `field_domain="range"`, the same domain `perturbed_bearing_range`'s own
    down component uses) -- so a cue-B-absent result below is bit-for-bit
    what `perturbed_bearing_range` already returns, not a second
    independent estimate that happens to agree.

    **Cue B** is the perceived depression angle: the true depression
    (`atan2(height_above_unit_m, true_distance_m)`) plus the *depression*
    seed domain's own three-part draw (`_stable_fraction` with
    `field_domain="depression"`, module docstring's "Cue B ... its own seed
    domain"), scaled by `DEPRESSION_SIGMA_DEG` times the optic's existing
    bearing scale (`_SIGHT_BEARING_SIGMA_SCALE_BY_OPTIC`) -- the same scale
    `look_sigma_m`'s cross-range term already uses, so the 9K113 narrows
    this cue the same way it narrows bearing, with no new per-optic
    constant. **This is the no-omniscience fence, made testable (E7)**: the
    perceived depression is drawn independently of `RelativeDirection`/
    `RELATIVE_DIRECTION_SIGMA_DEG` -- nothing here ever reads that channel,
    by construction (it is not even imported into this module).

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

    **`BL-B106`: no final per-object offset is added any more** -- cue A's
    own down-range draw already carries the correlated structure; a second,
    object-keyed bias layered on top of that (as pre-`BL-B106` code did)
    would reintroduce exactly the independent-per-object term the plan's
    model replaces."""
    _sigma_cross_m, sigma_a_m = look_sigma_m(true_distance_m, optic)

    down_fraction_a = _stable_fraction(
        field_domain="range",
        true_bearing_deg=0.0,
        true_range_m=true_distance_m,
        optic_class=optic.name,
        poll_key=poll_key,
    )
    cue_a_range_m = max(
        _CUE_A_MIN_RANGE_M, true_distance_m + down_fraction_a * sigma_a_m
    )
    inverse_a = 1.0 / cue_a_range_m
    weight_a = (true_distance_m**2 / sigma_a_m) ** 2 if sigma_a_m > 0.0 else 0.0

    true_depression_rad = math.atan2(height_above_unit_m, true_distance_m)
    bearing_scale = _SIGHT_BEARING_SIGMA_SCALE_BY_OPTIC.get(optic.name, 1.0)
    sigma_delta_rad = math.radians(DEPRESSION_SIGMA_DEG * bearing_scale)
    depression_fraction = _stable_fraction(
        field_domain="depression",
        true_bearing_deg=0.0,
        true_range_m=true_distance_m,
        optic_class=optic.name,
        poll_key=poll_key,
    )
    perceived_depression_rad = (
        true_depression_rad + depression_fraction * sigma_delta_rad
    )

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
    final_range_m = max(0.0, fused_range_m)

    return final_range_m, sigma_down_m
