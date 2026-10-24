"""`SightHead` -- Petrovich's **simulated** 9K113 sight (`[[BL-B80]]`,
`plans/9k113-sight-pointing/plan.md`, re-plan v2). Gyro world-stabilised,
gimbal-limited, slew-rate-limited -- this **is** his sight for perception;
the real DCS sight is a best-effort slave of it (`Export.lua`'s
`run_sight_servo`, outside this process entirely).

**One construction site besides the runner's `default_factory`**, the
same `MissionMemory.append` precedent `plan.md`'s "Co-moving Fields" names
-- `advance_sight_head` is the only function that builds a new `SightHead`
other than the zero-argument default. Frozen and replaced, never mutated,
same replay-determinism reasoning `OpticState` already follows.

**`select_sight_goal` is `seen_world_direction`'s one caller** (fence F3,
`test_sight_head.py`) -- the "Aim source" rule from the plan: while
Petrovich has the target resolved in the sight, the sight aims at the
target's own true direction (through the already-sanctioned ownship-
relative channel), not at belief's imprecise world location."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Literal

import tuning
from belief.attack_run import SeenDirection, seen_world_direction
from belief.contacts import Contact
from perception.geometry import (
    GeoPosition,
    body_relative_direction,
    world_direction_from_body,
)
from perception.optics import SIGHT_WIDE_OPTIC
from perception.source import OwnshipState

#: The simulated head's per-axis slew rate -- the same figures `Export.
#: lua`'s own per-frame setpoint rate limit mirrors by hand (no tuning
#: mechanism outside body-layer), sourced from `Devices_specs/9K113.lua`
#: (`h_axis_velocity`/`v_axis_velocity`, confirmed live per `mi24p-
#: command-surface.md` §4.2). A different value changes how fast
#: Petrovich's simulated sight can slew onto a newly chosen look, so this
#: is tunable (root `CLAUDE.md`'s "Behaviour-affecting constants are
#: tunable").
SLEW_AZ_DPS: float = tuning.real(
    "belief.sight_head.SLEW_AZ_DPS",
    20.0,
    lo=5.0,
    hi=40.0,
    status="derived",
)
#: How fast Petrovich's simulated sight can slew in elevation, in degrees
#: per second -- the 9K113's own vertical rate, half the azimuth figure,
#: from the same source as `SLEW_AZ_DPS`; a higher value has him settle
#: on a new look sooner than the real sight can.
SLEW_EL_DPS: float = tuning.real(
    "belief.sight_head.SLEW_EL_DPS",
    10.0,
    lo=2.0,
    hi=20.0,
    status="derived",
)

#: How long the sight keeps tracking the last *seen* direction after the
#: target drops out of the glass (left the FOV, LOS blocked, a binocular/
#: unaided poll, hands busy) before falling back to belief's own desired
#: direction -- the plan's "Aim source" selection rule, `held` row. A
#: different value changes how long Petrovich keeps the mark on a
#: momentarily-obscured target before it jumps back to belief's coarser
#: estimate, so this is tunable. Not yet flown -- an agreed guess pending
#: Flight B's masking rows.
SEEN_AIM_HOLD_S: float = tuning.real(
    "belief.sight_head.SEEN_AIM_HOLD_S",
    3.0,
    lo=0.0,
    hi=10.0,
    status="agreed-guess",
)

#: Gimbal limits are **not** new constants here -- read from `SIGHT_WIDE_
#: OPTIC.regard_*` (one source of truth, the plan's own Affected Files
#: note), not re-declared.
_GIMBAL_AZ_HALF_DEG = SIGHT_WIDE_OPTIC.regard_azimuth_half_deg
_GIMBAL_EL_UP_DEG = SIGHT_WIDE_OPTIC.regard_elevation_up_deg
_GIMBAL_EL_DOWN_DEG = SIGHT_WIDE_OPTIC.regard_elevation_down_deg
assert _GIMBAL_AZ_HALF_DEG is not None
assert _GIMBAL_EL_UP_DEG is not None
assert _GIMBAL_EL_DOWN_DEG is not None

SightHeadMode = Literal["off", "caged", "free"]
AimSource = Literal["seen", "held", "belief"]


@dataclass(frozen=True, slots=True)
class SightHead:
    """The simulated head's own state, carried across polls by the
    runner. See the plan's "Design detail" section for the full
    transition table (`off`/`caged`/`free`, the 886/898 lamps).

    `world_az_true_deg`/`world_el_deg` are the head's **current** body
    direction expressed in the world frame -- `None` unless `mode is
    "free"`. `goal_world_*`/`goal_rate_*` are what was last sent to
    `Export.lua`'s `sight_target` op (the wire's own goal/rate pair).

    *Seen aim* fields (`aim_source`, `seen_contact_id`, `last_seen_*`) are
    `select_sight_goal`'s own bookkeeping -- see the plan's "Aim source"
    Co-moving Fields rows."""

    mode: SightHeadMode = "off"
    world_az_true_deg: float | None = None
    world_el_deg: float | None = None
    goal_world_az_deg: float | None = None
    goal_world_el_deg: float | None = None
    goal_rate_az_deg_s: float = 0.0
    goal_rate_el_deg_s: float = 0.0

    aim_source: AimSource = "belief"
    seen_contact_id: str | None = None
    last_seen_goal_az_deg: float | None = None
    last_seen_goal_el_deg: float | None = None
    last_seen_rate_az_deg_s: float = 0.0
    last_seen_rate_el_deg_s: float = 0.0
    last_seen_t_look: float | None = None


def _clamp_gimbal(az_deg: float, el_deg: float) -> tuple[float, float]:
    """Clamps a body-relative direction into the sight's field of regard
    -- "a held direction that leaves the gimbal envelope is dragged at the
    stop, as the real head is" (plan's "Simulated head" paragraph)."""
    assert _GIMBAL_AZ_HALF_DEG is not None
    assert _GIMBAL_EL_UP_DEG is not None
    assert _GIMBAL_EL_DOWN_DEG is not None
    clamped_az = max(-_GIMBAL_AZ_HALF_DEG, min(_GIMBAL_AZ_HALF_DEG, az_deg))
    clamped_el = max(_GIMBAL_EL_DOWN_DEG, min(_GIMBAL_EL_UP_DEG, el_deg))
    return clamped_az, clamped_el


