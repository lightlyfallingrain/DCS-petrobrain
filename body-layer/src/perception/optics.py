"""Named optics and per-optic field-of-view test --
`plans/detection-cones-slice1/plan.md`, slice 1 of the "detection cones"
milestone `body-layer/ROADMAP.md` names.

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

`Optic.boresight_azimuth_deg` is pinned to `0.0` (dead ahead, Decision 3
of the plan) -- there is no slew model in this slice.

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

**The `BINOCULAR_RANGE_MULTIPLIER` round trip, stated honestly so a future
reader does not conclude it was pointless (`visibility.py`'s own docstring
carries the full chronology; this is the short version):** 4.0 (inherited,
unexamined, from `HelperAI.lua`'s `extra_eyesight_ratio`) -> 8.0 (a
same-session excursion: a realistic 8x30 instrument, magnification stated
honestly with no derating) -> **4.0 again (final, this change)**. The
final 4.0 is numerically identical to the first but is **not** the
restored inherited number -- it is independently derived from a Б-6 6x30
(a real, honestly-stated 6x magnification) times a stabilisation penalty
for handheld use on a vibrating airframe (see `BINOCULAR_OPTIC` below).
That it lands on the same value as the number this project spent two
passes trying to get away from is a coincidence worth keeping, not
evidence the excursion was wasted: the old 4.0 was an unexamined borrowed
constant; the new 4.0 is a derived one that happens to match it, and --
for the first time -- also matches what the 2026-09-17 screenshot ladder
independently shows. Two different lines of evidence (a physical
derivation and photographic ground truth) landing on the same number is a
real confirmation, not a round trip back to where this started.

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
    """One named optic: what it magnifies by, and what it shows once
    pointed (field of view). `magnification` is the figure `visibility.
    py`'s range-threshold formula and `_achieved_tier` actually use --
    stated honestly as the instrument's own optical magnification, no
    hidden derating factor (see module docstring). `fov_half_angle_deg`
    is `None` for an optic with no FOV restriction (the naked eye -- the
    cockpit occlusion mask is its only envelope); `BINOCULAR_OPTIC` below
    is the first optic in this table to carry a real value."""

    name: str
    magnification: float
    fov_half_angle_deg: float | None
    boresight_azimuth_deg: float = 0.0


#: Magnification 1.0, no FOV restriction -- the cockpit mask is the naked
#: eye's only envelope. **The default `check_visibility` optic as of
#: 2026-09-20** (was `BINOCULAR_OPTIC` -- see module docstring's "Naked eye
#: is now the default" note for why).
UNAIDED_OPTIC: Final[Optic] = Optic(
    name="unaided",
    magnification=1.0,
    fov_half_angle_deg=None,
)

#: **No longer the default -- a deliberate, narrower, raised-to-the-eyes
#: act, as of 2026-09-20** (see module docstring). A Б-6 6x30 -- Soviet
#: standard compact issue, true field of view ~8.5 deg.
#:
#: `magnification=4.0` is `BINOCULAR_RANGE_MULTIPLIER` (`visibility.py`'s
#: own constant, imported rather than redefined here -- see that module's
#: Decision 1 on why the constant's home stays `visibility.py`), derived
#: as **6x raw glass times a ~0.67 unstabilised-platform penalty**:
#: handheld 6x on a vibrating helicopter does not deliver 6x of usable
#: acuity (`6.0 * 0.67 ~= 4.0`). Unlike the earlier, reversed
#: `handheld_effectiveness` split (`visibility.py`'s own docstring has that
#: history), this is not a separate dataclass field manufactured to cancel
#: a number back to a target -- it is the derivation behind this one
#: `magnification` value, stated in prose because there is no second field
#: for it to live in. **This is also, independently, what the
#: 2026-09-17 screenshot ladder's binocular column shows** -- the first
#: time the physical argument (glass x stabilisation penalty) and the
#: photographic evidence have produced the same number without either
#: being tuned to match the other.
#:
#: `fov_half_angle_deg=4.25` (half the ~8.5 deg true field) -- **set to a
#: real value, not `None`, for the first time.** Safe precisely because
#: binoculars are no longer the default: no concrete `PerceptionSource`
#: calls `check_visibility` with this optic yet (plan Decision 4), so the
#: gate cannot misfire in the live path today, and `within_optic_fov`
#: finally has a real number to enforce once mode selection wires this
#: optic in (slice 2). Binoculars magnifying with no field-of-view cost at
#: all was the free-lunch half of the over-detection problem this change
#: fixes -- magnification without a narrower cone was exactly backwards.
BINOCULAR_OPTIC: Final[Optic] = Optic(
    name="binocular",
    magnification=BINOCULAR_RANGE_MULTIPLIER,
    fov_half_angle_deg=4.25,
)


def within_optic_fov(optic: Optic, azimuth_deg: float, elevation_deg: float) -> bool:
    """True if `(azimuth_deg, elevation_deg)` -- a body-relative direction,
    same convention as `perception.geometry.BodyRelativeDirection` -- falls
    inside `optic`'s field of view.

    `optic.fov_half_angle_deg is None` means "no restriction," always
    `True` (`UNAIDED_OPTIC`). Otherwise compares the true angular
    separation between `(azimuth_deg, elevation_deg)` and
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
