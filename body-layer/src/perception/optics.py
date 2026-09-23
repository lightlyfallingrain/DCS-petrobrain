"""Named optics and per-optic field-of-view test --
`plans/detection-cones-slice1/plan.md`, slice 1 of the "detection cones"
milestone `body-layer/ROADMAP.md` names, extended to per-tier multipliers
by slice 2A (`plans/detection-cones-slice2/plan.md`, `body-layer/research/
2026-09-21-slice2-model-decisions.md` decision 1).

**Per-tier, not one magnification (slice 2A).** `Optic` no longer carries a
single `magnification` -- ED's own `recognition_distance_ratio_threshold`
(0.25 naked-eye vs. 0.5 optics) and the 2026-09-21 sortie both show
presence scaling sub-linearly with magnification while class/type scale
supra-linearly, so a single number applied uniformly to all three
recognition tiers was never right. `presence_range_mult`/
`class_range_mult`/`type_range_mult` are the three independently-measured
multipliers instead, all derived from the BTR-60 alone (the decisions
doc's "why they come from the BTR-60 alone" section) -- `UNAIDED_OPTIC` is
1.0/1.0/1.0 by construction (the baseline observer, distinctiveness and
per-tier multipliers all inert), `BINOCULAR_OPTIC` is 2.42/3.50/3.00.

**The 9K113 sight's multipliers (wide 3.55/7.00/6.50, narrow
5.81/13.75/15.00) are deliberately NOT added here as named `Optic`
instances.** The sight itself stays out of scope this slice (see the
scope-cut paragraph below, unchanged) -- adding it as a selectable table
entry would let a concrete `PerceptionSource` select it, which is exactly
what `plans/detection-cones-slice2/plan.md`'s "Explicitly out of scope"
section defers to its own backlog item. Its values live in the decisions
doc and in `perception.clustering`'s own docstring (the floor-fix
derivation needs the narrow sight's 5.81 to state why the floor had to
become optic-parametric), not as an importable constant here.

**Scope cut (user, 2026-09-20): the 9K113 sight is deferred entirely.**
This module names only `UNAIDED_OPTIC` and `BINOCULAR_OPTIC`. The 9K113's
own magnification/field-of-view/field-of-regard figures, sourced and
unverified alike, stay recorded in `body-layer/research/
2026-09-20-9k113-sight-optics-from-manual.md` until the sight itself gets
its own slice. `Optic` therefore carries no field-of-regard fields (how
far an optic can be *pointed*, as opposed to what it shows once pointed):
with no sighted optic in this table, every entry's regard would be `None`
and unexercised by any test, so those fields were cut along with the
9K113 entries that were their only reason to exist. A future 9K113 slice
adds them back, sourced fields intact in the research note above.

**`Optic.boresight_azimuth_deg` is deleted (slice 2B, `plans/
detection-cones-slice2/plan.md`).** `within_optic_fov` now takes the
boresight as a parameter instead of reading it off the optic -- an optic is
pointed by the head, not bolted to the airframe, and slice 2B is what makes
the head's own direction (`perception.gaze.Gaze.center_azimuth_deg`) a real
runtime value. Every existing call passed `boresight_azimuth_deg=0.0`
(dead ahead, no slew model), so `visibility.check_visibility` passes `0.0`
whenever no gaze is active, reproducing the old pinned behaviour exactly.

**`Optic.peripheral: bool` (slice 2B).** `UNAIDED_OPTIC` is `True`,
`BINOCULAR_OPTIC` is `False` -- the naked eye keeps its wide,
change-detecting peripheral channel; raised binoculars trade it away
entirely, not just field of view. This is the one field that makes the
two-channel eyesight model (`plans/detection-cones-slice2/plan.md` hard
part 2a) operative today with no attention-capture channel wired: a
candidate in `perception.gaze.gaze_for`'s `stimulus_ids` bypasses the gaze
gate only when the active optic's `peripheral` is `True` -- see that
function's own docstring for the invariant this does *not* relax (a bypass
never grants vision the cockpit mask/range/LOS gates would otherwise deny).

**Naked eye is now the default, not binoculars (final scope change,
2026-09-20, same session).** `visibility.check_visibility`'s `optic`
parameter now resolves to `UNAIDED_OPTIC`, not `BINOCULAR_OPTIC` -- see
that function's own docstring for the mechanism. The reason belongs here,
next to the two optics it distinguishes: modelling Petrovich as
permanently glassed-up was the single biggest source of over-detection in
this channel. He was getting binocular magnification across the *whole*
cockpit-mask envelope, with no field-of-view cost at all -- every
candidate the mask admitted got treated as if he had raised binoculars to
look at it specifically. Real observation is naked-eye by default;
binoculars are a deliberate, narrower, raised-to-the-eyes act, which is
exactly what `BINOCULAR_OPTIC.fov_half_angle_deg` now being a real number
(not `None`) encodes -- see that optic's own docstring below.

**`BINOCULAR_RANGE_MULTIPLIER` is retired, not carried forward (slice
2A).** It lived in `visibility.py` and was imported here as
`BINOCULAR_OPTIC.magnification`; the single-number-per-optic premise it
encoded is exactly what per-tier multipliers replace. Its own round-trip
history (4.0 -> 8.0 -> 4.0, `visibility.py`'s docstring had the full
chronology) is no longer relevant to the current model -- the binocular
optic's numbers now come from the BTR-60 measurement (2.42/3.50/3.00),
not from that constant. Deleting it also dissolves the real circular
import this module and `visibility.py` used to have (each needed a name
from the other): `optics.py` no longer imports anything from
`visibility.py`, so `visibility.py` can import `Optic`/`UNAIDED_OPTIC`/
`within_optic_fov` as an ordinary top-level import instead of the
`TYPE_CHECKING`/function-local workaround its own docstring used to
explain.

Pure, no I/O, no DCS/world-model dependency -- mirrors `cockpit_mask.py`'s
own posture.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class Optic:
    """One named optic: how much farther it lets each recognition tier be
    achieved, and what it shows once pointed (field of view).

    `presence_range_mult`/`class_range_mult`/`type_range_mult` replace the
    old single `magnification` (slice 2A) -- the multiplier `visibility.
    py`'s range-threshold formula and `_achieved_tier` apply to the
    `lowres`/`medres`/`hires` threshold respectively, stated honestly per
    tier rather than as one number assumed to apply uniformly. All three
    are BTR-60-derived (module docstring); `UNAIDED_OPTIC` is 1.0 on all
    three by construction.

    `fov_half_angle_deg` is `None` for an optic with no FOV restriction
    (the naked eye -- the cockpit occlusion mask is its only envelope);
    `BINOCULAR_OPTIC` below is the first optic in this table to carry a
    real value.

    `peripheral` (slice 2B) is `True` iff this optic retains a wide,
    change-detecting peripheral channel alongside its focused view --
    module docstring."""

    name: str
    presence_range_mult: float
    class_range_mult: float
    type_range_mult: float
    fov_half_angle_deg: float | None
    #: Defaults `True` so every existing synthetic test `Optic(...)` still
    #: constructs unchanged -- only `BINOCULAR_OPTIC` sets this `False`.
    peripheral: bool = True


#: 1.0 on every tier, no FOV restriction -- the cockpit mask is the naked
#: eye's only envelope. **The default `check_visibility` optic as of
#: 2026-09-20** (was `BINOCULAR_OPTIC` -- see module docstring's "Naked eye
#: is now the default" note for why). The baseline observer every other
#: optic's multipliers are measured against.
UNAIDED_OPTIC: Final[Optic] = Optic(
    name="unaided",
    presence_range_mult=1.0,
    class_range_mult=1.0,
    type_range_mult=1.0,
    fov_half_angle_deg=None,
    peripheral=True,
)

#: **No longer the default -- a deliberate, narrower, raised-to-the-eyes
#: act, as of 2026-09-20** (see module docstring). A Б-6 6x30 -- Soviet
#: standard compact issue, true field of view ~8.5 deg.
#:
#: `presence_range_mult=2.42`/`class_range_mult=3.50`/`type_range_mult=
#: 3.00` (slice 2A, `body-layer/research/2026-09-21-slice2-model-
#: decisions.md` decision 1) -- BTR-60-derived, per-tier, replacing the
#: old flat `magnification=4.0` (`BINOCULAR_RANGE_MULTIPLIER`, retired,
#: see module docstring). Presence buys proportionally less than the old
#: flat figure implied (2.42 vs. 4.0) while class buys almost as much
#: (3.50) and type a little less again (3.00) -- ED's own
#: `recognition_distance_ratio_threshold` (0.25 naked vs. 0.5 optics) and
#: the sortie both point the same direction: glass buys recognition more
#: than it buys detection.
#:
#: `fov_half_angle_deg=4.25` (half the ~8.5 deg true field) -- **set to a
#: real value, not `None`, for the first time.** Safe precisely because
#: binoculars are no longer the default: no concrete `PerceptionSource`
#: calls `check_visibility` with this optic yet (plan Decision 4), so the
#: gate cannot misfire in the live path today, and `within_optic_fov`
#: finally has a real number to enforce once mode selection wires this
#: optic in (slice 2B). Binoculars magnifying with no field-of-view cost at
#: all was the free-lunch half of the over-detection problem the 2026-09-20
#: change fixed -- magnification without a narrower cone was exactly
#: backwards.
BINOCULAR_OPTIC: Final[Optic] = Optic(
    name="binocular",
    presence_range_mult=2.42,
    class_range_mult=3.50,
    type_range_mult=3.00,
    fov_half_angle_deg=4.25,
    peripheral=False,
)


def within_optic_fov(
    optic: Optic,
    boresight_azimuth_deg: float,
    azimuth_deg: float,
    elevation_deg: float,
    boresight_elevation_deg: float = 0.0,
) -> bool:
    """True if `(azimuth_deg, elevation_deg)` -- a body-relative direction,
    same convention as `perception.geometry.BodyRelativeDirection` -- falls
    inside `optic`'s field of view, centred on `boresight_azimuth_deg`
    (module docstring's "an optic is pointed by the head" note -- the
    caller supplies where the head/eyes currently point, typically
    `perception.gaze.Gaze.center_azimuth_deg`, or `0.0` when no gaze is
    active).

    `optic.fov_half_angle_deg is None` means "no restriction," always
    `True` (`UNAIDED_OPTIC`). Otherwise compares the true angular
    separation between `(azimuth_deg, elevation_deg)` and
    `(boresight_azimuth_deg, 0.0)` against the half-angle -- small-angle-
    safe great-circle-style separation via the standard spherical law of
    cosines, not a flat azimuth/elevation box (an optic's circular eyepiece
    does not admit a target only because it clears an azimuth check and an
    elevation check independently).

    **`boresight_elevation_deg` exists because a level boresight makes a
    narrow optic useless at close range** (`plans/binocular-optic/plan.md`
    Stage 2). It defaulted to level when the gate was written, which was
    harmless while nothing passed a real optic: a ground unit 1 km away
    from 120 m AGL sits ~6.9 degrees below the horizon, outside
    `BINOCULAR_OPTIC`'s own 4.25-degree half-angle -- so binoculars would
    have been unable to look at precisely the contacts worth looking at.
    You point binoculars *at* a thing, including downwards; the default
    stays level so every existing caller is unchanged."""
    if optic.fov_half_angle_deg is None:
        return True

    az_delta_rad = math.radians(azimuth_deg - boresight_azimuth_deg)
    el_rad = math.radians(elevation_deg)
    boresight_el_rad = math.radians(boresight_elevation_deg)

    cos_separation = math.sin(el_rad) * math.sin(boresight_el_rad) + math.cos(
        el_rad
    ) * math.cos(boresight_el_rad) * math.cos(az_delta_rad)
    # Guard against floating-point drift pushing a near-1.0 cosine just
    # outside acos's domain.
    cos_separation = max(-1.0, min(1.0, cos_separation))
    separation_deg = math.degrees(math.acos(cos_separation))

    # A tiny epsilon absorbs floating-point round-trip error through
    # sin/cos/acos -- without it, a separation constructed to sit exactly
    # on the half-angle boundary can land a few ULPs over and be rejected,
    # which would make "exactly at the boundary" an untestable case.
    return separation_deg <= optic.fov_half_angle_deg + 1e-9
