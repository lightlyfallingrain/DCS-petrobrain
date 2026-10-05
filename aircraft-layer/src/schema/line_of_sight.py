"""DCS-driven line-of-sight wire format -- `plans/dcs-driven-los/plan.md`
(X-B29).

`petrobrain-line-of-sight-hook.lua` polls, once a second, the same
`net.dostring_in("scripting", ...)` bridge `petrobrain-mission-telemetry-
hook.lua` already uses for unit velocity -- but unlike that feed, this one
is **cone-scoped** (plan Second Revision, SS8-SS10): the snippet only
computes a sightline for a unit inside the currently-commanded look-
direction wedge (`PB_LOOK_HOUR`/`PB_LOOK_FOV_DEG`, set by the inbound
look-direction command channel, see `collector.command_sender.
LookDirectionSender`), not for every unit in the player bubble.

Wire format (Hook -> collector), one JSON datagram per poll (matches
`petrobrain-mission-telemetry-hook.lua`'s own envelope shape):

    {"payload": "<compact string below>", "bridge_call_ms": <float>}

The compact string packs everything `dostring_in` can return across the
Hook/mission-scripting boundary (one scalar) into one delimited string,
mirroring `unit_velocity.py`'s own packing:

    "<units_in_bubble>|<units_in_wedge>|<sightlines_computed>|<hour_used>|"
    "<fov_half_deg_used>|<dcs_model_time_s>|<entries>"

`entries` is `"<unit_name>:<building_clear01>:<terrain_clear01>;..."`,
semicolon-separated, `01` meaning a literal `0`/`1` (never a bare Lua
boolean, which has no stable string form across a `dostring_in` round
trip). Empty population still returns a well-formed string (entries empty).

`units_in_bubble`/`units_in_wedge`/`sightlines_computed` are the plan's
own observability triad (SS1/SS10/SS12): `units_in_wedge` turns the plan's
uniform-azimuth cone-population *estimates* into a measurement, and
`sightlines_computed < units_in_wedge` would mean the `MAX_SIGHTLINES_PER_
CALL` guard (a blow-up backstop, not a policy -- plan SS10) actually bit.
`hour_used`/`fov_half_deg_used` are the wedge the snippet actually queried
with this poll, independent of whatever body-layer most recently pushed --
see `annotate_los`'s own docstring (`perception/detection_trace.py`) for why
this is recorded per poll rather than assumed to track the push.

`building_clear`/`terrain_clear` are two independently-computed, separately
published fields (`world.searchObjects`/`SEGMENT` and `land.isVisible`
respectively, plan "REVISION (2026-09-29)") -- never pre-ANDed on the wire,
so a misbehaviour after both are live stays attributable to one half. The
join on the body-layer side (`naked_eye_source._resolve_los_by_unit_name`)
is what combines them into one `live_los_clear` verdict.

`samples` is keyed by `unit_name`, the same join key `unit_velocity.py`
already established for the sibling feed (`LoGetWorldObjects`'s own
`UnitName`) -- `LoGetWorldObjects` and the mission-scripting environment
share no other identifier. A duplicate `unit_name` within one poll is
resolved last-entry-wins at this parsing step, the same documented,
accepted limitation `unit_velocity.py`'s own `from_wire` carries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class LineOfSightParseError(ValueError):
    """Raised when a line-of-sight wire payload does not match the
    expected shape."""


@dataclass(frozen=True, slots=True)
class LineOfSightVerdict:
    """One unit's building/terrain LOS verdict for one poll. Two
    independently-computed fields, never pre-combined -- see the module
    docstring's "never pre-ANDed on the wire" note."""

    unit_name: str
    building_clear: bool
    terrain_clear: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "building_clear": self.building_clear,
            "terrain_clear": self.terrain_clear,
        }