def _step_toward(
    current_deg: float, goal_deg: float, rate_dps: float, dt_s: float
) -> float:
    """Moves `current_deg` toward `goal_deg` by at most `rate_dps * dt_s`,
    landing exactly on `goal_deg` within one step of it -- the Python twin
    of `Export.lua`'s `sight_rate_limit_step`
    (`test_sight_servo_lua.py` pins the two against each other)."""
    delta = goal_deg - current_deg
    max_step = rate_dps * max(dt_s, 0.0)
    if delta > max_step:
        return current_deg + max_step
    if delta < -max_step:
        return current_deg - max_step
    return goal_deg


def _world_to_body(
    world_az_deg: float, world_el_deg: float, ownship: OwnshipState
) -> tuple[float, float]:
    """World-true `(az, el)` -> body-relative `(az, el)` at `ownship`'s
    current attitude -- a unit-range target built directly from the
    world direction, handed to `body_relative_direction`. Shared by the
    gimbal clamp inside `advance_sight_head` and `head_body_direction`
    below, so the same conversion is not written twice."""
    az_rad = math.radians(world_az_deg)
    el_rad = math.radians(world_el_deg)
    target = GeoPosition(
        x=math.cos(el_rad) * math.cos(az_rad),
        z=math.cos(el_rad) * math.sin(az_rad),
        alt_m=math.sin(el_rad),
    )
    direction = body_relative_direction(
        GeoPosition(x=0.0, z=0.0, alt_m=0.0),
        target,
        heading_true_deg=ownship.heading_true_deg,
        pitch_deg=ownship.pitch_deg,
        bank_deg=ownship.bank_deg,
    )
    return direction.azimuth_deg, direction.elevation_deg


