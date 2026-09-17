"""Body-relative occlusion mask for the naked-eye perception channel --
`plans/cockpit-visibility/plan.md`, replacing `visibility.py`'s old flat
`NAKED_EYE_FOV_HALF_WIDTH_DEG` azimuth cone (see that module's docstring
for why: no elevation term at all meant Petrovich saw through the fuselage
and the floor, and the cone's one number was borrowed from the 9K113's
sight limits, not derived from the cockpit).

**Mechanism/calibration split (plan D3, `body-layer/CLAUDE.md`'s
"mechanism and calibration never share a commit" rule, from BL-2.6):** this
module is committed twice. The first commit lands this file's structure --
`OcclusionMask`, its interpolation, `is_visible`, and the per-station
`COCKPIT_MASKS` table wired into `visibility.py` -- with clearly-placeholder
numbers. The second commit only replaces those numbers with angles derived
from real cockpit screenshots, plus a derivation note; no other line in
this module changes between the two. `test_cockpit_mask.py` tests the
mechanism entirely against its own small synthetic masks, never against
`COCKPIT_MASKS`'s shipped values -- a mask table replacement in commit 2
must not be able to break that test file at all.

**Mask shape (D2):** a maximum-depression-per-azimuth-band table, small and
coarse by intent ("no need to take to canopy beam, that's too much
detail" -- user, plan D2), linearly interpolated between breakpoints, plus
a hard rear cutoff matching `docs/concept/state-transitions.jpg`'s "no
visibility to rear hemisphere": beyond `rear_cutoff_deg` nothing is visible
at all, regardless of elevation.

**Symmetric, not left/right-asymmetric (D5):** one table, mirrored across
the centreline via `abs(azimuth_deg)` in `is_visible` below. The real
cockpit is not actually symmetric (the left seat structure is more
obstructed than the right in the reference screenshots), but modelling that
would make `scan_left`/`scan_right` differ in detection performance for a
questionable amount of realism at this coarseness -- see the plan's D5 for
the full argument. The mechanism itself does not assume symmetry (nothing
below stops a future per-side table); only the populated values do.

**Per-station, not global (D6):** `COCKPIT_MASKS` is keyed by crew station
even though only `STATION_CO_PILOT` (Petrovich's own seat) is populated --
retrofitting a station dimension later, through a gate that assumed one
global mask, would cost far more than keying it now.

**Upward visibility is deliberately not modelled.** There is no separate
"maximum elevation above boresight" bound anywhere in this module -- nothing
this project cares about flies above a helicopter at low level, and the
rotor/roof would make a modelled upper limit fiction anyway (plan D2). This
falls out of the mechanism for free rather than needing a special case:
`is_visible` only ever checks `depression_deg <= max_depression_deg`, and
`depression_deg` for anything above boresight is negative, which is
trivially `<=` any of this table's (positive) values -- as long as the
target's azimuth is not past `rear_cutoff_deg`, an above-boresight contact
always clears the depression check on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Final

#: Petrovich's own seat -- the only station this project currently models
#: (D6). A future pilot/wingman perspective (`todo/todo.md`'s parked
#: "wingman brain") would add a second key here, not restructure this type.
STATION_CO_PILOT: Final[str] = "co_pilot"


@dataclass(frozen=True, slots=True)
class OcclusionMask:
    """One crew station's visibility envelope: the maximum depression
    angle (degrees, positive = below the airframe boresight,
    `perception.geometry.BodyRelativeDirection.elevation_deg` negated) the
    crew member can see down to, as a function of `abs(relative azimuth
    deg)` -- `0` is straight down the nose, `180` is dead astern.

    `breakpoints` is a non-empty tuple of `(abs_azimuth_deg,
    max_depression_deg)` pairs, sorted ascending by azimuth and covering
    `[0, rear_cutoff_deg)`; `max_depression_deg` is linearly interpolated
    between consecutive breakpoints. Beyond `rear_cutoff_deg` there is no
    visibility at all (see module docstring) -- not "very shallow", blocked
    entirely, matching `docs/concept/state-transitions.jpg`."""

    breakpoints: tuple[tuple[float, float], ...]
    rear_cutoff_deg: float

    def max_depression_deg(self, abs_azimuth_deg: float) -> float | None:
        """Max depression Petrovich can see down to at `abs_azimuth_deg`
        (already folded to `[0, 180]` -- symmetric mirroring is
        `is_visible`'s job, not this method's). `None` means blocked
        entirely (past the rear cutoff)."""
        if abs_azimuth_deg >= self.rear_cutoff_deg:
            return None

        points = self.breakpoints
        if abs_azimuth_deg <= points[0][0]:
            return points[0][1]
        for (az_a, dep_a), (az_b, dep_b) in pairwise(points):
            if az_a <= abs_azimuth_deg <= az_b:
                if az_b == az_a:
                    return dep_b
                fraction = (abs_azimuth_deg - az_a) / (az_b - az_a)
                return dep_a + fraction * (dep_b - dep_a)
        # abs_azimuth_deg is past the last breakpoint but still short of
        # rear_cutoff_deg -- hold the last breakpoint's value flat.
        return points[-1][1]


#: **Derivation note (plan D7) -- uncalibrated, first-pass, +/-10-15 deg at
#: best.** Read off four co-pilot-seat screenshots (`win-mac-sync/
#: from-windows/Screen_260917_0000{55,59,105,125}.jpg` -- forward/right/
#: left/wide) at an **assumed pitch of 5 deg nose down** (typical cruise,
#: user 2026-09-17). Because the mask is body-relative (D1), every angle
#: below is measured from the **airframe boresight**, not the visible
#: horizon -- at 5 deg nose down the horizon sits ~5 deg above boresight in
#: each screenshot, so a horizon-referenced reading would be uniformly 5
#: deg too shallow as a depression limit. Record this assumed pitch
#: alongside the table (this comment) so a future re-derivation from a
#: different attitude corrects consistently rather than silently
#: inheriting this one's.
#:
#: - **0 deg (nose), `...55`/`...125`:** genuinely good -- the chin glazing
#:   lets the boresight-relative view run steep, estimated ~45 deg down
#:   before the dash/gunsight assembly starts occluding it.
#: - **~90 deg (abeam), `...59` (right):** horizon and mid-distance stay
#:   visible, but the sill/side console cuts off the near ground -- no
#:   steep depression, estimated ~15 deg.
#: - **Left (`...105`) is visibly more obstructed** than the right in the
#:   same screenshot set, consistent with the plan's asymmetry finding --
#:   not read as a separate number here because D5 keeps one symmetric
#:   table regardless (see module docstring).
#: - **Rear hemisphere:** no screenshot evidence either way -- kept at the
#:   spec diagram's flat "no visibility to rear hemisphere"
#:   (`docs/concept/state-transitions.jpg`), same `rear_cutoff_deg=100.0`
#:   commit 1 shipped as a placeholder, now the real, if still coarse,
#:   value.
#:
#: 20/50/80 deg breakpoints are not independently screenshot-derived --
#: they interpolate between the two anchored readings above (0 deg/~45 and
#: ~90 deg/~15) on the plan D2 band shape, tapering the last segment toward
#: the rear cutoff. Treat this table exactly like `visibility.py`'s own
#: uncalibrated tier constants: a documented starting point for live-sortie
#: retuning, not a settled number.
_CO_PILOT_MASK: Final[OcclusionMask] = OcclusionMask(
    breakpoints=(
        (0.0, 45.0),
        (20.0, 35.0),
        (50.0, 22.0),
        (80.0, 15.0),
        (100.0, 5.0),
    ),
    rear_cutoff_deg=100.0,
)

#: Per-station occlusion masks (D6). Only `STATION_CO_PILOT` is populated.
COCKPIT_MASKS: Final[dict[str, OcclusionMask]] = {
    STATION_CO_PILOT: _CO_PILOT_MASK,
}


def is_visible(mask: OcclusionMask, azimuth_deg: float, elevation_deg: float) -> bool:
    """Whether a target at `azimuth_deg` (signed, `perception.geometry.
    BodyRelativeDirection.azimuth_deg` convention) / `elevation_deg`
    (signed, same convention) clears `mask`. Symmetric mirroring (D5)
    happens here, via `abs(azimuth_deg)` -- `OcclusionMask` itself only
    ever sees an already-folded `[0, 180]` azimuth."""
    abs_azimuth_deg = abs(azimuth_deg)
    max_depression_deg = mask.max_depression_deg(abs_azimuth_deg)
    if max_depression_deg is None:
        return False
    depression_deg = -elevation_deg
    return depression_deg <= max_depression_deg
