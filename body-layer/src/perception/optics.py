"""Named optics and per-optic field-of-view test --
`plans/detection-cones-slice1/plan.md`, slice 1 of the "detection cones"
milestone `body-layer/ROADMAP.md` names.

**Scope cut (user, 2026-09-20): the 9K113 sight is deferred entirely.**
This module names only `UNAIDED_OPTIC` and `BINOCULAR_OPTIC` -- the latter
being today's implicit, unconditional default (`visibility.py`'s
`BINOCULAR_RANGE_MULTIPLIER`, applied to every naked-eye candidate) made
explicit, which is the core value of this slice. The 9K113's own
magnification/field-of-view/field-of-regard figures, sourced and
unverified alike, stay recorded in `body-layer/research/
2026-09-20-9k113-sight-optics-from-manual.md` until the sight itself gets
its own slice. `Optic` therefore carries only a field of view
(`fov_half_angle_deg`) -- **no field-of-regard fields** (how far an optic
can be *pointed*, as opposed to what it shows once pointed): with no
sighted optic in this table, every entry's regard would be `None` and
unexercised by any test, so those fields were cut along with the 9K113
entries that were their only reason to exist. A future 9K113 slice adds
them back, sourced fields intact in the research note above.

`Optic.boresight_azimuth_deg` is pinned to `0.0` (dead ahead, Decision 3
of the plan) -- there is no slew model in this slice.

Pure, no I/O, no DCS/world-model dependency -- mirrors `cockpit_mask.py`'s
own posture.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from perception.visibility import BINOCULAR_RANGE_MULTIPLIER


@dataclass(frozen=True, slots=True)
class Optic:
    """One named optic: what it magnifies by, what it shows once pointed
    (field of view), and how much of that raw magnification is actually
    usable in practice.

    `magnification` is the instrument's own, true optical magnification.
    `handheld_effectiveness` (default `1.0`, i.e. no derating) is a
    **separate** factor for anything that erodes what raw magnification
    alone would predict -- a handheld instrument's image shake in a
    vibrating airframe being the motivating case (see `BINOCULAR_OPTIC`
    below). `effective_magnification` is the product of the two, and is
    the figure both `visibility.py`'s range-threshold formula and
    `_achieved_tier` actually use -- never `magnification` alone.
    `fov_half_angle_deg` is `None` for an optic with no FOV restriction
    (the naked eye and the binoculars -- the cockpit occlusion mask is
    their only envelope)."""

    name: str
    magnification: float
    fov_half_angle_deg: float | None
    boresight_azimuth_deg: float = 0.0
    handheld_effectiveness: float = 1.0

    @property
    def effective_magnification(self) -> float:
        """The multiplier `visibility.py` actually applies to the range
        threshold -- `magnification * handheld_effectiveness`, never raw
        `magnification` alone. See the class docstring and
        `BINOCULAR_OPTIC`'s own comment for why the two are kept separate
        rather than folded into one number."""
        return self.magnification * self.handheld_effectiveness


#: Magnification 1.0, no derating, no FOV restriction -- the naked eye
#: sees whatever the cockpit mask admits.
UNAIDED_OPTIC: Final[Optic] = Optic(
    name="unaided",
    magnification=1.0,
    fov_half_angle_deg=None,
)

#: **Today's implicit default, now a named value -- and, as of 2026-09-20,
#: a realistic instrument split into its two honest components rather than
#: one borrowed engine constant.**
#:
#: `magnification=8.0` is a Б-8 / БПЦ5 8x30 -- standard Soviet compact
#: issue, handheld-practical in a vibrating Mi-24 front cockpit (user,
#: 2026-09-20). Realistic, but not measured in-sim.
#:
#: `handheld_effectiveness=0.5` is a **named, measurable** derating factor
#: for what raw 8x magnification does not survive intact when handheld in
#: a vibrating airframe rather than mounted. It is itself unmeasured --
#: chosen specifically so `effective_magnification` (8.0 * 0.5 = 4.0)
#: reproduces `BINOCULAR_RANGE_MULTIPLIER` exactly, so this refactor
#: changes no detection behaviour (see `visibility.py`'s docstring and
#: `test_binocular_optic_effective_magnification_matches_the_calibrated_
#: constant` below). The point of naming it separately from magnification
#: is that a real number now exists for a future calibration sortie to
#: actually measure, which was impossible while it was hidden inside a
#: mislabelled "magnification."
#:
#: `effective_magnification` (4.0) is `BINOCULAR_RANGE_MULTIPLIER` --
#: `visibility.py`'s own constant, imported rather than redefined here
#: (see that module's Decision 1 on why the constant's home stays
#: `visibility.py`) -- the empirically calibrated figure every existing
#: sortie's data is already built on. `magnification` and
#: `handheld_effectiveness` are chosen to multiply to it, not the other
#: way around.
#:
#: No FOV restriction -- binoculars magnify what is already being looked
#: at, they do not narrow where the head can turn.
BINOCULAR_OPTIC: Final[Optic] = Optic(
    name="binocular",
    magnification=8.0,
    fov_half_angle_deg=None,
    handheld_effectiveness=BINOCULAR_RANGE_MULTIPLIER / 8.0,
)


def within_optic_fov(optic: Optic, azimuth_deg: float, elevation_deg: float) -> bool:
    """True if `(azimuth_deg, elevation_deg)` -- a body-relative direction,
    same convention as `perception.geometry.BodyRelativeDirection` -- falls
    inside `optic`'s field of view.

    `optic.fov_half_angle_deg is None` means "no restriction," always
    `True` (both optics currently in this table). Otherwise compares the
    true angular separation between `(azimuth_deg, elevation_deg)` and
    `(optic.boresight_azimuth_deg, 0.0)` against the half-angle --
    small-angle-safe great-circle-style separation via the standard
    spherical law of cosines, not a flat azimuth/elevation box (an optic's
    circular eyepiece does not admit a target only because it clears an
    azimuth check and an elevation check independently)."""
    if optic.fov_half_angle_deg is None:
        return True

    az_delta_rad = math.radians(azimuth_deg - optic.boresight_azimuth_deg)
    el_rad = math.radians(elevation_deg)
    boresight_el_rad = 0.0

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
