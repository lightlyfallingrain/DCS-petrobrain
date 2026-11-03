"""`BL-B110` Stage 0 -- measure the expected-area-check "trigger", then fix
its definition (no behaviour change). `plans/expected-area-check/plan.md`
Stage 0: "turn the scratch probe into `tests/test_expected_area_trigger.py`,
an ensemble over the salt seam with BL-B108's `_observation` shape."

**What the trigger is.** Stage 2 (not built by this entry -- see the plan's
"ships with Stage 1's merge" split) re-evaluates `belief.association_
over_time.passes_gate` *as if the remembered contact A had been in this
very look*, via a new `as_if_optic_class` keyword on that function. This
file's `_as_if_gate` is a **test-only** stand-in for that not-yet-built
keyword -- it duplicates `passes_gate`'s own body (the only way to measure
a hypothesis that production code does not yet accept a parameter for)
rather than modifying `passes_gate` itself, so this entry stays "no
behaviour change" in shipped code. Stage 2's own implementer should lift
this function's body into the real keyword rather than re-deriving it.

**Two variants were measured, not one.** The plan's own candidate --
"evaluating the hypothesis sigma at the tighter of the two optics" --
reads as replacing *both* the hypothesis hat sigma magnitude and the
correlation field-class with the tighter optic's own values
(`_as_if_gate`'s `as_if_optic_class` drives `look_sigma_m` directly).
**Measured finding: that variant also inflates the same-group false-
trigger rate past the plan's own ~10% gate** (27-48% at `n=200`, same
group, binocular-anchor-then-naked-eye, `gap_s=6.0`) -- the hypothesis
sigma it substitutes is tighter than the look's own *real* declared
noise, so a genuine same-position reacquisition fails the stricter test
purely from the real look's own ordinary measurement error. **Variant 2
(adopted below): only the *correlation field-class* passed to
`correlated_innovation` is overridden to the tighter optic; the
hypothesis sigma magnitude stays the look's own real declared value,
scaled to the hypothesis range exactly as the honest gate already
computes it.** This keeps the "different groups" catch rate for the
well-caught direction (anchor tighter than the new look, e.g.
binocular-then-unaided) just as high, while cutting the same-group,
short-gap (6 s) false-trigger rate from 27-48% down to 3-7% -- inside the
gate. **Both variants measured with the project's own ensemble harness
(`perception.estimation._FIELD_REALISATION_SALT`), `n=150-200` trials/
cell, this committed code.**

**Stage 0's own gate, both findings recorded honestly, per the plan's own
instruction ("if the false-trigger rate exceeds ~10% in any cell, stop
and bring it to the user"):**

1. **The far-unaided -> near-binocular residual stays high (69-74%,
   `n=100-150`) and neither variant touches it** -- confirms the plan's
   own Risks entry ("The far-unaided -> near-binocular residual (up to
   26%) survives Stage 2... Only a tighter trigger (Stage 0) or anchors
   (Stage 2b) reach it"), at this harness's own (larger) measured scale.
   The mechanism: when the anchor itself was founded through the
   *looser* optic (unaided), the anchor's own wide covariance dominates
   the gate's sum regardless of how tight the new look's hypothesis is
   made -- tightening the *look's* side barely moves a sum the anchor's
   own looseness already dominates. **This is not fixed here**: it is
   exactly the gap `[[BL-B111]]`'s point line-of-sight check or Stage
   2b's anchors would need to close.
2. **The long-gap, stationary (installation-component, zero growth),
   binocular-anchor-then-unaided same-group case exceeds the ~10% gate**:
   7-15% at a 120 s gap, **25-27% at a 600 s gap** (`n=150`, Variant 2,
   both measured ranges). This is `test_false_trigger_rate_for_long_gap_
   stationary_same_group_exceeds_the_gate` below -- **a genuine Stage 0
   STOP finding, reported rather than silently engineered around**
   (`plan.md`'s own instruction). Stage 2 is not built by this entry
   regardless (BL-B110 Stages 0a/0/1 only), so nothing ships against this
   gap; it is recorded here and in `plan.md`'s Stage 0 section for
   whoever builds Stage 2 to resolve first. The short-gap (6 s) and
   moving-class (armour, 8 m/s growth, any gap) same-group cells all stay
   comfortably inside the 10% gate -- see the fenced tests below."""

