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
gate in that function still runs independently and can still reject it.

**2C (`plans/detection-cones-slice2/plan.md`'s "the scan loop"): the
default stops being "no restriction" and becomes an active o'clock scan
loop.** `ScanPlan` + `gaze_at(t_sim, plan) -> Gaze` replace the plain
`Gaze | None` field `NakedEyePerceptionSource` carried through 2B --
`gaze_at` is a **pure function of sim time, not a state machine** (hard
part 1): no ticker, no mutation, nothing to reset on a telemetry gap or
serialise for replay. Two cases, both driven by table lookup + a modulo,
never a loop or a sweep:

- **Free scan** (`plan.commanded_sector is None`, `NakedEyePerceptionSource`'s
  own default when `logger.py` has no `scan_area` task pending): `SCAN_PLAN`
  -- the o'clock-cone table `12, 11, 10, 9, 12, 1, 2, 3`, each held for
  `FOCUS_DWELL_S` (2.0 s) -- indexed by `t_sim % SCAN_CYCLE_PERIOD_S`
  (16.0 s, derived as `len(SCAN_PLAN) * FOCUS_DWELL_S` rather than stated
  as its own literal, so hard part 8's plan-C fallback -- swap the table,
  nothing else -- stays a one-line edit). **Adopt A** (hard part 8): the
  *unique* 16 s reading of the diagram's 9-3 span at 2 s/cone, chosen
  because 16 s is the largest cycle for which one missed sweep still lands
  inside `belief.decay.POSITION_HALF_LIFE_S` (30 s) rather than skipping a
  whole certainty band.
- **Commanded scan** (`plan.commanded_sector` set, `plan.command_t_sim` the
  sim time the command was issued): the user's own framing of focus (hard
  part 2a) -- *"within a sector it is itself a smaller cone moving in a
  scan pattern"* -- generalises directly: each `RelativeSector` decomposes
  into its own o'clock legs (`_SECTOR_LEGS` -- `ahead` -> just `12`,
  `left` -> `11, 10, 9`, `right` -> `1, 2, 3`, `full` -> the same 8-slot
  table free scan uses), cycled from `t_sim - plan.command_t_sim` instead
  of from absolute sim time, so a scan a player just ordered starts at that
  sector's first leg rather than wherever the free-scan phase happened to
  be. This is what makes `command_t_sim` a live input rather than inert
  data carried for its own sake (hard part 2a's own standard) -- a single
  wide static wedge, 2B's commanded-scan behaviour, would leave it unused.
  A single-leg sector (`ahead`) degenerates to a static 30-degree gaze by
  construction (`len(legs) == 1`, so every `t_sim` maps to index 0), which
  is why 2B's own "commanded ahead admits a dead-ahead contact" behaviour
  still holds -- narrower than 2B's old 60-degree wedge, the same
  general narrowing every leg gets under this model, not a special case.

`gaze_from_relative_sector` (2B) is retired here, not kept alongside --
its one caller (`logger.py`'s `_active_gaze`) now builds a `ScanPlan`
instead of a static `Gaze`, and a function with no caller left is dead
code, not a hedge. `_RELATIVE_SECTOR_WEDGE_DEG` stays: `belief.attention.
AttentionArea` still reads it directly for the *success-check* wedge (a
fixed sector for "was a contact seen here at some point," an unrelated
question from "is he looking there right now")."""

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

    #: Where the look is pointed vertically, body-relative degrees,
    #: positive up (`plans/binocular-optic/plan.md` Stage 2). Zero -- level
    #: -- for every scanning gaze, which is why it defaults to it and why
    #: nothing before this needed it: the o'clock scan sweeps horizontally
    #: and `within_gaze` tests azimuth alone, unchanged.
    #:
    #: It matters only for a *narrow* optic, and there it is decisive: a
    #: ground contact 1 km away from 120 m AGL is ~6.9 degrees below the
    #: horizon, well outside a binocular's 4.25-degree half-angle. With a
    #: level boresight the instrument could never be aimed at the contacts
    #: it exists to resolve.
    center_elevation_deg: float = 0.0


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


#: One o'clock hour, half-width (module docstring, hard part 8) -- the
#: focus cone's own angular size, independent of which sector/leg it sits
#: in.
FOCUS_CONE_HALF_WIDTH_DEG: Final[float] = 15.0

#: How long the focus cone dwells on one o'clock position before stepping
#: to the next (user decision, 2026-09-21).
FOCUS_DWELL_S: Final[float] = 2.0

#: Free scan's ordered o'clock-cone table (hard part 8, "Adopt A") -- 12 is
#: deliberately visited twice per cycle (the forward arc gets double the
#: dwell of a flank o'clock), never inlined elsewhere: `gaze_at` and every
#: derived constant below read this tuple directly, so revisiting hard part
#: 8's plan-C alternative (`11, 12, 1` / `10, 9` / `2, 3`, 20 s) is a
#: one-table edit plus `belief.decay.OBSERVED_WINDOW_S`, nothing else.
SCAN_PLAN: Final[tuple[int, ...]] = (12, 11, 10, 9, 12, 1, 2, 3)

#: A commanded sector's own o'clock legs (module docstring's "Commanded
#: scan" case) -- `ahead`/`left`/`right` are exactly the three-way split
#: `SCAN_PLAN` itself is built from (`12` / `11, 10, 9` / `1, 2, 3`);
#: `full` reuses `SCAN_PLAN` verbatim, since "scan the whole 9-3 span" is
#: the free-scan table's own definition.
_SECTOR_LEGS: Final[dict[RelativeSector, tuple[int, ...]]] = {
    "ahead": (12,),
    "left": (11, 10, 9),
    "right": (1, 2, 3),
    "full": SCAN_PLAN,
}

#: Free scan's cycle period, derived rather than stated -- `len(SCAN_PLAN)
#: * FOCUS_DWELL_S` rather than a bare `16.0`, so a future table edit (hard
#: part 8's plan C) carries this constant with it automatically.
#: `belief.decay.OBSERVED_WINDOW_S` imports this directly (hard part 8's
#: "the scan period is not a free parameter").
SCAN_CYCLE_PERIOD_S: Final[float] = len(SCAN_PLAN) * FOCUS_DWELL_S


@dataclass(frozen=True, slots=True)
class ScanPlan:
    """What the naked-eye focus channel is currently doing -- a frozen
    value, never a state machine (hard part 1). `commanded_sector is None`
    means free scan; `commanded_sector` set means a commanded scan, cycling
    that sector's own o'clock legs (`_SECTOR_LEGS`) from `command_t_sim`
    (the sim time the command was issued) rather than from absolute sim
    time, so a scan a player just ordered starts at that sector's first
    leg. `command_t_sim` must be `None` exactly when `commanded_sector` is
    `None` -- `__post_init__` enforces this pairing rather than leaving it
    an unchecked convention."""

    commanded_sector: RelativeSector | None
    command_t_sim: float | None

    def __post_init__(self) -> None:
        if (self.commanded_sector is None) != (self.command_t_sim is None):
            raise ValueError(
                "ScanPlan.command_t_sim must be set if and only if "
                "commanded_sector is set"
            )


#: Free scan, module docstring's default -- `NakedEyePerceptionSource.
#: scan_plan`'s own default and `logger.py`'s `_active_gaze` fallback when
#: no `scan_area` task is pending.
FREE_SCAN_PLAN: Final[ScanPlan] = ScanPlan(commanded_sector=None, command_t_sim=None)


def _gaze_for_clock_hour(clock_hour: int) -> Gaze:
    """The `Gaze` for one o'clock position, body-relative -- `12` is dead
    ahead (`0.0`), positive clockwise (`3` is `90.0`, `9` is `-90.0`),
    matching `Gaze.center_azimuth_deg`'s own convention and
    `_RELATIVE_SECTOR_WEDGE_DEG`'s existing `left`/`right` centers (`10`
    o'clock is `-60.0`, `2` o'clock is `60.0`)."""
    center_azimuth_deg = ((clock_hour % 12) * 30.0 + 180.0) % 360.0 - 180.0
    return Gaze(
        center_azimuth_deg=center_azimuth_deg,
        half_width_deg=FOCUS_CONE_HALF_WIDTH_DEG,
        label=f"{clock_hour}_oclock",
    )


def gaze_at(t_sim: float, plan: ScanPlan) -> Gaze:
    """The effective `Gaze` at `t_sim` under `plan` -- a pure function of
    sim time (module docstring, hard part 1): a modulo and a table index,
    never a mutation. Free scan indexes `SCAN_PLAN` by `t_sim %
    SCAN_CYCLE_PERIOD_S`; a commanded scan indexes that sector's own
    `_SECTOR_LEGS` entry by elapsed time since `plan.command_t_sim`."""
    if plan.commanded_sector is None:
        legs = SCAN_PLAN
        elapsed_s = t_sim % SCAN_CYCLE_PERIOD_S
    else:
        assert plan.command_t_sim is not None  # ScanPlan.__post_init__
        legs = _SECTOR_LEGS[plan.commanded_sector]
        cycle_s = len(legs) * FOCUS_DWELL_S
        elapsed_s = (t_sim - plan.command_t_sim) % cycle_s
    index = min(int(elapsed_s // FOCUS_DWELL_S), len(legs) - 1)
    return _gaze_for_clock_hour(legs[index])
