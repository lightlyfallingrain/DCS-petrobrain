"""HTTP client for the aircraft-layer LAN API.

Unlike the world-model seam (`perception.geometry`, in-process import), this
is a real network call -- aircraft-layer/DCS may be a different box than
body-layer, per `plans/pb1-perception-logger/plan.md`'s framing of the two
seams. Stdlib only (`urllib.request`), consistent with `aircraft-layer/`'s
and `world-model/`'s dependency policy.

`GET /world_objects/latest` (stage 3) and `GET /petrovich_indication/latest`
(stage 4) are the endpoints `plans/pb1-perception-logger/plan.md` adds to
the aircraft layer (`aircraft-layer/src/api/server.py`) alongside the
pre-existing `GET /telemetry/latest` (`aircraft-layer/src/api/server.py`,
`aircraft-layer/src/schema`). All three return JSON `null` when the
collector's cache is still empty -- not an error, Export.lua may not have
connected or DCS may not be running a mission -- and this client passes
that through as `None` rather than raising.

`push_text_line` (BL-2.5, `plans/dcs-text-panel-output/plan.md`) is this
client's one write call, the aircraft layer's only inbound/write path
(`POST /text/push`). Unlike the `get_*` methods above, a failure here
(network error, non-200, invalid JSON) raises `AircraftLayerError` rather
than being swallowed -- this client call is between two processes that are
both expected to be reachable when body-layer runs with `--overlay`, so a
push failure is meaningful information for the caller
(`logger.ConsolePerceptionRunner`'s per-push try/except is where that
meaning gets consumed, so one failed push never stops the poll loop).

`trigger_petrovich_search`/`get_petrovich_wheel_latest` (BL-6, `plans/
bl6-commands-inspect-adapt/plan.md`) are this milestone's second
inbound/write path and its matching read. `trigger_petrovich_search`
follows `push_text_line`'s raise-on-failure posture, not the `get_*`
methods' swallow-and-return-`None` one -- per the plan's explicit
asymmetry note on `aircraft-layer/src/collector/command_sender.py`: unlike
`/text/push`'s opaque display string, a dropped search command is a real
behavioral gap the caller needs to know about, not an expected "listener
absent" state. `get_petrovich_wheel_latest` is an ordinary `get_*` read
(swallows nothing itself, `None` on an empty cache) mirroring
`get_petrovich_indication_latest`'s shape exactly, just against
`list_indication(10)`'s wheel-state feed instead of `list_indication(6)`'s
classification feed.

`get_unit_velocity_latest` (`plans/movement-detection/plan.md`) is this
seam's `GET /unit_velocity/latest` counterpart to `get_world_objects_latest`
above -- same "not an error" empty-cache posture, same `dict[str, Any]`
shallow pass-through (`aircraft-layer/src/schema/unit_velocity.py`'s
`UnitVelocitySnapshot.to_dict`). `naked_eye_source.py` is the one caller,
resolving the per-`unit_name` join against a world-objects snapshot itself
-- this client does no joining or interpretation, mirroring every other
`get_*` method here.

`get_line_of_sight_latest`/`post_look_direction` (`plans/dcs-driven-los/
plan.md`, X-B29) are this seam's `GET /line_of_sight/latest` and
`POST /command/look_direction` counterparts. `get_line_of_sight_latest`
follows `get_unit_velocity_latest`'s exact "not an error" empty-cache
posture; `naked_eye_source.py` resolves the per-`unit_name` join itself,
same split of responsibility as the velocity feed. `post_look_direction`
follows `trigger_petrovich_search`'s raise-on-failure posture, not the
`get_*` methods' swallow-and-return-`None` one -- a dropped look-direction
push is a real coverage gap (the query cone can go stale, plan SS9c), not
an opaque display string to swallow.

`get_mission_start_latest` (`plans/bl15-mission-start/plan.md`, BL-15
Stage 1) is this seam's `GET /mission_start/latest` counterpart to
`get_line_of_sight_latest` above -- same "not an error" empty-cache
posture (no `onSimulationStart` has fired yet this collector process's
lifetime, the ordinary state before a mission ever loads). `logger.py`'s
`_check_for_new_mission` is the one caller, comparing the returned
`sequence` against the last one it saw to detect a genuine mission
(re)start -- this client does no comparison or interpretation itself, same
split of responsibility as every other `get_*` method here.

`get_firing_latest` (`plans/emitter-visibility/plan.md` Stage B, `AC-B8`)
is this seam's `GET /firing/latest` counterpart to `get_line_of_sight_
latest` above, with one difference: the aircraft layer's own response is
never JSON `null` (`EmitterTracker.snapshot()`'s own docstring: there is
no "cache empty" state distinct from "nothing is firing right now"), so
this method's return type carries no `None` case for that reason -- it
still raises `AircraftLayerError` on a genuine transport/parse failure
(an aircraft-layer instance predating `AC-B8` has no such route at all,
same as every other `get_*` on an unreachable endpoint). `naked_eye_
source.py` resolves the per-`unit_name` join itself, same split of
responsibility as the velocity and LOS feeds.

`write_cockpit_switch` (`plans/9k113-effectors/plan.md`, BL-B66 Stage 1)
is this seam's write side for the generic cockpit-switch channel. It
follows `push_text_line`/`trigger_petrovich_search`'s raise-on-failure
posture, not the `get_*` methods' swallow-and-return-`None` one -- a
dropped cockpit-switch write is a real behavioral gap (a 9K113 power-up
switch silently not thrown), not an opaque display string to swallow. It
takes a raw `device`/`cmd`/`value` triple and performs **no validation
and no allow-list check** of its own -- `belief.sight_effector` is the
one module above this client that knows which device/cmd numbers mean
what; this client is a pure pass-through, same division of labour
`post_look_direction` already has for its own two already-validated
integers. **Its matching readback, `get_cockpit_switch_state_latest`, is
removed** (`plans/effector-sequences/plan.md` Stage 4, decided "remove")
-- see `get_watched_args_latest`/`read_args` below, this seam's two
replacement read paths.

`get_watched_args_latest`/`set_watch_args`/`read_args` (`plans/
effector-sequences/plan.md` Stage 4, "readback by need" option B) are
this seam's two cockpit-arg readback paths, replacing `get_cockpit_
switch_state_latest` above.

- `get_watched_args_latest` is an ordinary `get_*` read (`GET
  /watched_args/latest`, swallows nothing itself, `None` on an empty
  cache) mirroring `get_petrovich_wheel_latest`'s shape exactly -- the
  **continuous** feed, a small `polled.toml`-driven arg set `Export.lua`
  polls at its own export tick (the same cadence as the telemetry line)
  and sends only on change.
- `set_watch_args` (`POST /command/watch_args`) follows `write_cockpit_
  switch`'s raise-on-failure posture -- installing the wrong watched
  set, or failing to install one at all, is a real behavioral gap
  (`sight_ready`/`home_phase` silently never updating), not an opaque
  display string to swallow.
- `read_args` (`POST /query/read_args`) is this seam's first
  **synchronous** call -- it blocks until the aircraft layer's own
  `ArgReadBroker` round-trips a one-shot read through `Export.lua` (or
  the request times out), unlike every other method here, which either
  returns immediately from a cache or fires-and-forgets a command. Also
  raises `AircraftLayerError` on any failure (non-200, including the
  aircraft layer's own `504`/`503`), **and re-validates the response
  body before returning it** (security plan review required change 1,
  `plans/effector-sequences/security-stage4-plan.md`): every value must
  be a finite, non-bool number, every key a decimal string in 0..4095
  that is one of the args actually *requested*, and the whole map at
  most 64 entries -- the HTTP response is still a trust boundary (a
  compromised aircraft-layer/collector dependency, or a plain bug in the
  forwarding path), and a NaN must never reach `belief.effector_engine`'s
  own `_matches` (`abs(NaN - t) < g` is `False`, which would read as
  "differs" and write).

`write_sight_target` (`plans/9k113-sight-pointing/plan.md`, BL-B80) is a
third, narrower write op on the same `POST /command/*` family -- a
persistent **world** goal direction/rate Export.lua's own per-frame servo
rate-limits toward, not a one-shot `cockpit_switch` write. Same
raise-on-failure posture as `write_cockpit_switch`, same "no validation,
this client is a pure pass-through" division. **v2 (re-plan) drops the
degree<->raw conversion entirely** -- the wire carries degrees directly,
and `Export.lua`'s own servo converts internally; `belief.sight_effector.
write_sight_target` is still the one caller above this client, just a
pure pass-through now rather than a conversion site.

`get_spu8_state_latest` (`plans/effector-sequences/plan.md` D6, BL-B90
Stage 2) is this seam's `GET /spu8/state` counterpart to `get_cockpit_
switch_state_latest` -- same "not an error" empty-cache posture. Its one
caller is `CrewConsole.drain_config_error` via `logger.py`'s poll loop,
reading `gate_open` to decide whether the intercom is up before speaking
the one-shot "bad sequence file" error line (D6: *"once the intercom is
up"*).

`get_sight_servo_latest` is this seam's read side for the same feed --
`Export.lua`'s per-frame DCS-slave servo status (mode, setpoint, the
mark-derived body direction when valid, error, stall flag), a *second*
feed from `/cockpit_switch/latest` (that one is change-gated; this one
changes every frame under the per-frame value-change mechanism, a
different rate class -- see the plan's Affected Files "Departure,
stated")."""

