"""The 9K113 guidance-unit power-up / OBSERV / weapon-safety-bar switches,
as read from the cockpit (`plans/9k113-effectors/plan.md`, BL-B66 Stage 1).

Six args, read every frame, sent only on change (same cadence/throttle
shape as `schema.spu8.Spu8Sample` -- see `Export.lua`'s
`push_cockpit_switch_state`):

- arg 773 (`missl_pw`) -- MISSILE POWER.
- arg 761 (`cplr_distr`) -- CPLR DISTR. **Unverified** -- see
  `Export.lua`'s own comment on this arg for why.
- arg 885 (`sight_pw`) -- Sight Power (GUID.UNIT POWER).
- arg 955 (`scho_pw`) -- SHCHO PWR B1.
- arg 886 (`observe`) -- OBSERV. (NABL).
- arg 673 (`weap_safe`) -- the weapons safety switches bar. `1` is ARMED,
  `0` is SAFE (`body-layer/research/2026-10-14-9k113-warmup-atgm-
  procedure.md` Finding 6: "ON arms the circuit, OFF safes it").

**This layer carries the raw values and decides nothing**, the same rule
every other schema here follows: all six animate through intermediate
values for ~0.1s on a flip (confirmed live,
`aircraft-layer/research/2026-10-17-9k113-effector-and-slew-probe-
findings.md` finding 3), so a reader must threshold rather than test
equality.

**Two more, optional (BL-B66 Stage 4b, `EXPORT_SCRIPT_VERSION` "...21b")**:

- arg 874 (`sight_az`) -- the sight head's actual azimuth position
  readback, raw.
- arg 876 (`sight_elev`) -- the sight head's actual elevation position
  readback, raw. Its degrees-per-unit is unmeasured (piecewise gauge) --
  this layer never converts it, raw only.

`float | None`, defaulting to `None` when absent, **not** required like
the six switch args above: a deployed `Export.lua` older than Stage 4b
never sends them at all, and that must parse exactly as "no reading yet",
the same absence the rest of this layer already treats as "no sample"
rather than a parse error. **`[[BL-B80]]` v2 (`EXPORT_SCRIPT_VERSION`
"...22c") stops sending both** (they echo the AI-axis demand, not a
position, confirmed by probe runs 1-10) -- the fields stay here, so an
older `Export.lua` and a newer collector still agree on the shape, but
every v2 sample carries `None` for both.

**Three more, optional lamps, `[[BL-B80]]` v2**: arg 898 (`align_lamp`,
Л5 gyro alignment), arg 960 (`ready_lamp`, guidance-unit READY), arg 962
(`launch_perm_lamp`, launch permission) -- real booleans this time (the
underlying arg is thresholded in `Export.lua` itself, unlike the six
switch args' raw-plus-decided split), `bool | None`, same "absent means
no reading yet" contract as `sight_az`/`sight_elev`.

**`to_api_dict`'s `"args"` map (`plans/effector-sequences/plan.md` R7,
BL-B90 Stage 2)**: `{"773": <raw missl_pw>, "761": <raw cplr_distr>,
"885": <raw sight_pw>, "955": <raw scho_pw>, "886": <raw observe>,
"673": <raw weap_safe>}` -- the same six raw values already on this
class, re-keyed by their DCS arg number as a string, so body-layer's
effector engine can look a curated registry entry's own `arg` number up
generically instead of this schema hard-coding six named fields for it
to read. Purely a derived view of data this class already carries --
nothing new is read from `Export.lua`, and the six named fields/
properties above are unchanged for every existing reader.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

#: Threshold for all six switch args. `>=`, never equality -- see the
#: module docstring; same reasoning/value as `schema.spu8._SWITCH_ON_
#: THRESHOLD`.
_SWITCH_ON_THRESHOLD = 0.5


class CockpitSwitchParseError(ValueError):
    """Raised when a cockpit-switch state line is missing fields or has
    the wrong types."""


@dataclass(frozen=True, slots=True)
class CockpitSwitchState:
    """One reading of args 773/761/885/955/886/673, with the dual-clock
    provenance every sample in this layer carries."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    missl_pw: float
    cplr_distr: float
    sight_pw: float
    scho_pw: float
    observe: float
    weap_safe: float
    #: Raw args 874/876 -- see the module docstring's "Two more, optional"
    #: section. `None` when the sending `Export.lua` predates Stage 4b, or
    #: (`[[BL-B80]]` v2) always, since the field stopped being sent.
    sight_az: float | None = None
    sight_elev: float | None = None
    #: The three real lamps -- see the module docstring's "Three more,
    #: optional lamps" section. `None` when the sending `Export.lua`
    #: predates `[[BL-B80]]` v2.
    align_lamp: bool | None = None
    ready_lamp: bool | None = None
    launch_perm_lamp: bool | None = None

    @property
    def missl_pw_on(self) -> bool:
        """MISSILE POWER is ON."""
        return self.missl_pw >= _SWITCH_ON_THRESHOLD

    @property
    def cplr_distr_on(self) -> bool:
        """CPLR DISTR is ON. **Unverified arg** -- see this module's
        docstring."""
        return self.cplr_distr >= _SWITCH_ON_THRESHOLD

    @property
    def sight_pw_on(self) -> bool:
        """Sight Power (GUID.UNIT POWER) is ON."""
        return self.sight_pw >= _SWITCH_ON_THRESHOLD

    @property
    def scho_pw_on(self) -> bool:
        """SHCHO PWR B1 is ON."""
        return self.scho_pw >= _SWITCH_ON_THRESHOLD

    @property
    def observe_on(self) -> bool:
        """OBSERV. is ON."""
        return self.observe >= _SWITCH_ON_THRESHOLD

    @property
    def weapons_armed(self) -> bool:
        """The weapons safety switches bar reads ARMED (not SAFE)."""
        return self.weap_safe >= _SWITCH_ON_THRESHOLD

    @staticmethod
    def from_dict(
        data: dict[str, Any], *, received_wall_clock_s: float
    ) -> CockpitSwitchState:
        if "t" not in data:
            raise CockpitSwitchParseError("missing required field(s): ['t']")
        model_time = data["t"]
        if isinstance(model_time, bool) or not isinstance(model_time, (int, float)):
            raise CockpitSwitchParseError(
                f"field 't' must be a number, got {type(model_time).__name__}"
            )

        values: dict[str, float] = {}
        for field in (
            "missl_pw",
            "cplr_distr",
            "sight_pw",
            "scho_pw",
            "observe",
            "weap_safe",
        ):
            raw = data.get(field)
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise CockpitSwitchParseError(
                    f"field {field!r} must be a number, got {type(raw).__name__}"
                )
            values[field] = float(raw)

        # Optional (Stage 4b): present-and-numeric is parsed; absent is
        # `None`, never a parse error -- see the module docstring's "Two
        # more, optional" section. A present-but-wrong-typed value *is*
        # still an error, same as any required field above: a value that
        # arrived malformed is not the same fact as one that never arrived.
        optional_values: dict[str, float | None] = {}
        for field in ("sight_az", "sight_elev"):
            raw = data.get(field)
            if raw is None:
                optional_values[field] = None
            elif isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise CockpitSwitchParseError(
                    f"field {field!r} must be a number, got {type(raw).__name__}"
                )
            else:
                optional_values[field] = float(raw)

        # Optional lamps (`[[BL-B80]]` v2) -- same "absent is None, wrong
        # type is an error" contract, but boolean-shaped.
        optional_lamps: dict[str, bool | None] = {}
        for field in ("align_lamp", "ready_lamp", "launch_perm_lamp"):
            raw = data.get(field)
            if raw is None:
                optional_lamps[field] = None
            elif not isinstance(raw, bool):
                raise CockpitSwitchParseError(
                    f"field {field!r} must be a boolean, got {type(raw).__name__}"
                )
            else:
                optional_lamps[field] = raw

        return CockpitSwitchState(
            dcs_model_time_s=float(model_time),
            received_wall_clock_s=received_wall_clock_s,
            missl_pw=values["missl_pw"],
            cplr_distr=values["cplr_distr"],
            sight_pw=values["sight_pw"],
            scho_pw=values["scho_pw"],
            observe=values["observe"],
            weap_safe=values["weap_safe"],
            sight_az=optional_values["sight_az"],
            sight_elev=optional_values["sight_elev"],
            align_lamp=optional_lamps["align_lamp"],
            ready_lamp=optional_lamps["ready_lamp"],
            launch_perm_lamp=optional_lamps["launch_perm_lamp"],
        )

    @staticmethod
    def from_json_line(
        line: str, *, received_wall_clock_s: float
    ) -> CockpitSwitchState:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CockpitSwitchParseError(f"line is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise CockpitSwitchParseError("line is not a JSON object")
        return CockpitSwitchState.from_dict(
            data, received_wall_clock_s=received_wall_clock_s
        )

    def to_api_dict(self) -> dict[str, Any]:
        """What `GET /cockpit_switch/latest` answers with. The six raw
        values and the six decided booleans -- same "raw plus decided"
        shape as `Spu8Sample.to_api_dict` -- plus `sight_az`/`sight_elev`
        (`None` always, as of `[[BL-B80]]` v2), the three real lamps
        (`align_lamp`/`ready_lamp`/`launch_perm_lamp`, `None` when the
        sending `Export.lua` predates v2), and `"args"` (the same six raw
        values re-keyed by DCS arg number -- see the module docstring's
        own `"args"` section)."""
        return {
            "t": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "missl_pw": self.missl_pw,
            "cplr_distr": self.cplr_distr,
            "sight_pw": self.sight_pw,
            "scho_pw": self.scho_pw,
            "observe": self.observe,
            "weap_safe": self.weap_safe,
            "missl_pw_on": self.missl_pw_on,
            "cplr_distr_on": self.cplr_distr_on,
            "sight_pw_on": self.sight_pw_on,
            "scho_pw_on": self.scho_pw_on,
            "observe_on": self.observe_on,
            "weapons_armed": self.weapons_armed,
            "sight_az": self.sight_az,
            "sight_elev": self.sight_elev,
            "align_lamp": self.align_lamp,
            "ready_lamp": self.ready_lamp,
            "launch_perm_lamp": self.launch_perm_lamp,
            "args": {
                "773": self.missl_pw,
                "761": self.cplr_distr,
                "885": self.sight_pw,
                "955": self.scho_pw,
                "886": self.observe,
                "673": self.weap_safe,
            },
        }
