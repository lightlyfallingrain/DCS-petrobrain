"""HTTP client for the aircraft-layer LAN API.

Unlike the world-model seam (`perception.geometry`, in-process import), this
is a real network call -- aircraft-layer/DCS may be a different box than
body-layer, per `plans/pb1-perception-logger/plan.md`'s framing of the two
seams. Stdlib only (`urllib.request`), consistent with `aircraft-layer/`'s
and `world-model/`'s dependency policy.

`GET /world_objects/latest` is the endpoint `plans/pb1-perception-logger/
plan.md` stage 3 adds to the aircraft layer (`aircraft-layer/src/api/
server.py`) alongside the pre-existing `GET /telemetry/latest`
(`aircraft-layer/src/api/server.py`, `aircraft-layer/src/schema`). Both
return JSON `null` when the collector's cache is still empty -- not an
error, Export.lua may not have connected or DCS may not be running a
mission -- and this client passes that through as `None` rather than
raising.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

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
