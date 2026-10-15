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

**The 9K113 sight is now two named `Optic` instances (`BL-B64`,
`plans/9k113-sight/plan.md` §11, Stage 1).** `SIGHT_WIDE_OPTIC`/
`SIGHT_NARROW_OPTIC` carry the multipliers measured in detection-cones
slice 2A (wide 3.55/7.00/6.50, narrow 5.81/13.75/15.00) and the FOV figures
sourced in `body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`
(wide 11.5 deg full angle, narrow 6.0 deg full angle -- half-angles below).
**Nothing selects either of them yet** -- the same posture `BINOCULAR_OPTIC`
held between slice 2A and `plans/binocular-optic/plan.md`, and for the same
reason: the table entry and the policy that reaches it (`BL-B64` Stage 2,
not built here) are separate decisions with separate risks. A concrete
`PerceptionSource` that selects `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`
would also need the field-of-regard check and the player-bubble cone
(`BL-B64` Stage 2 and §12 of the plan) -- neither exists yet, so passing
either optic to `check_visibility` today would be well-formed but is not
wired into any live path.

**`Optic` gains three field-of-regard fields** (`regard_azimuth_half_deg`,
`regard_elevation_up_deg`, `regard_elevation_down_deg`) -- how far an optic
can be *pointed*, as opposed to what it shows once pointed
(`fov_half_angle_deg`) or the cockpit occlusion mask. `None` on
`UNAIDED_OPTIC`/`BINOCULAR_OPTIC` (pointed by the head, unrestricted);
sourced on the two sight optics from the English-language Mi-24P manual's
§3.4 (±60 deg azimuth, +20/-15 deg elevation -- the research note above,
"The sight's real angular limits"). Three fields, not one, because the
elevation envelope is asymmetric. **Nothing reads these yet** -- the field
of regard is unenforced data until `BL-B64` Stage 2 (or `[[BL-B66]]`) adds
the check; recorded here now because the sight optics exist to carry it.

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