from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal

_DEFAULT_TIMEOUT_S = 2.0


class AircraftLayerError(RuntimeError):
    """Raised when the aircraft-layer API is unreachable, times out, or
    returns a response that isn't valid JSON."""


@dataclass(frozen=True, slots=True)
class AircraftLayerClient:
    """Thin JSON GET client for one aircraft-layer instance.

    `base_url` has no trailing slash, e.g. `"http://192.168.1.50:7791"`
    (the aircraft-layer LAN API's default port, see `aircraft-layer/src/api/
    server.py`'s `DEFAULT_PORT`)."""

    base_url: str
    timeout_s: float = _DEFAULT_TIMEOUT_S

    def get_telemetry_latest(self) -> dict[str, Any] | None:
        """`GET /telemetry/latest` -> the most recent `TelemetrySample` as a
        dict (see `aircraft-layer/src/schema/__init__.py`'s
        `TelemetrySample.to_dict`), or `None` if nothing has been received
        yet."""
        result = self._get_json("/telemetry/latest")
        if result is None:
            return None
        if not isinstance(result, dict):
            raise AircraftLayerError(
                f"expected a JSON object or null from /telemetry/latest, got {type(result).__name__}"
            )
        return result

    def get_world_objects_latest(self) -> dict[str, Any] | None:
        """`GET /world_objects/latest` -> the most recent world-objects
        snapshot as a dict (see `aircraft-layer/src/schema/world_objects.py`'s
        `WorldObjectsSnapshot.to_dict`), or `None` if nothing has been
        received yet."""
        result = self._get_json("/world_objects/latest")
        if result is None:
            return None
        if not isinstance(result, dict):
            raise AircraftLayerError(
                f"expected a JSON object or null from /world_objects/latest, got {type(result).__name__}"
            )
        return result

    def get_petrovich_indication_latest(self) -> dict[str, Any] | None:
        """`GET /petrovich_indication/latest` -> the most recent HelperAI
        indication sample as a dict (see `aircraft-layer/src/schema/
        petrovich_indication.py`'s `PetrovichIndicationSample.to_dict`,
        i.e. `{"dcs_model_time_s", "received_wall_clock_s", "fields"}` where
        `fields` is the flattened `{leaf_name: text}` record), or `None` if
        nothing has been received yet."""
        result = self._get_json("/petrovich_indication/latest")
        if result is None:
            return None
        if not isinstance(result, dict):
            raise AircraftLayerError(
                f"expected a JSON object or null from /petrovich_indication/latest, got {type(result).__name__}"
            )
        return result

    def get_unit_velocity_latest(self) -> dict[str, Any] | None:
        """`GET /unit_velocity/latest` -> the most recent `UnitVelocitySnapshot`
        as a dict (see `aircraft-layer/src/schema/unit_velocity.py`'s
        `UnitVelocitySnapshot.to_dict`), or `None` if nothing has been
        received yet -- same "not an error" posture as `get_world_objects_
        latest` (`plans/movement-detection/plan.md`)."""
        result = self._get_json("/unit_velocity/latest")
        if result is None:
            return None
        if not isinstance(result, dict):
            raise AircraftLayerError(
                f"expected a JSON object or null from /unit_velocity/latest, got {type(result).__name__}"
            )
        return result

    def get_line_of_sight_latest(self) -> dict[str, Any] | None:
        """`GET /line_of_sight/latest` -> the most recent
        `LineOfSightSnapshot` as a dict (see `aircraft-layer/src/schema/
        line_of_sight.py`'s `LineOfSightSnapshot.to_dict`), or `None` if
        nothing has been received yet -- same "not an error" posture as
        `get_unit_velocity_latest` (`plans/dcs-driven-los/plan.md`)."""
        result = self._get_json("/line_of_sight/latest")
        if result is None:
            return None
        if not isinstance(result, dict):
            raise AircraftLayerError(
                f"expected a JSON object or null from /line_of_sight/latest, got {type(result).__name__}"
            )
        return result

    def get_mission_start_latest(self) -> dict[str, Any] | None:
        """`GET /mission_start/latest` -> the most recent
        `MissionStartEvent` as a dict (see `aircraft-layer/src/schema/
        mission_start.py`'s `MissionStartEvent.to_dict`, i.e.
        `{"sequence", "theatre", "received_wall_clock_s"}`), or `None` if
        no `onSimulationStart` has fired yet this collector process's
        lifetime -- same "not an error" posture as `get_line_of_sight_
        latest` (`plans/bl15-mission-start/plan.md`)."""
        result = self._get_json("/mission_start/latest")
        if result is None:
            return None
        if not isinstance(result, dict):
            raise AircraftLayerError(
                f"expected a JSON object or null from /mission_start/latest, got {type(result).__name__}"
            )
        return result

    def get_firing_latest(self) -> dict[str, Any]:
        """`GET /firing/latest` -> the most recent `EmitterTracker.
        snapshot()` as a dict (`{"dcs_model_time_s", "received_wall_
        clock_s", "active"}`, see `aircraft-layer/src/collector/
        firing_receiver.py`). Never `None` -- see the module docstring."""
        result = self._get_json("/firing/latest")
        if not isinstance(result, dict):
            raise AircraftLayerError(
                f"expected a JSON object from /firing/latest, got {type(result).__name__}"
            )
        return result

    def get_watched_args_latest(self) -> dict[str, Any] | None:
        """`GET /watched_args/latest` -> the most recent `WatchedArgsState`
        as a dict (see `aircraft-layer/src/schema/watched_args.py`'s
        `WatchedArgsState.to_api_dict`, i.e. `{"t", "received_wall_clock_s",
        "watch_id", "args"}`), or `None` if nothing has been received yet
        -- the continuous readback feed (`plans/effector-sequences/plan.md`
        Stage 4)."""
        result = self._get_json("/watched_args/latest")
        if result is None:
            return None
        if not isinstance(result, dict):
            raise AircraftLayerError(
                f"expected a JSON object or null from /watched_args/latest, got {type(result).__name__}"
            )
        return result

    def set_watch_args(self, watch_id: str, args: list[int]) -> None:
        """`POST /command/watch_args` -> installs the set of args the
        continuous feed above should watch (`plans/effector-sequences/
        plan.md` Stage 4). Raises `AircraftLayerError` on any failure,
        mirroring `write_cockpit_switch` -- see the module docstring for
        why."""
        self._post_json(
            "/command/watch_args",
            {"watch_id": watch_id, "args": args},
        )

    def read_args(self, args: list[int]) -> dict[str, float]:
        """`POST /query/read_args` -> a synchronous one-shot read of
        `args` (`plans/effector-sequences/plan.md` Stage 4, S4.2). Blocks
        until the aircraft layer's own `ArgReadBroker` round-trips the
        read through `Export.lua`, or raises `AircraftLayerError` on any
        failure (non-200, including the aircraft layer's own `504` on a
        timeout or `503` when the channel is unconfigured/busy) -- see
        the module docstring for why this call, unlike every `get_*`
        method above, both raises on failure *and* re-validates its own
        response body before returning it."""
        result = self._post_json("/query/read_args", {"args": args})
        if not isinstance(result, dict):
            raise AircraftLayerError(
                f"expected a JSON object from /query/read_args, got {type(result).__name__}"
            )
        raw_values = result.get("values")
        if not isinstance(raw_values, dict) or len(raw_values) > 64:
            raise AircraftLayerError(
                f"'values' must be an object of at most 64 entries, got {raw_values!r}"
            )
        requested = set(args)
        validated: dict[str, float] = {}
        for key, raw in raw_values.items():
            if (
                not isinstance(key, str)
                or not re.fullmatch(r"\d{1,4}", key)
                or int(key) > 4095
                or int(key) not in requested
            ):
                raise AircraftLayerError(f"bad or unrequested arg key {key!r}")
            if (
                isinstance(raw, bool)
                or not isinstance(raw, (int, float))
                or not math.isfinite(raw)
            ):
                raise AircraftLayerError(
                    f"value for arg {key} must be a finite number, got {raw!r}"
                )
            validated[key] = float(raw)
        return validated

    def get_spu8_state_latest(self) -> dict[str, Any] | None:
        """`GET /spu8/state` -> the most recent SPU-8 intercom-panel
        reading as a dict (see `aircraft-layer/src/schema/spu8.py`'s
        `Spu8Sample.to_api_dict`, i.e. `{"t", "received_wall_clock_s",
        "net1", "ics_power", "vol", "net1_on", "ics_power_on",
        "gate_open"}`), or `None` if nothing has been received yet --
        same "not an error" posture as `get_watched_args_latest`
        (`plans/effector-sequences/plan.md` D6)."""
        result = self._get_json("/spu8/state")
        if result is None:
            return None
        if not isinstance(result, dict):
            raise AircraftLayerError(
                f"expected a JSON object or null from /spu8/state, got {type(result).__name__}"
            )
        return result

    def write_cockpit_switch(self, device: int, cmd: int, value: float) -> None:
        """`POST /command/cockpit_switch` -> writes any clickable cockpit
        control (`aircraft-layer/src/collector/command_sender.py`'s
        `CommandSender.send_cockpit_switch`, BL-B66 Stage 1). Raises
        `AircraftLayerError` on any failure, mirroring `push_text_line`/
        `trigger_petrovich_search` -- see the module docstring for why."""
        self._post_json(
            "/command/cockpit_switch",
            {"device": device, "cmd": cmd, "value": value},
        )

    def write_sight_target(
        self,
        goal_az_deg: float,
        goal_el_deg: float,
        goal_rate_az_deg_s: float,
        goal_rate_el_deg_s: float,
        t_sim: float,
    ) -> None:
        """`POST /command/sight_target` -> sends the simulated sight
        head's current world goal direction, rate, and the sim time it
        was computed at, to `Export.lua`'s per-frame servo
        (`aircraft-layer/src/collector/command_sender.py`'s
        `CommandSender.send_sight_target`, `plans/9k113-sight-pointing/
        plan.md`, BL-B80 v2). Raises `AircraftLayerError` on any failure,
        mirroring `write_cockpit_switch` -- see the module docstring for
        why."""
        self._post_json(
            "/command/sight_target",
            {
                "goal_az_deg": goal_az_deg,
                "goal_el_deg": goal_el_deg,
                "goal_rate_az_deg_s": goal_rate_az_deg_s,
                "goal_rate_el_deg_s": goal_rate_el_deg_s,
                "t_sim": t_sim,
            },
        )

    def get_sight_servo_latest(self) -> dict[str, Any] | None:
        """`GET /sight_servo/latest` -> the most recent DCS-slave servo
        status (see `aircraft-layer/src/schema/sight_servo.py`'s
        `SightServoState.to_api_dict`), or `None` if nothing has been
        received yet -- same "not an error" posture as `get_cockpit_
        switch_state_latest` (`plans/9k113-sight-pointing/plan.md`,
        BL-B80 v2)."""
        result = self._get_json("/sight_servo/latest")
        if result is None:
            return None
        if not isinstance(result, dict):
            raise AircraftLayerError(
                f"expected a JSON object or null from /sight_servo/latest, got {type(result).__name__}"
            )
        return result

    def post_look_direction(self, hour: int, fov_half_deg: int) -> None:
        """`POST /command/look_direction` -> pushes the currently-commanded
        look-direction wedge (`aircraft-layer/src/collector/command_sender.
        LookDirectionSender`, `plans/dcs-driven-los/plan.md` SS9). Raises
        `AircraftLayerError` on any failure -- see the module docstring for
        why this call, unlike the `get_*` methods above, does not swallow
        failure."""
        self._post_json(
            "/command/look_direction",
            {"hour": hour, "fov_half_deg": fov_half_deg},
        )

    def push_text_line(self, text: str) -> None:
        """`POST /text/push` -> pushes one line to the in-cockpit overlay
        (`aircraft-layer/src/collector/text_sender.py`, BL-2.5). Raises
        `AircraftLayerError` on any failure -- see the module docstring for
        why this call, unlike the `get_*` methods above, does not swallow
        failure."""
        self._post_json("/text/push", {"text": text})

    def get_petrovich_wheel_latest(self) -> dict[str, Any] | None:
        """`GET /petrovich_wheel/latest` -> the most recent
        `list_indication(10)` (Petrovich's AI-Wheel state) sample as a dict
        (see `aircraft-layer/src/schema/petrovich_wheel.py`'s
        `PetrovichWheelSample.to_dict`, the same
        `{dcs_model_time_s, received_wall_clock_s, fields}` shape as
        `get_petrovich_indication_latest`), or `None` if nothing has been
        received yet."""
        result = self._get_json("/petrovich_wheel/latest")
        if result is None:
            return None
        if not isinstance(result, dict):
            raise AircraftLayerError(
                f"expected a JSON object or null from /petrovich_wheel/latest, got {type(result).__name__}"
            )
        return result

    def trigger_petrovich_search(self, mode: Literal["forward", "boresight"]) -> None:
        """`POST /command/petrovich_search` -> drives Petrovich's AI Wheel
        to start a search (`aircraft-layer/src/collector/command_sender.py`,
        BL-6): `"forward"` for `SRCH FWD` (long press), `"boresight"` for
        `SRCH BRST` (short press). Raises `AircraftLayerError` on any
        failure, mirroring `push_text_line` -- **not** the `get_*` methods'
        swallow-and-return-`None` posture, since a dropped search command is
        a real behavioral gap the caller needs to know about (see the
        module docstring)."""
        self._post_json("/command/petrovich_search", {"mode": mode})

    def _get_json(self, path: str) -> Any:
        url = f"{self.base_url}{path}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout_s) as response:
                body = response.read()
        except (urllib.error.URLError, OSError) as exc:
            raise AircraftLayerError(f"request to {url} failed: {exc}") from exc
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise AircraftLayerError(f"invalid JSON from {url}: {exc}") from exc

    def _post_json(self, path: str, body: dict[str, Any]) -> Any:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                response_body = response.read()
        except (urllib.error.URLError, OSError) as exc:
            raise AircraftLayerError(f"request to {url} failed: {exc}") from exc
        if not response_body:
            return None
        try:
            return json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise AircraftLayerError(f"invalid JSON from {url}: {exc}") from exc