from __future__ import annotations

from typing import Final

import pytest

import perception.estimation as estimation_module
from belief.association_over_time import (
    GATE_SIGMA_THRESHOLD,
    _contact_covariance,
    class_compatibility,
    implied_position,
    percept_position_uncertainty,
)
from belief.contacts import Contact, ContactStore
from belief.percept import Percept, percept_of
from belief.position_belief import correlated_innovation, covariance_from_uncertainty
from perception.estimation import (
    perturbed_bearing_range,
    range_sigma_scale_for_optic,
    stable_down_sigma_m,
)
from perception.geometry import GeoPosition, bearing_deg, horizontal_range_m
from perception.optics import BINOCULAR_OPTIC, UNAIDED_OPTIC, Optic
from perception.source import (
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
    Observation,
    OwnshipState,
    PositionUncertainty,
)

_CLASSIFICATION_LEVEL = 2

#: Armour -- the default row `test_plausible_speed_mps_default_is_eight_
#: not_the_old_flat_twenty` pins (8.0 m/s), a moving class. `s-125` is a
#: real `_KEYWORD_PROFILES` match with `installation_component=True`
#: (`perception.object_model`), a zero-growth class -- used for the
#: long-gap "stationary" cells, matching the plan's own "stationary, then
#: moving at `plausible_speed_mps`" long-gap grid.
_MOVING_CLASSIFICATION_RAW = "OP_ARMORED"
_STATIONARY_CLASSIFICATION_RAW = "s-125"


def _ownship(t_sim: float, alt_m: float = 500.0) -> OwnshipState:
    return OwnshipState(t_sim=t_sim, x=0.0, z=0.0, alt_m=alt_m, heading_true_deg=0.0)


def _observation(
    *,
    observation_id: str,
    t_sim: float,
    ownship: OwnshipState,
    group_z: float,
    bias_object_id: int,
    optic: Optic,
    classification_raw: str,
) -> Observation:
    """`test_relative_distance_sweep._observation`'s own shape, duplicated
    rather than imported (no test file in this project imports another's
    private helpers) -- trimmed to the air-target path only, since none of
    this file's cells need the ground-unit (`surface`) branch."""
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    centroid = GeoPosition(x=0.0, z=group_z, alt_m=ownship.alt_m)
    true_bearing_deg = bearing_deg(observer, centroid)
    true_range_m = horizontal_range_m(observer, centroid)
    sigma_cross_m, sigma_down_m = estimation_module.look_sigma_m(true_range_m, optic)
    estimated_bearing_deg, estimated_range_m = perturbed_bearing_range(
        observation_id=observation_id,
        object_id=bias_object_id,
        true_bearing_deg=true_bearing_deg,
        true_range_m=true_range_m,
        sigma_cross_m=sigma_cross_m,
        sigma_down_m=sigma_down_m,
        optic_class=optic.name,
        poll_key=t_sim,
    )
    return Observation(
        id=observation_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=0.0,
        source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
        classification_raw=classification_raw,
        bearing_deg=estimated_bearing_deg,
        range_m=estimated_range_m,
        ownship_at_observation=ownship,
        derived_world_position=None,
        provenance="test",
        classification_level=_CLASSIFICATION_LEVEL,
        continues_observation_id=None,
        surface_alt_m=None,
        position_uncertainty=PositionUncertainty(
            sigma_cross_m=sigma_cross_m,
            sigma_down_m=sigma_down_m,
            sigma_down_stable_m=stable_down_sigma_m(sigma_down_m),
            optic_class=optic.name,
        ),
    )


def _fresh_realisation(salt: str) -> None:
    """`test_relative_distance_sweep._fresh_realisation`'s own seam, same
    reason (dozens of calls per test; a tight-loop `monkeypatch` would be
    needless overhead)."""
    estimation_module._FIELD_REALISATION_SALT = salt
    estimation_module._field_frequencies.cache_clear()


