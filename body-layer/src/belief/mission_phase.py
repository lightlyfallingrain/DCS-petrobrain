"""Live mission-phase sequencing -- `plans/bl7-mission-phase-relevance/
plan.md`. Consumes MI-6's `--emit-compact` JSON artifact
(`mission-interpreter/src/runtime/compact.py`'s `RuntimeMissionUnderstanding`,
written via `dataclasses.asdict`) as a plain file read + JSON parse, never a
Python import of mission-interpreter's own code -- mission-interpreter is
not the world-model exception root `CLAUDE.md`'s "Module independence"
section carves out, so the subproject boundary here is the same
HTTP/JSON-or-file-read discipline every other cross-subproject seam in this
codebase uses.

This module hand-parses the compact artifact's two fields BL-7 needs
(`phases`, `route`) rather than importing `schema.tags.Tagged`/
`schema.understanding.MissionPhase`/`runtime.compact.CompactRoutePoint` --
`CompactRoutePoint`/`MissionPhaseInfo` below are small local mirrors of
those shapes, each still carrying `epistemic_status`/`basis` alongside the
value (root `CLAUDE.md`: "preserve provenance... on every feature derived
from mixing DCS + external sources"), not collapsed to a bare value.
`key_locations` is deliberately not parsed here -- `CompactLocation` (that
artifact's shape) carries no position field, so relevance can only be
scored against route waypoints this milestone (see the plan's Risks
section).

`MissionPhaseTracker` is the live state engine: it walks ownship position
against the loaded route's waypoints and reports which mission phase is
currently active. **Monotonic** -- `last_reached_waypoint_index` never
decrements, even if ownship temporarily regresses past a waypoint's capture
radius (e.g. a turn that briefly increases range to the last-reached
waypoint). `update()` checks every not-yet-reached waypoint each poll, not
just the immediate next one, so a poll gap that jumps past an intermediate
waypoint (a coarse poll interval, or DCS itself skipping the aircraft ahead
in a replay) still advances the tracker past it rather than stalling on a
waypoint ownship never gets within radius of again.

`WAYPOINT_CAPTURE_RADIUS_M` is a guessed placeholder pending live-flight
calibration -- same debt class as `perception.visibility`'s already-flagged,
still-uncalibrated tier constants (see that module's own docstring). Do not
treat the value below as validated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from perception.geometry import GeoPosition, range_m

#: Capture radius (metres) within which ownship is considered to have
#: reached a route waypoint. Placeholder pending live-flight calibration --
#: do not treat as validated (see module docstring).
WAYPOINT_CAPTURE_RADIUS_M: Final[float] = 3000.0


@dataclass(frozen=True, slots=True)
class CompactRoutePoint:
    """Local mirror of `runtime.compact.CompactRoutePoint`'s value shape,
    plus the `Tagged` envelope's `epistemic_status`/`basis` -- `x`/`y` are
    DCS-native planar coordinates (`x` = northing, `z`/`y` = easting per
    `world-model/research/2026-09-02-m1-coordinate-transform.md`), mapping
    directly onto `perception.geometry.GeoPosition(x=x, z=y, ...)`, the same
    convention every other body-layer position already uses."""

    index: int
    x: float
    y: float
    place_name: str | None
    epistemic_status: str
    basis: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MissionPhaseInfo:
    """Local mirror of `schema.understanding.MissionPhase`'s value shape,
    plus the `Tagged` envelope's `epistemic_status`/`basis`."""

    name: str
    waypoint_index: int
    epistemic_status: str
    basis: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MissionUnderstandingData:
    """Immutable, loaded once by `load_mission_understanding`. `phases` is
    defensively re-sorted ascending by `waypoint_index` even though MI-3/
    MI-6 already guarantee that order -- cheap, and this is the one place a
    violated upstream guarantee would silently break phase sequencing."""

    phases: tuple[MissionPhaseInfo, ...]
    route: tuple[CompactRoutePoint, ...]


def _require_list(raw: object, key: str) -> list[object]:
    if not isinstance(raw, dict):
        raise ValueError("mission understanding artifact root is not a JSON object")  # noqa: TRY004
    value = raw.get(key)
    if not isinstance(value, list):
        raise ValueError(f"mission understanding artifact missing '{key}' list")  # noqa: TRY004
    return value


def _unwrap_tagged(
    item: object, field_name: str
) -> tuple[dict[str, object], str, tuple[str, ...]]:
    """Unwraps one `Tagged`-shaped JSON object (`{value, epistemic_status,
    basis, confidence}`) -- `confidence` is not read, BL-7 has no use for
    it. Raises `ValueError` with a clear message on any missing/malformed
    field, per this module's "fail loudly at startup" posture (this is a
    one-time load, not a per-poll hot path)."""
    if not isinstance(item, dict):
        raise ValueError(f"{field_name} entry is not a Tagged-shaped object: {item!r}")  # noqa: TRY004
    value = item.get("value")
    epistemic_status = item.get("epistemic_status")
    basis = item.get("basis")
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} entry has no 'value' object: {item!r}")  # noqa: TRY004
    if not isinstance(epistemic_status, str):
        raise ValueError(f"{field_name} entry missing 'epistemic_status': {item!r}")  # noqa: TRY004
    if not isinstance(basis, list) or not all(isinstance(b, str) for b in basis):
        raise ValueError(f"{field_name} entry has malformed 'basis': {item!r}")
    return value, epistemic_status, tuple(basis)