def head_body_direction(
    head: SightHead, ownship: OwnshipState
) -> tuple[float, float] | None:
    """The head's current direction, converted to body-relative at
    `ownship`'s attitude -- `None` unless `head.mode == "free"`. The one
    place `body._apply_active_gaze` (perception's actual gaze) and
    `sight_trace_writer` read the head's position as a body direction;
    everywhere else the head's own state stays in the world frame it is
    actually held in."""
    if (
        head.mode != "free"
        or head.world_az_true_deg is None
        or head.world_el_deg is None
    ):
        return None
    return _world_to_body(head.world_az_true_deg, head.world_el_deg, ownship)


def select_sight_goal(
    head: SightHead,
    *,
    look_contact: Contact | None,
    desired_world_az_deg: float | None,
    desired_world_rate_az_deg_s: float,
    desired_world_el_deg: float | None,
    desired_world_rate_el_deg_s: float,
    last_sight_look_sim: float | None,
    now_sim: float,
) -> tuple[AimSource, float, float, float, float, str | None, float | None]:
    """The plan's "Aim source" selection rule, per poll. `look_contact` is
    the contact belief's `decide_optic` chose to look at this poll (`None`
    when idle/searching); `desired_world_*` is belief's own desired world
    direction/rate for that choice (today's design, used for the
    `belief` row and as `held`'s own fallback when nothing was ever seen).

    Returns `(aim_source, goal_az_deg, goal_el_deg, rate_az_deg_s,
    rate_el_deg_s, seen_contact_id, last_seen_t_look)` -- the caller
    (`advance_sight_head`) folds these into the next `SightHead`.

    **`seen_world_direction` is called here, and only here**, under
    `belief/` (fence F2/F3, `test_sight_head.py`) -- the plan's "no new
    exception module" preference: this is the second consumer of the
    already-sanctioned ownship-relative perception channel, reached
    through `attack_run.py`'s existing fenced reader."""
    seen: SeenDirection | None = None
    if look_contact is not None:
        seen = seen_world_direction(look_contact)

    # `seen` row: the look must be *through the sight*, i.e. the contact's
    # last percept was admitted on the latest sight-tier poll
    # (`last_sight_look_sim`) -- a binocular/unaided look also produces an
    # equally exact seen direction, and must not steer the sight.
    if (
        seen is not None
        and last_sight_look_sim is not None
        and seen.t_look == last_sight_look_sim
    ):
        assert look_contact is not None  # `seen` is only set when it is
        rate_az = 0.0
        rate_el = 0.0
        if (
            head.aim_source == "seen"
            and head.seen_contact_id == look_contact.id
            and head.last_seen_t_look is not None
            and head.last_seen_t_look != seen.t_look
            and head.last_seen_t_look > 0.0
        ):
            dt_look = seen.t_look - head.last_seen_t_look
            if dt_look > 0.0 and head.last_seen_goal_az_deg is not None:
                rate_az = (seen.az_true_deg - head.last_seen_goal_az_deg) / dt_look
            if dt_look > 0.0 and head.last_seen_goal_el_deg is not None:
                rate_el = (seen.el_deg - head.last_seen_goal_el_deg) / dt_look
        return (
            "seen",
            seen.az_true_deg,
            seen.el_deg,
            rate_az,
            rate_el,
            look_contact.id,
            seen.t_look,
        )

    # `held` row: was `seen`, now isn't, but the hold window has not
    # expired -- keep tracking the last seen goal/rate unchanged. "Not
    # refreshed from belief" (plan): `last_seen_*` fields pass through as
    # they were.
    if (
        head.aim_source in ("seen", "held")
        and head.last_seen_t_look is not None
        and head.last_seen_goal_az_deg is not None
        and head.last_seen_goal_el_deg is not None
        and now_sim - head.last_seen_t_look <= SEEN_AIM_HOLD_S
        and (look_contact is None or head.seen_contact_id == look_contact.id)
    ):
        return (
            "held",
            head.last_seen_goal_az_deg,
            head.last_seen_goal_el_deg,
            head.last_seen_rate_az_deg_s,
            head.last_seen_rate_el_deg_s,
            head.seen_contact_id,
            head.last_seen_t_look,
        )

    # `belief` row: no look, the look contact changed, the hold expired,
    # or never seen -- today's design. `seen_contact_id`/`last_seen_*` are
    # cleared, per the plan's Co-moving Fields table ("a re-alignment
    # never resumes an old seen track").
    return (
        "belief",
        desired_world_az_deg if desired_world_az_deg is not None else 0.0,
        desired_world_el_deg if desired_world_el_deg is not None else 0.0,
        desired_world_rate_az_deg_s,
        desired_world_rate_el_deg_s,
        None,
        None,
    )


