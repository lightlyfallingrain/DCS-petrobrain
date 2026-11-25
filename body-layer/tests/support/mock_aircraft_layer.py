"""`MockAircraftLayerServer` -- a real loopback `http.server.HTTPServer`
serving `GET /telemetry/latest`, `GET /world_objects/latest`,
`GET /petrovich_indication/latest`, `GET /line_of_sight/latest`, and
`GET /firing/latest` from a
preloaded list of poll frames, mirroring `tests/test_aircraft_client.py`'s
handler-factory pattern (a real server, not a mocked `urllib`) so the
mock-flight chain tests exercise the real HTTP wire shape end to end.

**`GET /firing/latest` always serves a readable, daylight `mission_clock`
unless a frame explicitly overrides it** (debug: `plans/
bl-b124-light-level/debug-mock-flights.md`). Before this, the route did
not exist at all -- a 404, caught by `aircraft_client.AircraftLayerError`
and treated as "no firing feed" by every caller, which is the correct
degrade for emitter/firing resolution (`perception.naked_eye_source.
_resolve_firing_active`'s own "predates `AC-B8`" posture). But `[[BL-B124]]`
Stage 4 wired this same endpoint's `mission_clock` sub-wire into ambient
light level, and that feature's own policy (user Q6, `explore-notes.md`:
"mission should always have both readable. Error if not.") treats an
unreadable clock as **forced full dark**, not a silent daylight no-op --
so every scenario built on this server before `GET /firing/latest`
existed was silently flying at night from Stage 4 onward, changing scan/
gaze behaviour (and, via `look_direction`'s now-reachable `POST`, failing
outright since this handler had no `do_POST`). The fix is this route
itself, not a `do_POST` stub -- a stub would let scenarios keep running
in the dark and stop testing what they were written for. The synthesised
default (`_DEFAULT_MISSION_CLOCK_YEAR`/`_MONTH`/`_DAY`, local noon plus
the served frame's own `dcs_model_time_s`) keeps every existing scenario
in broad daylight exactly as it was before Stage 4, and advances with sim
time rather than freezing, so it is never mistaken for a dead/repeated
feed by `body._resolve_sun_elevation_deg`'s own staleness check regardless
of how long a test's real wall-clock run takes.

**`line_of_sight` added by `plans/bl11-stage4-fail-closed/plan.md` step 4
(`BL-11` Stage 4)**: fail-closed means a naked-eye candidate with no live
LOS verdict is now rejected outright rather than falling back to
world-model's offline primitive, so this server has to actually serve one
for the mock-flight chain's naked-eye observations to be admitted at all --
see `tests/fixtures/mock_flight_canonical.json`'s own per-frame
`"line_of_sight"` key (added alongside this change) and `_world_object`'s
new `unit_name` field.

**Frame advance is keyed on `GET /telemetry/latest` only** -- this is the
one correctness-critical property this module exists to get right (see
`plans/mock-flight-fixture/plan.md`'s "Decisions made" section). Within one
`ConsolePerceptionRunner.run_once()` poll, both `HybridPerceptionSource` and
`NakedEyePerceptionSource` call `get_world_objects_latest()`/
`get_petrovich_indication_latest()` independently, after the runner has
already called `get_telemetry_latest()` once for that poll. If this server
advanced its frame index on every GET, the two sources could observe
different poll frames within what is supposed to be one logical tick -- no
live aircraft-layer server would ever do that (it serves whatever
Export.lua last pushed, unchanged between pushes). This server instead
tracks two pieces of state: `_next_telemetry_index` (the frame `/telemetry/
latest` will serve next) and `_served_index` (the frame index that was most
recently served by a `/telemetry/latest` call, which `/world_objects/latest`
and `/petrovich_indication/latest` both mirror, however many times either is
called before the next telemetry poll).

Holds at the last frame once exhausted -- `/telemetry/latest` stops
advancing past `len(frames) - 1`, mirroring a real aircraft-layer server's
"latest" semantics after Export.lua stops pushing (mission end, DCS closed).

Each frame is a plain dict with up to four optional keys -- `"telemetry"`,
`"world_objects"`, `"petrovich_indication"`, `"line_of_sight"` -- each
already in the exact
wire shape `aircraft_client.AircraftLayerClient`'s `get_*_latest()` methods
expect (`TelemetrySample.to_dict()`/`WorldObjectsSnapshot.to_dict()`/
`PetrovichIndicationSample.to_dict()`'s shapes, per `aircraft-layer/src/
schema/`). A key absent from a frame (or the frame value `None`) serves
JSON `null` for that endpoint on that poll, matching the real aircraft
layer's "collector cache still empty" contract. `"firing"` is the one
exception to this -- see the `GET /firing/latest` paragraph above: absent
or `None` there synthesises a daylight default rather than serving a
literal `null`, because the real aircraft-layer server this mock stands
in for never returns `null` from that route at all."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

Frame = dict[str, Any]

#: Local noon, used only to synthesise a default `/firing/latest`
#: `mission_clock` when a frame does not supply its own `"firing"` key --
#: see the module docstring. Mid-year so the sun is high at any Syria
#: latitude the scenario builders place ownship at; the exact date has no
#: other significance.
_DEFAULT_MISSION_CLOCK_ABS_TIME_S = 12 * 3600.0
_DEFAULT_MISSION_CLOCK_YEAR = 2024
_DEFAULT_MISSION_CLOCK_MONTH = 6
_DEFAULT_MISSION_CLOCK_DAY = 21


class MockAircraftLayerServer:
    """See module docstring. Construct with a list of frames, then either
    use as a context manager directly (`with MockAircraftLayerServer(frames)
    as url:`) or call `start()`/`stop()` explicitly."""

    def __init__(self, frames: list[Frame]) -> None:
        if not frames:
            raise ValueError("MockAircraftLayerServer needs at least one frame")
        self._frames = frames
        self._next_telemetry_index = 0
        self._served_index = 0
        self._lock = threading.Lock()
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        if self._httpd is None:
            raise RuntimeError("MockAircraftLayerServer is not running")
        return f"http://127.0.0.1:{self._httpd.server_port}"

    def start(self) -> str:
        server = self
        handler = _make_handler(server)
        self._httpd = HTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self.url

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._httpd = None
        self._thread = None

    def __enter__(self) -> str:
        return self.start()

    def __exit__(self, *exc_info: object) -> None:
        self.stop()

    def _telemetry_response(self) -> Any:
        """Serves the next telemetry frame and advances the shared index --
        the only place `_next_telemetry_index`/`_served_index` change."""
        with self._lock:
            frame = self._frames[self._next_telemetry_index]
            self._served_index = self._next_telemetry_index
            if self._next_telemetry_index < len(self._frames) - 1:
                self._next_telemetry_index += 1
            return frame.get("telemetry")

    def _world_objects_response(self) -> Any:
        with self._lock:
            return self._frames[self._served_index].get("world_objects")

    def _petrovich_indication_response(self) -> Any:
        with self._lock:
            return self._frames[self._served_index].get("petrovich_indication")

    def _line_of_sight_response(self) -> Any:
        with self._lock:
            return self._frames[self._served_index].get("line_of_sight")

    def _firing_response(self) -> Any:
        """See the module docstring. `aircraft_client.get_firing_latest`
        never returns `None` for a live aircraft-layer server, so this
        always serves a dict -- either the frame's own explicit `"firing"`
        override, or a synthesised one carrying a readable, daylight
        `mission_clock` that advances with this frame's own
        `dcs_model_time_s`, keeping `body._resolve_sun_elevation_deg` out
        of its forced-dark/grace path for every scenario that does not
        itself ask to test night behaviour."""
        with self._lock:
            frame = self._frames[self._served_index]
            explicit = frame.get("firing")
            if explicit is not None:
                return explicit
            telemetry = frame.get("telemetry")
            t_sim = telemetry.get("dcs_model_time_s") if telemetry else 0.0
            return {
                "dcs_model_time_s": t_sim,
                "received_wall_clock_s": t_sim,
                "active": None,
                "mission_clock": {
                    "abs_time_s": _DEFAULT_MISSION_CLOCK_ABS_TIME_S + (t_sim or 0.0),
                    "year": _DEFAULT_MISSION_CLOCK_YEAR,
                    "month": _DEFAULT_MISSION_CLOCK_MONTH,
                    "day": _DEFAULT_MISSION_CLOCK_DAY,
                },
            }


def _make_handler(server: MockAircraftLayerServer) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/telemetry/latest":
                self._respond(200, server._telemetry_response())
            elif self.path == "/world_objects/latest":
                self._respond(200, server._world_objects_response())
            elif self.path == "/petrovich_indication/latest":
                self._respond(200, server._petrovich_indication_response())
            elif self.path == "/line_of_sight/latest":
                self._respond(200, server._line_of_sight_response())
            elif self.path == "/firing/latest":
                self._respond(200, server._firing_response())
            else:
                self._respond(404, {"error": "not found"})

        def _respond(self, status: int, body: object) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            pass

    return _Handler