def _parse_phase(item: object) -> MissionPhaseInfo:
    value, epistemic_status, basis = _unwrap_tagged(item, "phases")
    name = value.get("name")
    waypoint_index = value.get("waypoint_index")
    if not isinstance(name, str) or not isinstance(waypoint_index, int):
        raise ValueError(f"malformed phase value: {value!r}")  # noqa: TRY004
    return MissionPhaseInfo(
        name=name,
        waypoint_index=waypoint_index,
        epistemic_status=epistemic_status,
        basis=basis,
    )


def _parse_route_point(item: object) -> CompactRoutePoint:
    value, epistemic_status, basis = _unwrap_tagged(item, "route")
    index = value.get("index")
    x = value.get("x")
    y = value.get("y")
    place_name = value.get("place_name")
    if (
        not isinstance(index, int)
        or not isinstance(x, (int, float))
        or not isinstance(y, (int, float))
    ):
        raise ValueError(f"malformed route point value: {value!r}")  # noqa: TRY004
    if place_name is not None and not isinstance(place_name, str):
        raise ValueError(f"malformed route point place_name: {value!r}")
    return CompactRoutePoint(
        index=index,
        x=float(x),
        y=float(y),
        place_name=place_name,
        epistemic_status=epistemic_status,
        basis=basis,
    )


def load_mission_understanding(path: Path) -> MissionUnderstandingData:
    """Reads MI-6's `--emit-compact` JSON output, unwraps each `Tagged`
    envelope, and builds `MissionUnderstandingData`. Raises a plain
    `ValueError` with a clear message on any missing/malformed field --
    this is a one-time startup load, not a per-poll hot path, so failing
    loudly here (rather than degrading silently) is the right posture,
    mirroring `aircraft_client`'s raise-on-write-failure precedent.

    Empty `phases`/`route` lists are valid (not an error) -- they degrade
    to `MissionPhaseTracker.current_phase() is None` rather than raising;
    only a missing or malformed field is treated as a schema violation.
    """
    raw = json.loads(path.read_text())
    phases = tuple(
        sorted(
            (_parse_phase(item) for item in _require_list(raw, "phases")),
            key=lambda phase: phase.waypoint_index,
        )
    )
    route = tuple(_parse_route_point(item) for item in _require_list(raw, "route"))
    return MissionUnderstandingData(phases=phases, route=route)


def _route_point_distance_m(position: GeoPosition, point: CompactRoutePoint) -> float:
    """Straight-line distance from `position` to `point`, via `perception.
    geometry.range_m` -- coordinate math stays in the dedicated coordinate
    subsystem, never reimplemented inline here. `point` carries no altitude
    (MI-6's compact artifact doesn't have one), so the target is placed at
    `position`'s own altitude, collapsing the vertical component -- adequate
    for a capture-radius/relevance check, not a claim of true slant range."""
    target = GeoPosition(x=point.x, z=point.y, alt_m=position.alt_m)
    return range_m(position, target)


@dataclass
class MissionPhaseTracker:
    """The live state engine, one instance per session. `data` is the
    immutable loaded artifact; `last_reached_waypoint_index` starts at -1
    ("before" the route) and only ever advances (see `update`'s docstring)."""

    data: MissionUnderstandingData
    last_reached_waypoint_index: int = -1

    def update(self, position: GeoPosition) -> None:
        """Advance `last_reached_waypoint_index` to the highest route-point
        index within `WAYPOINT_CAPTURE_RADIUS_M` of `position`, among every
        not-yet-reached point (not just the immediate next one) -- so a poll
        gap that jumps past an intermediate waypoint still advances past it.
        **Never decrements**: the result is always `>=` the current value,
        even if no not-yet-reached point is currently in range."""
        candidate = self.last_reached_waypoint_index
        for point in self.data.route:
            if point.index <= self.last_reached_waypoint_index:
                continue
            if _route_point_distance_m(position, point) <= WAYPOINT_CAPTURE_RADIUS_M:
                candidate = max(candidate, point.index)
        self.last_reached_waypoint_index = candidate

    def current_phase(self) -> MissionPhaseInfo | None:
        """The last phase (by `waypoint_index`) whose `waypoint_index <=
        last_reached_waypoint_index`, or `None` if the route hasn't reached
        the first phase's waypoint yet (or no phases were loaded)."""
        eligible = [
            phase
            for phase in self.data.phases
            if phase.waypoint_index <= self.last_reached_waypoint_index
        ]
        if not eligible:
            return None
        return max(eligible, key=lambda phase: phase.waypoint_index)


def mission_phase_relevance(
    position: GeoPosition,
    phase: MissionPhaseInfo | None,
    route: tuple[CompactRoutePoint, ...],
) -> float | None:
    """Distance in metres from `position` to the active `phase`'s waypoint,
    or `None` if there is no active phase or that waypoint index isn't in
    `route`. Smaller means more relevant. Deliberately a plain distance, not
    a normalized 0..1 score -- nothing downstream needs normalization yet."""
    if phase is None:
        return None
    for point in route:
        if point.index == phase.waypoint_index:
            return _route_point_distance_m(position, point)
    return None