@pytest.fixture(autouse=True)
def _restore_field_salt() -> None:
    yield
    estimation_module._FIELD_REALISATION_SALT = ""
    estimation_module._field_frequencies.cache_clear()


def _tighter_optic_name(a: str, b: str) -> str:
    """Whichever of two optic-class names has the smaller `range_sigma_
    scale_for_optic` -- "tighter" in the plan's own words."""
    return a if range_sigma_scale_for_optic(a) <= range_sigma_scale_for_optic(b) else b


def _as_if_gate(
    percept: Percept, contact: Contact, now_sim: float, as_if_optic_class: str
) -> bool:
    """Test-only stand-in for Stage 2's not-yet-built `passes_gate(...,
    as_if_optic_class=...)` keyword -- see module docstring. **Variant 2**:
    only `correlation_optic_class` is overridden; `hypothesis_uncertainty`
    is otherwise `passes_gate`'s own unchanged formula (the percept's own
    real declared sigma, scaled to the hypothesis range)."""
    if class_compatibility(percept.classification_raw, contact.last_class_raw) == (
        "incompatible"
    ):
        return False
    percept_position = implied_position(percept)
    dx = percept_position.x - contact.last_position.x
    dz = percept_position.z - contact.last_position.z
    elapsed_s = max(0.0, now_sim - contact.last_seen_sim)
    percept_uncertainty = percept_position_uncertainty(percept)
    observer = GeoPosition(
        x=percept.ownship_at_observation.x,
        z=percept.ownship_at_observation.z,
        alt_m=percept.ownship_at_observation.alt_m,
    )
    hypothesis_bearing_deg = bearing_deg(observer, contact.last_position)
    hypothesis_range_m = horizontal_range_m(observer, contact.last_position)
    hypothesis_scale = (
        hypothesis_range_m / percept.range_m if percept.range_m > 0.0 else 1.0
    )
    hypothesis_uncertainty = PositionUncertainty(
        sigma_cross_m=percept_uncertainty.sigma_cross_m * hypothesis_scale,
        sigma_down_m=percept_uncertainty.sigma_down_m * hypothesis_scale,
        sigma_down_stable_m=percept_uncertainty.sigma_down_stable_m * hypothesis_scale,
        optic_class=percept_uncertainty.optic_class,
    )
    look_covariance = covariance_from_uncertainty(
        hypothesis_uncertainty, percept.bearing_deg
    )
    s, _c, _kappa_view = correlated_innovation(
        contact.position,
        _contact_covariance(contact, elapsed_s),
        look_covariance,
        correlation_bearing_deg=hypothesis_bearing_deg,
        correlation_range_m=hypothesis_range_m,
        correlation_optic_class=as_if_optic_class,
        correlation_sigma_down_stable_m=hypothesis_uncertainty.sigma_down_stable_m,
    )
    return s.mahalanobis_squared(dx, dz) <= GATE_SIGMA_THRESHOLD**2