def advance_sight_head(
    head: SightHead,
    *,
    ownship: OwnshipState,
    dt_s: float,
    align_observed: bool,
    observ_observed: bool,
    look_contact: Contact | None,
    desired_body_az_deg: float | None,
    desired_body_el_deg: float | None,
    desired_world_rate_az_deg_s: float = 0.0,
    desired_world_rate_el_deg_s: float = 0.0,
    last_sight_look_sim: float | None = None,
) -> SightHead:
    """Advances the simulated head one poll -- the plan's "Simulated
    head" design-detail paragraph, mode-by-mode:

    - `886` off (`observ_observed` false): `off`. Every direction/goal/
      rate `None`/zero; nothing sent.
    - `886` on, `898` (Л5 gyro alignment) not yet lit (`align_observed`
      false): `caged`. Body direction `(0, 0)`; no world direction, no
      `sight_target` sent.
    - `898` lit: `free`. Converges toward `select_sight_goal`'s chosen
      goal at `SLEW_AZ_DPS`/`SLEW_EL_DPS`, gimbal-clamped. Entering `free`
      from `caged` seeds the world direction at that poll's boresight
      (body `(0, 0)` converted to world at the current attitude).

    `desired_body_az_deg`/`desired_body_el_deg` is belief's own desired
    look (`OpticState.look_azimuth_deg`/`look_elevation_deg`), body-
    relative, or `None` when nothing sight-tier is desired this poll (a
    glance away, binocular, capped) -- in that case the head holds its
    own current direction rather than snapping back (plan: "it holds, it
    does not snap back")."""
    if not observ_observed:
        return SightHead()

    if not align_observed:
        return replace(
            head,
            mode="caged",
            world_az_true_deg=None,
            world_el_deg=None,
        )

    # `caged` -> `free`: seed world direction at boresight, this poll's
    # attitude.
    if head.mode != "free" or head.world_az_true_deg is None:
        current_world_az, current_world_el = world_direction_from_body(
            0.0,
            0.0,
            heading_true_deg=ownship.heading_true_deg,
            pitch_deg=ownship.pitch_deg,
            bank_deg=ownship.bank_deg,
        )
    else:
        current_world_az, current_world_el = (
            head.world_az_true_deg,
            head.world_el_deg if head.world_el_deg is not None else 0.0,
        )

    desired_world_az_deg: float | None = None
    desired_world_rate_az = desired_world_rate_az_deg_s
    desired_world_rate_el = desired_world_rate_el_deg_s
    if desired_body_az_deg is not None and desired_body_el_deg is not None:
        desired_world_az_deg, desired_world_el_deg = world_direction_from_body(
            desired_body_az_deg,
            desired_body_el_deg,
            heading_true_deg=ownship.heading_true_deg,
            pitch_deg=ownship.pitch_deg,
            bank_deg=ownship.bank_deg,
        )
    else:
        desired_world_el_deg = None

    (
        aim_source,
        goal_az_deg,
        goal_el_deg,
        rate_az_deg_s,
        rate_el_deg_s,
        seen_contact_id,
        last_seen_t_look,
    ) = select_sight_goal(
        head,
        look_contact=look_contact,
        desired_world_az_deg=desired_world_az_deg,
        desired_world_rate_az_deg_s=desired_world_rate_az,
        desired_world_el_deg=desired_world_el_deg,
        desired_world_rate_el_deg_s=desired_world_rate_el,
        last_sight_look_sim=last_sight_look_sim,
        now_sim=ownship.t_sim,
    )

    if (
        desired_body_az_deg is None
        and desired_body_el_deg is None
        and aim_source == "belief"
    ):
        # Nothing sight-tier desired this poll and no seen/held track --
        # hold the head's own current direction rather than snapping to a
        # fabricated "belief" goal of (0, 0).
        goal_az_deg, goal_el_deg = current_world_az, current_world_el
        rate_az_deg_s, rate_el_deg_s = 0.0, 0.0

    new_world_az = _step_toward(current_world_az, goal_az_deg, SLEW_AZ_DPS, dt_s)
    new_world_el = _step_toward(current_world_el, goal_el_deg, SLEW_EL_DPS, dt_s)

    # Clamp to gimbal at the *current* attitude -- convert world -> body,
    # clamp, convert back. A held direction that leaves the envelope is
    # dragged at the stop.
    body_now_az, body_now_el = _world_to_body(new_world_az, new_world_el, ownship)
    clamped_body_az, clamped_body_el = _clamp_gimbal(body_now_az, body_now_el)
    final_world_az, final_world_el = world_direction_from_body(
        clamped_body_az,
        clamped_body_el,
        heading_true_deg=ownship.heading_true_deg,
        pitch_deg=ownship.pitch_deg,
        bank_deg=ownship.bank_deg,
    )

    # `last_seen_*` fields: updated on `seen`, held unchanged on `held`
    # (`select_sight_goal` already returned the unchanged `seen_contact_
    # id`/`last_seen_t_look` for that row), cleared on `belief` -- the
    # plan's Co-moving Fields table, "a re-alignment never resumes an old
    # seen track".
    last_seen_goal_az: float | None
    last_seen_goal_el: float | None
    if aim_source == "seen":
        last_seen_goal_az = goal_az_deg
        last_seen_goal_el = goal_el_deg
        last_seen_rate_az = rate_az_deg_s
        last_seen_rate_el = rate_el_deg_s
    elif aim_source == "held":
        last_seen_goal_az = head.last_seen_goal_az_deg
        last_seen_goal_el = head.last_seen_goal_el_deg
        last_seen_rate_az = head.last_seen_rate_az_deg_s
        last_seen_rate_el = head.last_seen_rate_el_deg_s
    else:  # "belief"
        last_seen_goal_az = None
        last_seen_goal_el = None
        last_seen_rate_az = 0.0
        last_seen_rate_el = 0.0

    return replace(
        head,
        mode="free",
        world_az_true_deg=final_world_az,
        world_el_deg=final_world_el,
        goal_world_az_deg=goal_az_deg,
        goal_world_el_deg=goal_el_deg,
        goal_rate_az_deg_s=rate_az_deg_s,
        goal_rate_el_deg_s=rate_el_deg_s,
        aim_source=aim_source,
        seen_contact_id=seen_contact_id,
        last_seen_goal_az_deg=last_seen_goal_az,
        last_seen_goal_el_deg=last_seen_goal_el,
        last_seen_rate_az_deg_s=last_seen_rate_az,
        last_seen_rate_el_deg_s=last_seen_rate_el,
        last_seen_t_look=last_seen_t_look,
    )
