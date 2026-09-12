"""HTTP client for world-model's new read-only API
(`world-model/src/api/server.py`, MI-2 -- `plans/mi2-world-enrichment/
plan.md`).

This is mission-interpreter's first real HTTP seam to another subproject,
mirroring `body-layer/src/aircraft_client.py`'s shape (stdlib
`urllib.request` only, a frozen/slots dataclass wrapping `base_url`/
`timeout_s`, one `get_*` method per endpoint, a `_get_json(path)` helper).

**Unlike `aircraft_client.py`, every method here raises on failure -- there
is no "not built yet" expected-empty state.** `aircraft_client.py`'s
`get_*` methods return `None` on an empty cache because Export.lua may
genuinely not have connected yet; that is a real, expected runtime state.
Once mission-interpreter's MI-2 stage runs, a world-model query failure
(network error, non-200, malformed JSON, or a shape that isn't what the
route promises) is always a real gap -- world-model's store either has the
theatre built or it does not, and if this client is being called at all,
the caller expects an answer. So every method raises
`WorldModelClientError` rather than swallowing to `None`.

Response bodies are returned as raw `dict[str, Any]`/`list[dict[str,
Any]]` rather than re-declared mirror dataclasses of world-model's
`PositionDescription`/`PlaceMatch` -- this avoids a second, hand-maintained
copy of world-model's schema on this side of the HTTP boundary that could
silently drift from the real one (mirrors `aircraft_client.py`'s own
`dict[str, Any]` return convention for exactly this reason).

`theatre` is a constructor field (matching the server's own one-theatre
binding, see `api.server`'s module docstring) so every call site doesn't
have to pass it per-call.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

_DEFAULT_TIMEOUT_S = 5.0


class WorldModelClientError(RuntimeError):
    """Raised when the world-model API is unreachable, times out, returns a
    non-2xx status, or returns a response that isn't valid JSON of the
    expected shape."""


@dataclass(frozen=True, slots=True)
class WorldModelClient:
    """Thin JSON GET client for one world-model API instance, bound to one
    `theatre` (matching the server's own one-theatre-per-process binding,
    see `api.server`'s module docstring for why a mismatched `theatre`
    would otherwise produce a silently-wrong-projection result).

    `base_url` has no trailing slash, e.g. `"http://127.0.0.1:7792"` (the
    world-model API's default port, see `world-model/src/api/server.py`'s
    `DEFAULT_PORT`)."""

    base_url: str
    theatre: str
    timeout_s: float = _DEFAULT_TIMEOUT_S

    def get_describe_position(self, x: float, z: float) -> dict[str, Any]:
        """`GET /describe_position?x=<x>&z=<z>&theatre=<theatre>` -> the
        raw `PositionDescription` JSON (see `world-model/src/query/
        describe.py`)."""
        query = urllib.parse.urlencode({"x": x, "z": z, "theatre": self.theatre})
        result = self._get_json(f"/describe_position?{query}")
        if not isinstance(result, dict):
            raise WorldModelClientError(
                f"expected a JSON object from /describe_position, got "
                f"{type(result).__name__}"
            )
        return result

    def get_find_place_by_name(
        self, text: str, kinds: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """`GET /find_place_by_name?text=<text>[&kinds=<comma-separated>]`
        -> a list of raw `PlaceMatch` JSON objects (see `world-model/src/
        query/search.py`)."""
        params: dict[str, str] = {"text": text}
        if kinds is not None:
            params["kinds"] = ",".join(kinds)
        query = urllib.parse.urlencode(params)
        result = self._get_json(f"/find_place_by_name?{query}")
        if not isinstance(result, list):
            raise WorldModelClientError(
                f"expected a JSON list from /find_place_by_name, got "
                f"{type(result).__name__}"
            )
        for match in result:
            if not isinstance(match, dict):
                raise WorldModelClientError(
                    "expected every /find_place_by_name result to be a JSON "
                    f"object, got {type(match).__name__}"
                )
        return result

    def get_line_of_sight_clear(
        self,
        observer: tuple[float, float, float],
        target: tuple[float, float, float],
    ) -> bool:
        """`GET /line_of_sight?ox=...&oz=...&oalt=...&tx=...&tz=...&talt=...
        &theatre=<theatre>` -> whether the sightline from `observer` to
        `target` (each `(x, z, alt_m)` in DCS-native coordinates) is clear,
        per `world-model/src/query/line_of_sight.py`."""
        ox, oz, oalt = observer
        tx, tz, talt = target
        query = urllib.parse.urlencode(
            {
                "ox": ox,
                "oz": oz,
                "oalt": oalt,
                "tx": tx,
                "tz": tz,
                "talt": talt,
                "theatre": self.theatre,
            }
        )
        result = self._get_json(f"/line_of_sight?{query}")
        clear = result.get("clear") if isinstance(result, dict) else None
        if not isinstance(clear, bool):
            raise WorldModelClientError(
                f"expected {{'clear': bool}} from /line_of_sight, got {result!r}"
            )
        return clear

    def _get_json(self, path: str) -> Any:
        url = f"{self.base_url}{path}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout_s) as response:
                body = response.read()
        except (urllib.error.URLError, OSError) as exc:
            raise WorldModelClientError(f"request to {url} failed: {exc}") from exc
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise WorldModelClientError(f"invalid JSON from {url}: {exc}") from exc