def _rates(
    *,
    first_km: float,
    second_km: float,
    first_optic: Optic,
    second_optic: Optic,
    gap_s: float,
    classification_raw: str,
    n: int,
    salt_prefix: str,
) -> tuple[float, float, float]:
    """`(honest_fold_rate, trigger_catches_rate, residual_fold_rate)` over
    `n` independent field realisations -- founds a contact `first_km` away
    through `first_optic`, then (`gap_s` later) observes a second percept
    `second_km` away through `second_optic`. `first_km == second_km` is
    the "same group" case (a genuine reacquisition); `first_km !=
    second_km` is "different groups" (the memory-only fold defect this
    entry exists for).

    `trigger_catches_rate` is measured as `P(honest fold AND as-if gate
    fails)` -- the trigger only ever matters on a percept the honest gate
    would otherwise have resolved onto this contact (Stage 2's own first
    trigger condition, "the percept resolves through the gate onto A").
    `residual_fold_rate = honest_fold_rate - trigger_catches_rate =
    P(honest fold AND as-if gate also passes)`: for "different groups"
    this is the harm (a wrongful fold that survives the trigger); for
    "same group" it is the desired outcome (a correct fold the trigger
    leaves alone), and `trigger_catches_rate` is the harm (a false split)."""
    honest_count = 0
    catch_count = 0
    for trial in range(n):
        _fresh_realisation(f"{salt_prefix}-{trial}")
        store = ContactStore()
        first = _observation(
            observation_id="first",
            t_sim=0.0,
            ownship=_ownship(0.0),
            group_z=-first_km * 1000.0,
            bias_object_id=1,
            optic=first_optic,
            classification_raw=classification_raw,
        )
        store.ingest([first], 0.0)
        store.tick(0.0)
        assert len(store.contacts) == 1
        a = store.contacts[0]

        second = _observation(
            observation_id="second",
            t_sim=gap_s,
            ownship=_ownship(gap_s),
            group_z=-second_km * 1000.0,
            bias_object_id=2,
            optic=second_optic,
            classification_raw=classification_raw,
        )
        percept_b = percept_of(second)
        assert a.position.anchor is not None
        as_if_optic = _tighter_optic_name(
            second_optic.name, a.position.anchor.optic_class
        )
        as_if_passes = _as_if_gate(percept_b, a, gap_s, as_if_optic)

        store.ingest([second], gap_s)
        store.tick(gap_s)
        honest_fold = len(store.contacts) == 1
        if honest_fold:
            honest_count += 1
            if not as_if_passes:
                catch_count += 1
    honest_rate = honest_count / n
    catch_rate = catch_count / n
    return honest_rate, catch_rate, honest_rate - catch_rate


# --- Different groups: the memory-only fold defect itself -----------------

#: Measured (this committed code, `n=150`): far-binocular-then-near-unaided
#: catches 79-85% of the honest fold, leaving a residual of 1-5% -- the
#: plan's own primary worked case ("far group glassed... near group then
#: seen by eye") is essentially resolved by the trigger.
_FAR_BINOCULAR_NEAR_UNAIDED_RESIDUAL_FENCE: Final = 0.10


@pytest.mark.parametrize("far_km,near_km", ((4.5, 3.0), (5.0, 3.5)))
def test_residual_fold_rate_for_far_binocular_near_unaided_is_small(
    far_km: float, near_km: float
) -> None:
    """The plan's primary worked case: a far group glassed through
    binoculars, held in memory, then a genuinely different near group seen
    seconds later by naked eye. Measured residual 1-5% (`n=150`); fenced
    generously at 10%."""
    _honest, _catch, residual = _rates(
        first_km=far_km,
        second_km=near_km,
        first_optic=BINOCULAR_OPTIC,
        second_optic=UNAIDED_OPTIC,
        gap_s=6.0,
        classification_raw=_MOVING_CLASSIFICATION_RAW,
        n=150,
        salt_prefix=f"diff-far_b_near_u-{far_km}-{near_km}",
    )
    assert residual <= _FAR_BINOCULAR_NEAR_UNAIDED_RESIDUAL_FENCE, (
        f"far={far_km} near={near_km}: residual fold {residual:.2%} exceeds "
        f"the {_FAR_BINOCULAR_NEAR_UNAIDED_RESIDUAL_FENCE:.0%} fence -- the "
        "trigger's catch of this direction has weakened"
    )


@pytest.mark.parametrize("far_km,near_km", ((4.5, 3.0), (5.0, 3.5)))
def test_residual_fold_rate_for_far_unaided_near_binocular_stays_high(
    far_km: float, near_km: float
) -> None:
    """The plan's own acknowledged unresolved gap (Risks: "the far-unaided
    -> near-binocular residual... survives Stage 2... only a tighter
    trigger or anchors reach it"). When the anchor is founded through the
    *looser* optic, its own wide covariance dominates the gate's sum
    regardless of how tight the new look's hypothesis is made, so neither
    measured variant of the trigger catches this direction. Measured
    residual 68-74% (`n=100`) -- a characterisation, not a guarantee: this
    pins that the gap is real and this large, so a future change that
    silently closes it (worth knowing about) or widens it further (worth
    catching) both show up here."""
    _honest, _catch, residual = _rates(
        first_km=far_km,
        second_km=near_km,
        first_optic=UNAIDED_OPTIC,
        second_optic=BINOCULAR_OPTIC,
        gap_s=6.0,
        classification_raw=_MOVING_CLASSIFICATION_RAW,
        n=100,
        salt_prefix=f"diff-far_u_near_b-{far_km}-{near_km}",
    )
    assert residual >= 0.50, (
        f"far={far_km} near={near_km}: residual fold {residual:.2%} dropped "
        "below 50% -- the far-unaided -> near-binocular gap may have "
        "closed; if a real model change did this deliberately, update this "
        "characterisation rather than loosening it to make a flake pass"
    )


