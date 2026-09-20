"""Named optics and per-optic field-of-view test --
`plans/detection-cones-slice1/plan.md`, slice 1 of the "detection cones"
milestone `body-layer/ROADMAP.md` names.

**Two bounds, not one.** Each `Optic` below carries two independent
angular quantities that are easy to conflate but describe different
things:

* **Field of view** (`fov_half_angle_deg`) -- how much the eyepiece shows
  once it is pointed somewhere. Genuinely circular (Decision 2 of the
  plan), so one half-angle is enough.
* **Field of regard** (`regard_azimuth_half_deg` /
  `regard_elevation_min_deg` / `regard_elevation_max_deg`) -- how far the
  optic can be *pointed* in the first place. A rectangle, and asymmetric
  in elevation for the 9K113 sight, so it cannot be collapsed into a
  half-angle at all.

Collapsing the two would make the sight appear to see its FOV degrees of
the world *total*, when in fact it sees that many degrees *at a time*,
anywhere within its (much wider) regard rectangle.

**The regard fields are data only in this slice -- nothing gates on them
yet.** `Optic.boresight_azimuth_deg` is pinned to `0.0` (dead ahead,
Decision 3) and there is no slew model, so the FOV cone always sits well
inside the regard rectangle and a regard check could never fire in
today's code. They are carried here for slice 2 (attention/scanning),
which is where pointing the optic becomes possible at all. Do not add a
regard gate to `visibility.check_visibility` on the strength of these
fields existing -- an unreachable branch that no test can exercise is
worse than no branch.

**Provenance is two different classes of number, not one.** The regard
bounds for the 9K113 sight (`SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`) are
*sourced* -- the English-language Mi-24P manual, section 3.4 "Missile
Guidance Controls" (`body-layer/research/
2026-09-20-9k113-sight-optics-from-manual.md`). The FOV half-angles for
those same two optics are *user-supplied and unverified* -- adopted on
user direction so the table holds real-shaped numbers rather than round
invented ones, but with a known internal inconsistency: magnification
rises ×3.03 (×3.3 -> ×10) while the field narrows only ×1.92
(11.5° -> 6.0°). A single optical train sharing one objective would
narrow in proportion to magnification, which would put the narrow field
near 3.8° instead of 3.0° (6.0° full). **If a sim measurement ever
contradicts one of these two figures, doubt the narrow FOV (6.0° full)
first** -- see the research note's "One internal inconsistency" section.
Each `Optic`'s own docstring below repeats which class its numbers belong
to, so the distinction survives being read out of context.

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
    (field of view), and how far it can be pointed in the first place
    (field of regard). See module docstring for why those are two
    independent bounds, and for which fields are sourced vs. unverified
    per optic.

    `fov_half_angle_deg` / `regard_azimuth_half_deg` /
    `regard_elevation_min_deg` / `regard_elevation_max_deg` are all
    `None` for an optic with no such restriction (the naked eye and the
    binoculars, per the plan's table -- the cockpit occlusion mask is
    their only envelope). `regard_elevation_min_deg` is signed negative
    for "below boresight", positive for "above", matching
    `perception.geometry.BodyRelativeDirection.elevation_deg`'s own sign
    convention -- **not** `cockpit_mask.py`'s depression convention (that
    module's `max_depression_deg` is positive-down; this dataclass is
    positive-up, deliberately kept aligned with `elevation_deg` since
    `within_optic_fov` below compares directly against it)."""

    name: str
    magnification: float
    fov_half_angle_deg: float | None
    boresight_azimuth_deg: float = 0.0
    regard_azimuth_half_deg: float | None = None
    regard_elevation_min_deg: float | None = None
    regard_elevation_max_deg: float | None = None


#: Magnification 1.0, no FOV restriction (the naked eye sees whatever the
#: cockpit mask admits), no field of regard (the head can turn to look
#: anywhere the mask allows).
UNAIDED_OPTIC: Final[Optic] = Optic(
    name="unaided",
    magnification=1.0,
    fov_half_angle_deg=None,
)

#: **Today's implicit default, now a named value.** Magnification is
#: `BINOCULAR_RANGE_MULTIPLIER` (`visibility.py`'s own constant, imported
#: rather than redefined here -- see that module's Decision 1 on why the
#: constant's home stays `visibility.py`), no FOV restriction, no field of
#: regard, same as `UNAIDED_OPTIC` -- binoculars magnify what is already
#: being looked at, they do not narrow or widen where the head can turn.
BINOCULAR_OPTIC: Final[Optic] = Optic(
    name="binocular",
    magnification=BINOCULAR_RANGE_MULTIPLIER,
    fov_half_angle_deg=None,
)

#: The 9K113 sight's guidance unit (ПН) at its wide magnification setting
#: (handle position A, ×3.3 -- `body-layer/research/
#: 2026-09-20-9k113-sight-optics-from-manual.md`). `fov_half_angle_deg`
#: (5.75°, 11.5° full) is **user-supplied and unverified** -- see module
#: docstring. `regard_azimuth_half_deg`/`regard_elevation_min_deg`/
#: `regard_elevation_max_deg` (±60° azimuth, −15°/+20° elevation) are
#: **sourced** from the English-language Mi-24P manual §3.4. Boresight
#: pinned dead ahead (Decision 3) -- no slew model exists yet.
SIGHT_WIDE_OPTIC: Final[Optic] = Optic(
    name="sight_wide",
    magnification=3.3,
    fov_half_angle_deg=5.75,
    boresight_azimuth_deg=0.0,
    regard_azimuth_half_deg=60.0,
    regard_elevation_min_deg=-15.0,
    regard_elevation_max_deg=20.0,
)

#: The same 9K113 guidance unit at its narrow setting (handle position B,
#: ×10). `fov_half_angle_deg` (3.0°, 6.0° full) is **user-supplied and
#: unverified**, and is the figure most likely to be wrong -- see module
#: docstring's note on the magnification-vs-field-narrowing inconsistency.
#: Field of regard is the same sourced envelope as `SIGHT_WIDE_OPTIC`
#: (both magnifications share one gyro-stabilised head).
SIGHT_NARROW_OPTIC: Final[Optic] = Optic(
    name="sight_narrow",
    magnification=10.0,
    fov_half_angle_deg=3.0,
    boresight_azimuth_deg=0.0,
    regard_azimuth_half_deg=60.0,
    regard_elevation_min_deg=-15.0,
    regard_elevation_max_deg=20.0,
)


def within_optic_fov(optic: Optic, azimuth_deg: float, elevation_deg: float) -> bool:
    """True if `(azimuth_deg, elevation_deg)` -- a body-relative direction,
    same convention as `perception.geometry.BodyRelativeDirection` -- falls
    inside `optic`'s field of view.

    `optic.fov_half_angle_deg is None` means "no restriction," always
    `True` (the naked eye and binoculars). Otherwise compares the true
    angular separation between `(azimuth_deg, elevation_deg)` and
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

    return separation_deg <= optic.fov_half_angle_deg
