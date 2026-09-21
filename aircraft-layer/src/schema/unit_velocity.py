"""Unit-velocity wire format -- `plans/movement-detection/plan.md` Stage 1.

`petrobrain-mission-telemetry-hook.lua` polls `Object.getVelocity()` for
every unit and static object, once a second, via `net.dostring_in(
"scripting", ...)` -- the same bridge `petrobrain-f10-commands-hook.lua` has
polled at 1 Hz since 2026-09-13 (`aircraft-layer/research/
2026-09-22-mission-bridge-already-shipping.md`). `dostring_in` can only
return one simple scalar across the Hook/mission-scripting boundary (the
same constraint `petrobrain-f10-commands-hook.lua`'s own `POLL_CODE` works
around), so the mission-scripting snippet packs everything into one compact
string:

    "<unit_count>|<dcs_model_time_s>|<unit_name>:<vx>:<vy>:<vz>;<unit_name>:<vx>:<vy>:<vz>;..."

`unit_count` is the snippet's own count, first field, per `plans/
movement-detection/plan.md` Stage 0 part 2's self-measurement design.
`dcs_model_time_s` is stamped **inside the scripting state** via
`timer.getTime()`, never in the Hook via `DCS.getRealTime()` -- the plan's
sharpest replay-determinism risk (see that plan's "Risks & Unknowns"). Empty
population still returns a well-formed string (`"0|<t>|"`, entries empty).

The Hook script wraps that string plus its own `os.clock()`-measured
`bridge_call_ms` (the per-call bridge cost -- unmeasurable from the Mac side,
Stage 0 part 2) into one JSON UDP datagram to
`collector.unit_velocity_receiver.UnitVelocityReceiver`:

    {"payload": "<compact string above>", "bridge_call_ms": <float>}

`UnitVelocitySnapshot.from_wire` is the only supported way to turn that pair
into the typed record the rest of the pipeline works with -- mirrors
`world_objects.WorldObjectsSnapshot.from_dict`'s role for that sibling feed.

Velocity components are DCS-native x/y/z, metres/second -- `y` is the
vertical axis (DCS convention, same as every other DCS vector this project
handles), `x`/`z` the north-like/east-like horizontal axes. Passed through
unconverted; unit conversion (if any) is `perception.motion`'s job on the
consuming side, not this schema's.

`samples` is keyed by `unit_name` -- the join key `plans/movement-detection/
plan.md` Decision 1 settles on, since `LoGetWorldObjects` and the
mission-scripting environment share no other identifier. Built from the wire
string's semicolon-separated entries; **a duplicate `unit_name` within one
poll is resolved last-entry-wins at this parsing step** (a `dict` has no
other way to hold two values under one key) -- this is a different, cheaper
concern from the "non-unique `UnitName`" collision the plan's Risks section
flags for `perception.association`'s join: that one is about two
*world-object* candidates sharing a name and needing both dropped to `None`,
which requires the candidate pool this module never sees. A duplicate
purely within the velocity feed itself (two Mission-Scripting units sharing
a name) is a rarer, DCS-mission-authoring-level oddity, not something this
schema can raise past without breaking `from_wire`'s single-pass parse."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class UnitVelocityParseError(ValueError):
    """Raised when a unit-velocity wire payload does not match the expected
    shape."""


@dataclass(frozen=True, slots=True)
class UnitVelocitySample:
    """One unit's velocity vector for one poll, DCS-native m/s."""

    unit_name: str
    vx: float
    vy: float
    vz: float

    def to_dict(self) -> dict[str, Any]:
        return {"vx": self.vx, "vy": self.vy, "vz": self.vz}


@dataclass(frozen=True, slots=True)
class UnitVelocitySnapshot:
    """All unit velocities from one mission-scripting poll, plus that poll's
    dual-clock timestamps -- mirrors `WorldObjectsSnapshot`'s provenance
    shape -- and the Stage 0 part 2 self-measurement diagnostics
    (`unit_count`, `bridge_call_ms`)."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    unit_count: int
    bridge_call_ms: float
    samples: dict[str, UnitVelocitySample]

    @staticmethod
    def from_wire(
        payload: str, *, bridge_call_ms: float, received_wall_clock_s: float
    ) -> UnitVelocitySnapshot:
        """Parse one `"<unit_count>|<dcs_model_time_s>|<entries>"` compact
        string (module docstring) into a typed snapshot. `entries` may be
        empty (no units this poll)."""
        parts = payload.split("|", 2)
        if len(parts) != 3:
            raise UnitVelocityParseError(
                f"expected '<count>|<t>|<entries>', got {payload!r}"
            )
        count_str, t_str, entries_str = parts
        try:
            unit_count = int(count_str)
        except ValueError as exc:
            raise UnitVelocityParseError(
                f"field 'unit_count' must be an integer, got {count_str!r}"
            ) from exc
        try:
            dcs_model_time_s = float(t_str)
        except ValueError as exc:
            raise UnitVelocityParseError(
                f"field 'dcs_model_time_s' must be a number, got {t_str!r}"
            ) from exc

        samples: dict[str, UnitVelocitySample] = {}
        for entry in entries_str.split(";"):
            if not entry:
                continue
            sample = _parse_entry(entry)
            samples[sample.unit_name] = sample

        return UnitVelocitySnapshot(
            dcs_model_time_s=dcs_model_time_s,
            received_wall_clock_s=received_wall_clock_s,
            unit_count=unit_count,
            bridge_call_ms=bridge_call_ms,
            samples=samples,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dcs_model_time_s": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "unit_count": self.unit_count,
            "bridge_call_ms": self.bridge_call_ms,
            "samples": {
                name: sample.to_dict() for name, sample in self.samples.items()
            },
        }


def _parse_entry(entry: str) -> UnitVelocitySample:
    # rsplit rather than split: a unit_name is not expected to contain a
    # colon, but DCS mission-editor names are free text and this keeps a
    # stray colon in the name from misaligning the three trailing numeric
    # fields -- the same defensive posture `f10_command_receiver.py` takes
    # toward untrusted Hook-side strings.
    fields = entry.rsplit(":", 3)
    if len(fields) != 4:
        raise UnitVelocityParseError(
            f"expected '<unit_name>:<vx>:<vy>:<vz>', got {entry!r}"
        )
    unit_name, vx_str, vy_str, vz_str = fields
    if not unit_name:
        raise UnitVelocityParseError(f"empty unit_name in entry {entry!r}")
    try:
        vx, vy, vz = float(vx_str), float(vy_str), float(vz_str)
    except ValueError as exc:
        raise UnitVelocityParseError(
            f"velocity components must be numbers, got {entry!r}"
        ) from exc
    return UnitVelocitySample(unit_name=unit_name, vx=vx, vy=vy, vz=vz)