# --- Same group: the trigger must not falsely split a real reacquisition --


@pytest.mark.parametrize("range_km", (2.0, 3.0, 4.5))
@pytest.mark.parametrize(
    "first_optic,second_optic",
    ((BINOCULAR_OPTIC, UNAIDED_OPTIC), (UNAIDED_OPTIC, BINOCULAR_OPTIC)),
)
def test_false_trigger_rate_for_short_gap_same_group_is_within_the_gate(
    range_km: float, first_optic: Optic, second_optic: Optic
) -> None:
    """A genuinely same, moving (armour) group re-seen through a different
    optic 6s later must not be falsely split by the trigger more than the
    plan's own ~10% gate ("the duplicate rate the pilot would hear").
    Measured (`n=150`): binocular-then-unaided 3-7%, unaided-then-binocular
    0% -- both comfortably inside the gate."""
    _honest, catch, _residual = _rates(
        first_km=range_km,
        second_km=range_km,
        first_optic=first_optic,
        second_optic=second_optic,
        gap_s=6.0,
        classification_raw=_MOVING_CLASSIFICATION_RAW,
        n=150,
        salt_prefix=f"same-short-{range_km}-{first_optic.name}-{second_optic.name}",
    )
    assert catch <= 0.10, (
        f"range={range_km} {first_optic.name}->{second_optic.name}: false "
        f"trigger rate {catch:.2%} exceeds the plan's own ~10% gate -- "
        "stop and report per Stage 0's own instruction rather than "
        "loosening this fence"
    )


def test_false_trigger_rate_for_long_gap_stationary_same_group_exceeds_the_gate() -> (
    None
):
    """**Stage 0's own STOP finding** (module docstring, point 2): a
    genuinely stationary (installation-component, zero growth) group,
    founded through binoculars and re-seen by naked eye after a long gap,
    is falsely split by the trigger well past the plan's own ~10% gate --
    measured (`n=150`) 25-27% at a 600 s gap. This is recorded, not
    silently engineered around, per the plan's own instruction. Stage 2
    (the real trigger) is not built by this entry, so nothing ships
    against this gap yet; whoever builds Stage 2 must resolve it first.
    Asserted as `>= 0.15` (comfortably below the measured 25-27%) so this
    stays a documented, monitored defect rather than something a future
    change could silently regress past without anyone noticing it had
    improved -- if a future change brings this under the gate, that is
    good news, and this assertion (and its docstring, and `plan.md`'s
    Stage 0 section) should be updated to say so rather than left stale."""
    rates = {}
    for range_km in (2.0, 4.5):
        _honest, catch, _residual = _rates(
            first_km=range_km,
            second_km=range_km,
            first_optic=BINOCULAR_OPTIC,
            second_optic=UNAIDED_OPTIC,
            gap_s=600.0,
            classification_raw=_STATIONARY_CLASSIFICATION_RAW,
            n=150,
            salt_prefix=f"same-long-stationary-{range_km}",
        )
        rates[range_km] = catch
    for range_km, catch in rates.items():
        assert catch >= 0.15, (
            f"range={range_km}: false trigger rate {catch:.2%} dropped "
            "below 15% -- the long-gap stationary gate violation this test "
            "pins may have closed; if so, update plan.md's Stage 0 section "
            "and this docstring rather than leaving them stale"
        )
