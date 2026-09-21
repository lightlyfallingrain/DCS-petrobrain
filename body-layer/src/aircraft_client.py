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

`get_f10_commands` (`plans/f10-crew-commands/plan.md`) is this seam's
first *inbound* read -- `GET /f10_commands/poll` drains the aircraft
layer's F10-command queue, so unlike every other `get_*` method here, its
empty state is `[]`, not `None` (the response is always a JSON list, never
`null`). It still raises `AircraftLayerError` on transport/parse failure,
the same posture as every other `get_*` -- only the *empty* state differs
from the `/latest`-style endpoints.
"""

from __future__ import annotations

import json
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

    def get_f10_commands(self) -> list[dict[str, Any]]:
        """`GET /f10_commands/poll` -> drains the aircraft layer's F10
        radio-menu command queue (`aircraft-layer/src/collector/
        f10_command_receiver.py`, `plans/f10-crew-commands/plan.md`),
        returning every pending selection as a list of dicts (see
        `aircraft-layer/src/schema/f10_command.py`'s `F10CommandEvent.
        to_dict`, i.e. `{"command", "received_wall_clock_s"}`), oldest
        first. Returns `[]` when nothing is pending -- see the module
        docstring for why this is `[]`, not `None`, unlike the `get_*`
        methods above. Raises `AircraftLayerError` on any transport/parse
        failure, same as every other `get_*` method."""
        result = self._get_json("/f10_commands/poll")
        if not isinstance(result, list):
            raise AircraftLayerError(
                f"expected a JSON list from /f10_commands/poll, got {type(result).__name__}"
            )
        return result

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
