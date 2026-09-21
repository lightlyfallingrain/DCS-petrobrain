"""`Gaze` -- where Petrovich's eyes are pointed right now, as a pure filter
`visibility.check_visibility` applies -- `plans/detection-cones-slice2/
plan.md`'s 2B ("gaze as a filter").

**Gaze needs no state at all (hard part 1).** `perception` must not import
`belief` (`source.py`'s own module docstring), and gaze looks like it wants
to live in belief -- it is driven by commands, which are belief-level
intents -- but it is a *perceptual act*, not a belief. The resolution: a
`Gaze` is a frozen value, not a state machine. Belief owns the *intent*
(`belief.tasks.PendingIntent` + `belief.attention.AttentionArea.
relative_sector`, both already exist); `logger.py`'s poll loop reads that
intent each tick and hands perception a frozen `Gaze`; perception owns the
*act* of filtering against it. Nothing here mutates, resets on a telemetry
gap, or needs serialising for replay -- see `logger.py`'s own resolution
function (`_active_gaze`) for the belief-side half of this boundary.

**2B is deliberately behaviour-preserving.** `check_visibility`'s `gaze`
parameter defaults to `None`, meaning "no restriction at all" -- the gaze
gate is skipped entirely, exactly today's behaviour before this module
existed. `FULL_GAZE` below is a named, explicit forward-hemisphere wedge
(the same 90-degree half-width `RelativeSector`'s own `"full"` wedge
already uses) -- but it is *not* what `logger.py` assigns by default when
no scan command is pending, specifically because it is narrower than the
cockpit mask's own 130-degree rear cutoff (`cockpit_mask.py`,
`rear_cutoff_deg=130.0`): assigning it unconditionally would silently
narrow real detection between 90 and 130 degrees off the nose, which is not
a no-op. `FULL_GAZE` exists as the explicit "player selected the full
forward sector" value (`RelativeSector.full`'s own gaze), not as a
disguised always-on default. `logger.py` assigns `None` when no command is
active, precisely so the regression gate this slice is named for ("with no
command issued, the trace is identical to the previous slice") holds by
construction, not by coincidence on whatever a given fixture happens to
exercise.

**`RelativeSector`, `RELATIVE_SECTORS`, and the wedge table moved down from
`belief.attention` (hard part 8's setup).** `belief` is allowed to import
`perception` (it already imports `perception.geometry`); the reverse is
forbidden, which is exactly why this vocabulary has to live here rather
than the gate moving up into `belief`. `belief.attention` re-imports these
three names instead of defining them, so every existing importer
(`belief.contacts`, `belief.tools`, `belief.crew_console`, their tests)
keeps working unchanged. With a 30-degree focus cone and 30 degrees per
o'clock hour (2C), the o'clock cone *is* the o'clock position -- so
`RelativeSector` (the F10 command vocabulary's granularity) and the
o'clock cones (free scan's granularity, 2C) are two readings of the same
wedge arithmetic, which is the other reason this table belongs in
`perception` rather than staying `belief`-only.

**The bypass seam (hard parts 2a/4): salience bypasses the gaze gate only
when the active optic still has peripheral vision.** `gaze_for` is the one
function this seam is built from -- `optic.peripheral` (`optics.py`) is
what makes it operative today with no attention-capture channel wired yet:
supply a candidate id in `stimulus_ids` and it clears the gaze gate under
`UNAIDED_OPTIC` (`peripheral=True`) but not under `BINOCULAR_OPTIC`
(`peripheral=False`) -- the binocular's real cost (losing change detection
entirely, not just field of view) becomes an executable fact rather than
prose, with zero triggers wired. **The invariant that keeps this from
becoming an omniscience back door: a bypass clears the gaze gate only --
never the cockpit mask, never range/size, never terrain LOS.**
`gaze_for` returning `None` for a bypassed candidate is handed to
`check_visibility` exactly like today's unrestricted default; every other
gate in that function still runs independently and can still reject it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from perception.geometry import angular_delta_deg
from perception.optics import Optic

#: The crew-facing, ownship-relative sectors from `docs/concept/
#: state-transitions.jpg` -- moved here from `belief.attention` (module
#: docstring). Deliberately do **not** tile the circle: the spec states
#: "there is no visibility to rear hemisphere", so `full` spans the forward
#: hemisphere only and no rear sector is offered.
RelativeSector = Literal["ahead", "left", "right", "full"]

RELATIVE_SECTORS: Final[tuple[RelativeSector, ...]] = (
    "ahead",
    "left",
    "right",
    "full",
)

#: Each relative sector as `(center, half_width)` in **relative bearing
#: degrees**, 12 o'clock = 0, positive clockwise (so 3 o'clock = +90,
#: 9 o'clock = -90). Straight from the spec's o'clock bounds: `ahead`
#: 11-1, `left` 9-11, `right` 1-3, `full` 9-3. One o'clock hour is 30
#: degrees. `gaze_from_relative_sector` below reads this table directly --
#: it is already expressed body-relative, the exact convention `Gaze` uses,
#: so a commanded scan sector needs no further conversion to become a gaze.
_RELATIVE_SECTOR_WEDGE_DEG: Final[dict[RelativeSector, tuple[float, float]]] = {
    "ahead": (0.0, 30.0),
    "left": (-60.0, 30.0),
    "right": (60.0, 30.0),
    "full": (0.0, 90.0),
}


@dataclass(frozen=True, slots=True)
class Gaze:
    """Where Petrovich's eyes are pointed, as a body-relative azimuth wedge
    -- `center_azimuth_deg`/`half_width_deg` follow `perception.geometry.
    BodyRelativeDirection`'s convention (0 = dead ahead, positive
    clockwise), the same frame `visibility.check_visibility` already
    resolves every candidate into before testing it. `label` is a short,
    human-readable name (`"left"`, `"full"`, an o'clock hour in 2C) for
    debug/trace output -- never compared against or branched on."""

    center_azimuth_deg: float
    half_width_deg: float
    label: str


#: The forward hemisphere, matching `RelativeSector.full`'s own wedge --
#: **not** the runtime default (module docstring). Exists as the explicit
#: gaze a `"full"` scan command implies, and as a convenient fixture value
#: in tests.
FULL_GAZE: Final[Gaze] = Gaze(center_azimuth_deg=0.0, half_width_deg=90.0, label="full")


def within_gaze(gaze: Gaze, azimuth_deg: float) -> bool:
    """Whether a body-relative `azimuth_deg` (same convention as
    `perception.geometry.BodyRelativeDirection.azimuth_deg`) falls inside
    `gaze`'s wedge -- a pure azimuth test, no elevation term (hard part 3's
    Risks note: that is what makes it the cheapest, most selective gate,
    and the cockpit mask's own depression limits are what catch a steep
    dive/climb instead)."""
    return (
        angular_delta_deg(gaze.center_azimuth_deg, azimuth_deg) <= gaze.half_width_deg
    )


def gaze_for(
    object_id: int,
    gaze: Gaze | None,
    stimulus_ids: frozenset[int],
    optic: Optic,
) -> Gaze | None:
    """The effective gaze `check_visibility` should apply to `object_id`
    this poll (module docstring, hard parts 2a/4): `None` (no restriction)
    when `object_id` is a captured peripheral stimulus *and* `optic` still
    has peripheral vision -- otherwise `gaze` unchanged, including when
    `gaze` is already `None`. `stimulus_ids` defaults to an empty
    `frozenset` at every call site until the attention-capture channel
    exists (explicitly out of scope, plan's "Explicitly out of scope"
    section), so this is a true no-op today; the rule it encodes is live
    and tested regardless."""
    if object_id in stimulus_ids and optic.peripheral:
        return None
    return gaze


def gaze_from_relative_sector(sector: RelativeSector) -> Gaze:
    """The `Gaze` a commanded ownship-relative scan sector implies --
    reads `_RELATIVE_SECTOR_WEDGE_DEG` directly, which is already
    body-relative, so no reprojection or conversion is needed: the F10
    command vocabulary's belief-level wedge and this filter's
    perception-level wedge are the same numbers by construction. Used by
    `logger.py`'s per-poll gaze resolution (module docstring)."""
    center, half_width = _RELATIVE_SECTOR_WEDGE_DEG[sector]
    return Gaze(center_azimuth_deg=center, half_width_deg=half_width, label=sector)