**`UNAIDED_OPTIC.fov_half_angle_deg`: `None` -> `90.0` (user direction,
`docs/acceptance/2026-10-15-9k113-sight-direction.md` §14, done alongside
the 9K113 table work above).** `perception.gaze.FULL_GAZE` is already
`half_width_deg = 90.0` and the gaze gate runs before this one, so this
mostly restates an existing bound rather than changing behaviour -- see
that constant's own docstring just below for the one real difference
(`within_gaze` is azimuth-only, `within_optic_fov` is not) and for why the
naked eye's own `None`-means-no-op branch is being retired rather than
exercised for the first time. It also closes the one asymmetry `BL-B64`'s
cone work depends on: before this, the naked eye was the one optic whose
FOV gate was a documented no-op, which made "LOS is bounded by the optic's
FOV" false of the default optic specifically. 180 deg is explicitly
peripheral vision (the user's own framing) -- a narrower *focus* FOV,
reconciled against `perception.gaze.FOCUS_CONE_HALF_WIDTH_DEG`, is a later
refinement, not this one.

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

    `fov_half_angle_deg` was `None` for an optic with no FOV restriction;
    as of `BL-B64` (direction §14) that is no longer any shipped optic --
    `UNAIDED_OPTIC` carries a real value (90.0) too, so `within_optic_fov`'s
    `None` branch is unreachable from this table today (kept for a future
    pseudo-optic, see that function's own docstring). `BINOCULAR_OPTIC` was
    the first optic in this table to carry a real value; it no longer is
    the only one.

    `peripheral` (slice 2B) is `True` iff this optic retains a wide,
    change-detecting peripheral channel alongside its focused view --
    module docstring.

    `regard_azimuth_half_deg`/`regard_elevation_up_deg`/
    `regard_elevation_down_deg` (`BL-B64` Stage 1) are the field of
    regard -- how far this optic can be *pointed* -- `None` for an optic
    pointed by the head (unrestricted). Three fields because the
    elevation envelope need not be symmetric (the 9K113's is: +20/-15).

    `range_cap_m` (`BL-B64` Stage 2, `plans/9k113-sight/plan.md` §12a) is
    the sanity bound `visibility.check_visibility`'s range-admission gate
    clamps against -- generalises the old global `visibility.
    NAKED_EYE_RANGE_CAP_M` into a per-optic figure, the honest shape
    §12a's own finding calls for: the cone that admits a narrow-sight
    candidate past 10 km (direction §7) buys nothing if the range gate
    immediately clamps it back and rejects it, so the two must change
    together. `None` (every optic before this entry) means "use
    `visibility.NAKED_EYE_RANGE_CAP_M`" -- `check_visibility`/`tier_ranges`
    resolve that default themselves, so this module never has to import a
    literal from `visibility.py` (which would reinstate the circular
    import slice 2A deliberately dissolved, module docstring). The two
    sight optics below set `20_000.0` explicitly (direction §7's cone
    depth) -- deliberately the same figure as `[[BL-B64]]`'s 20 km cone,
    but **not aliased to it**: this field answers "how far can this optic
    claim to have resolved something," the cone answers "is a candidate
    even worth computing at all" (`association.PLAYER_BUBBLE_RADIUS_M`'s
    own docstring draws the identical distinction for the un-capped
    case), and a future optic could reasonably need the two to differ."""

    name: str
    presence_range_mult: float
    class_range_mult: float
    type_range_mult: float
    fov_half_angle_deg: float | None
    #: Defaults `True` so every existing synthetic test `Optic(...)` still
    #: constructs unchanged -- only `BINOCULAR_OPTIC` sets this `False`.
    peripheral: bool = True
    #: `None` for every optic pointed by the head (`UNAIDED_OPTIC`,
    #: `BINOCULAR_OPTIC`); sourced from the Mi-24P manual's English edition
    #: for the two sight optics below.
    regard_azimuth_half_deg: float | None = None
    regard_elevation_up_deg: float | None = None
    regard_elevation_down_deg: float | None = None
    #: `None` (every optic before `BL-B64` Stage 2) defers to
    #: `visibility.NAKED_EYE_RANGE_CAP_M` -- see this field's own
    #: docstring above.
    range_cap_m: float | None = None


#: 1.0 on every tier -- the cockpit mask is the naked eye's only range
#: envelope. **The default `check_visibility` optic as of 2026-09-20** (was
#: `BINOCULAR_OPTIC` -- see module docstring's "Naked eye is now the
#: default" note for why). The baseline observer every other optic's
#: multipliers are measured against.
#:
#: `fov_half_angle_deg=90.0`, not `None` (`BL-B64`, direction §14) -- see
#: the module docstring's own section on this change for why it is nearly
#: a no-op (`perception.gaze.FULL_GAZE` already bounds the naked eye to
#: +/-90 deg) and what the one real difference is.
UNAIDED_OPTIC: Final[Optic] = Optic(
    name="unaided",
    presence_range_mult=1.0,
    class_range_mult=1.0,
    type_range_mult=1.0,
    fov_half_angle_deg=90.0,
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

#: The 9K113 Raduga-Sh sight, wide (x3.3) setting -- `BL-B64` Stage 1,
#: `plans/9k113-sight/plan.md` §11. **Nothing selects this yet** (module
#: docstring).
#:
#: `presence_range_mult=3.55`/`class_range_mult=7.00`/`type_range_mult=
#: 6.50` -- measured in detection-cones slice 2A, sitting unused in this
#: module's history until now (previously recorded only in the decisions
#: doc and `perception.clustering`'s own docstring).
#:
#: `fov_half_angle_deg=5.75` -- half of the sourced 11.5 deg full field
#: (`body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`,
#: "Field of view per magnification"; that note flags both FOV figures as
#: user-supplied and explicitly unverified against either manual edition,
#: unlike the field-of-regard figures below).
#:
#: `regard_azimuth_half_deg=60.0`, `regard_elevation_up_deg=20.0`,
#: `regard_elevation_down_deg=-15.0` -- the sight head's own angular
#: limits, sourced from the English-language Mi-24P manual's §3.4
#: ("The sight's real angular limits -- SOURCED"), distinct from and far
#: wider than the FOV above: the sight *sees* a few degrees at a time and
#: can be *pointed* across a much wider arc.
SIGHT_WIDE_OPTIC: Final[Optic] = Optic(
    name="sight_wide",
    presence_range_mult=3.55,
    class_range_mult=7.00,
    type_range_mult=6.50,
    fov_half_angle_deg=5.75,
    peripheral=False,
    regard_azimuth_half_deg=60.0,
    regard_elevation_up_deg=20.0,
    regard_elevation_down_deg=-15.0,
    range_cap_m=20_000.0,
)

#: The 9K113 Raduga-Sh sight, narrow (x10) setting -- same source and
#: caveats as `SIGHT_WIDE_OPTIC` above.
#:
#: `presence_range_mult=5.81`/`class_range_mult=13.75`/`type_range_mult=
#: 15.00` -- measured in detection-cones slice 2A; `perception.clustering`'s
#: own floor-fix derivation already names the 5.81 figure (module
#: docstring).
#:
#: `fov_half_angle_deg=3.00` -- half the sourced 6.0 deg full field. The
#: research note flags one internal inconsistency worth repeating here:
#: magnification rises 3.03x (x3.3 -> x10) while this field narrows only
#: 1.92x (11.5 -> 6.0 deg); a single optical train sharing one objective
#: would put the narrow field nearer 3.8 deg. Not proof of an error --
#: separate optical paths can legitimately break that relation -- but if
#: exactly one of the two sourced FOVs is wrong, the note says 6.0 deg is
#: the one to doubt.
#:
#: Field of regard is identical to `SIGHT_WIDE_OPTIC`'s -- both settings
#: share one sight head, so what angles it can be *pointed* to does not
#: depend on which magnification is selected.
SIGHT_NARROW_OPTIC: Final[Optic] = Optic(
    name="sight_narrow",
    presence_range_mult=5.81,
    class_range_mult=13.75,
    type_range_mult=15.00,
    fov_half_angle_deg=3.00,
    peripheral=False,
    regard_azimuth_half_deg=60.0,
    regard_elevation_up_deg=20.0,
    regard_elevation_down_deg=-15.0,
    range_cap_m=20_000.0,
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
    `True`. **No optic in this table sets it any more as of `BL-B64`**
    (direction §14 gave `UNAIDED_OPTIC` a real 90-degree value) -- this
    branch is kept rather than deleted because it is the documented
    contract of a `None` half-angle, and a future pseudo-optic (e.g. a
    peripheral-awareness channel genuinely wider than 90 degrees) may still
    want it. Otherwise compares the true angular
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