@dataclass(frozen=True, slots=True)
class LineOfSightSnapshot:
    """All line-of-sight verdicts from one mission-scripting poll, plus
    that poll's dual-clock timestamps, the cone actually queried with
    (`hour_used`/`fov_half_deg_used`), and the observability triad
    (`units_in_bubble`/`units_in_wedge`/`sightlines_computed`) -- mirrors
    `UnitVelocitySnapshot`'s provenance shape."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    hour_used: int
    fov_half_deg_used: int
    units_in_bubble: int
    units_in_wedge: int
    sightlines_computed: int
    bridge_call_ms: float
    verdicts: dict[str, LineOfSightVerdict]

    @staticmethod
    def from_wire(
        payload: str, *, bridge_call_ms: float, received_wall_clock_s: float
    ) -> LineOfSightSnapshot:
        """Parse one compact wire string (module docstring) into a typed
        snapshot. `entries` may be empty (nothing in the queried wedge this
        poll)."""
        parts = payload.split("|", 6)
        if len(parts) != 7:
            raise LineOfSightParseError(
                "expected '<units_in_bubble>|<units_in_wedge>|"
                "<sightlines_computed>|<hour_used>|<fov_half_deg_used>|"
                f"<t>|<entries>', got {payload!r}"
            )
        (
            units_in_bubble_str,
            units_in_wedge_str,
            sightlines_computed_str,
            hour_used_str,
            fov_half_deg_used_str,
            t_str,
            entries_str,
        ) = parts

        units_in_bubble = _parse_int(units_in_bubble_str, "units_in_bubble")
        units_in_wedge = _parse_int(units_in_wedge_str, "units_in_wedge")
        sightlines_computed = _parse_int(sightlines_computed_str, "sightlines_computed")
        hour_used = _parse_int(hour_used_str, "hour_used")
        fov_half_deg_used = _parse_int(fov_half_deg_used_str, "fov_half_deg_used")
        try:
            dcs_model_time_s = float(t_str)
        except ValueError as exc:
            raise LineOfSightParseError(
                f"field 'dcs_model_time_s' must be a number, got {t_str!r}"
            ) from exc

        verdicts: dict[str, LineOfSightVerdict] = {}
        for entry in entries_str.split(";"):
            if not entry:
                continue
            verdict = _parse_entry(entry)
            verdicts[verdict.unit_name] = verdict

        return LineOfSightSnapshot(
            dcs_model_time_s=dcs_model_time_s,
            received_wall_clock_s=received_wall_clock_s,
            hour_used=hour_used,
            fov_half_deg_used=fov_half_deg_used,
            units_in_bubble=units_in_bubble,
            units_in_wedge=units_in_wedge,
            sightlines_computed=sightlines_computed,
            bridge_call_ms=bridge_call_ms,
            verdicts=verdicts,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dcs_model_time_s": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "hour_used": self.hour_used,
            "fov_half_deg_used": self.fov_half_deg_used,
            "units_in_bubble": self.units_in_bubble,
            "units_in_wedge": self.units_in_wedge,
            "sightlines_computed": self.sightlines_computed,
            "bridge_call_ms": self.bridge_call_ms,
            "verdicts": {
                name: verdict.to_dict() for name, verdict in self.verdicts.items()
            },
        }


def _parse_int(raw: str, field: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise LineOfSightParseError(
            f"field {field!r} must be an integer, got {raw!r}"
        ) from exc


def _parse_entry(entry: str) -> LineOfSightVerdict:
    # rsplit, not split: a unit_name is not expected to contain a colon, but
    # DCS mission-editor names are free text -- same defensive posture
    # `unit_velocity.py`'s own `_parse_entry` takes toward untrusted
    # Hook-side strings.
    fields = entry.rsplit(":", 2)
    if len(fields) != 3:
        raise LineOfSightParseError(
            f"expected '<unit_name>:<building_clear01>:<terrain_clear01>', "
            f"got {entry!r}"
        )
    unit_name, building_str, terrain_str = fields
    if not unit_name:
        raise LineOfSightParseError(f"empty unit_name in entry {entry!r}")
    building_clear = _parse_bool01(building_str, entry)
    terrain_clear = _parse_bool01(terrain_str, entry)
    return LineOfSightVerdict(
        unit_name=unit_name,
        building_clear=building_clear,
        terrain_clear=terrain_clear,
    )


def _parse_bool01(raw: str, entry: str) -> bool:
    if raw == "1":
        return True
    if raw == "0":
        return False
    raise LineOfSightParseError(
        f"expected a literal '0' or '1' clear flag, got {raw!r} in entry {entry!r}"
    )
