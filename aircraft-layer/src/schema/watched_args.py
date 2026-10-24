"""The generic cockpit-arg readback channel -- `plans/effector-sequences/
plan.md` Stage 4, both its "readback by need" revision (option B) and the
still-valid mechanism from the first, superseded spec it carries over
(S4.4/section 4.2-4.5).

**Replaces `schema.cockpit_switch.CockpitSwitchState` outright** (decided,
explore-notes "Stage 4 decisions, 2026-10-24", item 6: "remove"). That
feed's nine fixed args leave `Export.lua`'s per-frame work entirely; this
module covers the two read paths that take over:

- **Continuous** (`WatchedArgsState`, this class): a small, config-driven
  set of args `Export.lua` polls at its existing 5 Hz export tick and sends
  only on change, wire key `"watch_id"`. `body-layer/src/belief/
  effector_registry.load_polled_config` + `sight_effector.
  REQUIRED_POLLED_ARGS` decide the set; this schema only carries whatever
  set body-layer last asked for.
- **One-shot** (`parse_arg_values`, the shared validator below): a
  synchronous `POST /query/read_args` round trip through the collector's
  `ArgReadBroker`, answered by `Export.lua`'s `handle_read_args_command` on
  the same frame it arrives. There is no dataclass for a one-shot reply --
  the broker returns `(t, values)` directly (`collector.arg_read_broker.
  ArgReadResult`) -- but the reply's `"values"` map is validated by the
  exact same rules as `WatchedArgsState.from_dict`'s `"watched"` map, so
  `parse_arg_values` is factored out once and called by both: this
  module's own `from_dict` and `collector.arg_read_broker.ArgReadBroker`'s
  `"read_id"` line parser (security plan review, `plans/effector-sequences/
  security-stage4-plan.md`, required change 1 -- the same finiteness/type
  guard the continuous feed already had was missing from the one-shot
  path, and is now shared rather than duplicated).

**Raw values, body-layer decides.** `Export.lua` used to threshold
898/960/962 to booleans before sending; it now sends every watched/read arg
raw (`%.3f`), same precedent as the PTT feed (`schema.ptt.PttSample`) --
`belief.sight_effector.refresh_readback` applies the `>= 0.5` threshold on
the body-layer side now, where it can be tested without a redeploy."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any

#: The shared per-op bound, both read paths, both ends of the wire
#: (`Export.lua`'s own `MAX_WATCHED_ARGS`/`MAX_WATCHED_ARG_NUMBER`,
#: `api.server`'s POST validators, and this module) -- stated once per
#: side rather than imported across the Lua/Python boundary, held equal
#: by `tests/test_export_lua_constants_parity.py`.
MAX_WATCHED_ARGS = 64
MAX_WATCHED_ARG_NUMBER = 4095

_ARG_KEY_RE = re.compile(r"^\d{1,4}$")


class WatchedArgsParseError(ValueError):
    """Raised when a watched-args state line, or a `"values"`/`"watched"`
    map on either read path, is missing fields or has the wrong types."""


def parse_arg_values(raw: Any) -> dict[int, float]:
    """The one shared validator for an arg->value map arriving over the
    wire, on **either** read path (continuous `"watched"` or one-shot
    `"values"`) -- security plan review required change 1.

    `raw` must be a JSON object; at most `MAX_WATCHED_ARGS` keys; every key
    a decimal string in `0..MAX_WATCHED_ARG_NUMBER` (`^\\d{1,4}$`, so no
    sign, no leading `+`, matching what `Export.lua`'s own `parse_arg_list`
    accepts as an arg token); every value a finite, non-bool number
    (`math.isfinite` -- a NaN must never reach a caller's own `_matches`,
    where `abs(NaN - t) < g` is `False`, reading as "differs" and writing).
    Raises `WatchedArgsParseError` on any violation; never coerces or
    drops a bad entry silently, since a dropped key on this specific map
    would narrow the caller's model of "what Export.lua just reported",
    not merely omit noise."""
    if not isinstance(raw, dict):
        raise WatchedArgsParseError(f"expected an object, got {type(raw).__name__}")
    if len(raw) > MAX_WATCHED_ARGS:
        raise WatchedArgsParseError(
            f"at most {MAX_WATCHED_ARGS} keys allowed, got {len(raw)}"
        )
    values: dict[int, float] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not _ARG_KEY_RE.fullmatch(key):
            raise WatchedArgsParseError(f"bad arg key {key!r}")
        arg = int(key)
        if arg > MAX_WATCHED_ARG_NUMBER:
            raise WatchedArgsParseError(f"arg {arg} exceeds {MAX_WATCHED_ARG_NUMBER}")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise WatchedArgsParseError(
                f"value for arg {arg} must be a finite number, got {value!r}"
            )
        values[arg] = float(value)
    return values


@dataclass(frozen=True, slots=True)
class WatchedArgsState:
    """One reading of the continuous watched-args feed, with the dual-clock
    provenance every sample in this layer carries. `watch_id` is the
    content-derived id (`belief.effector_registry`/`effector_engine.
    watch_id_for`, body-layer side) the set was installed under -- a stale
    `watch_id` (one that does not match what body-layer currently wants
    installed) means `values` must be treated as unknown by the caller,
    never read against the wrong set (`collector.cache.WatchedArgsCache`'s
    own clear-on-`export_version` handles the restart case; the id mismatch
    itself is `body.py`'s own poll-block check, not this schema's job)."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    watch_id: str
    values: dict[int, float]

    @staticmethod
    def from_dict(
        data: dict[str, Any], *, received_wall_clock_s: float
    ) -> WatchedArgsState:
        if "t" not in data:
            raise WatchedArgsParseError("missing required field(s): ['t']")
        model_time = data["t"]
        if isinstance(model_time, bool) or not isinstance(model_time, (int, float)):
            raise WatchedArgsParseError(
                f"field 't' must be a number, got {type(model_time).__name__}"
            )

        watch_id = data.get("watch_id")
        if not isinstance(watch_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_]{1,16}", watch_id
        ):
            raise WatchedArgsParseError(
                f"field 'watch_id' must be a 1-16 char [A-Za-z0-9_] string, "
                f"got {watch_id!r}"
            )

        watched = data.get("watched")
        values = parse_arg_values(watched)

        return WatchedArgsState(
            dcs_model_time_s=float(model_time),
            received_wall_clock_s=received_wall_clock_s,
            watch_id=watch_id,
            values=values,
        )

    @staticmethod
    def from_json_line(line: str, *, received_wall_clock_s: float) -> WatchedArgsState:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WatchedArgsParseError(f"line is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise WatchedArgsParseError("line is not a JSON object")
        return WatchedArgsState.from_dict(
            data, received_wall_clock_s=received_wall_clock_s
        )

    def to_api_dict(self) -> dict[str, Any]:
        """What `GET /watched_args/latest` answers with. `"args"` matches
        Stage 2's own `{"<arg>": <raw>}` shape (`schema.cockpit_switch.
        CockpitSwitchState.to_api_dict`'s precedent) so `belief.
        effector_engine.observed_value`/`advance` do not have to change
        their readback-map shape to consume this feed instead."""
        return {
            "t": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "watch_id": self.watch_id,
            "args": {str(arg): value for arg, value in self.values.items()},
        }
