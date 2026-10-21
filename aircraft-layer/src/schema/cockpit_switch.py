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

        return CockpitSwitchState(
            dcs_model_time_s=float(model_time),
            received_wall_clock_s=received_wall_clock_s,
            missl_pw=values["missl_pw"],
            cplr_distr=values["cplr_distr"],
            sight_pw=values["sight_pw"],
            scho_pw=values["scho_pw"],
            observe=values["observe"],
            weap_safe=values["weap_safe"],
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
        shape as `Spu8Sample.to_api_dict`."""
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
        }
