"""`MockAircraftLayerServer` -- a real loopback `http.server.HTTPServer`
serving `GET /telemetry/latest`, `GET /world_objects/latest`, and
`GET /petrovich_indication/latest` from a preloaded list of poll frames,
mirroring `tests/test_aircraft_client.py`'s handler-factory pattern (a real
server, not a mocked `urllib`) so the mock-flight chain tests exercise the
real HTTP wire shape end to end.

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

Each frame is a plain dict with up to three optional keys -- `"telemetry"`,
`"world_objects"`, `"petrovich_indication"` -- each already in the exact
wire shape `aircraft_client.AircraftLayerClient`'s `get_*_latest()` methods
expect (`TelemetrySample.to_dict()`/`WorldObjectsSnapshot.to_dict()`/
`PetrovichIndicationSample.to_dict()`'s shapes, per `aircraft-layer/src/
schema/`). A key absent from a frame (or the frame value `None`) serves
JSON `null` for that endpoint on that poll, matching the real aircraft
layer's "collector cache still empty" contract.

`POST /text/push` (the overlay write path) is deliberately not implemented
-- this plan's fixture never sets `ConsolePerceptionRunner.overlay_client`,
so no test exercises it."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

Frame = dict[str, Any]


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


def _make_handler(server: MockAircraftLayerServer) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/telemetry/latest":
                self._respond(200, server._telemetry_response())
            elif self.path == "/world_objects/latest":
                self._respond(200, server._world_objects_response())
            elif self.path == "/petrovich_indication/latest":
                self._respond(200, server._petrovich_indication_response())
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
