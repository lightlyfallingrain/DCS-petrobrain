"""World-model's first HTTP seam (MI-2, `plans/mi2-world-enrichment/plan.md`)
-- a read-only LAN-reachable wrapper around `query.describe.
describe_position`, `query.search.find_place_by_name`, and
`query.line_of_sight.line_of_sight_clear`, mirroring `aircraft-layer/src/
api/server.py`'s shape exactly (module-level path constants, a
`_make_handler(...)` factory closing over the server's bound state and
returning a `BaseHTTPRequestHandler` subclass, a `_respond_json` helper, an
owning class with `open()`/`close()`/`serve_forever()`/`port`/context
manager).

Unlike the aircraft-layer API, this server has **no `POST` routes at all**
-- world-model's query surface is entirely read-only, so only the `400`
"bad query param" case applies here, never `503`/non-GET handling.

One server instance is bound to exactly one already-open
`sqlite3.Connection` and one `theatre` string at construction time (mirrors
`describe_position`'s own `(conn, theatre, ...)` signature -- the
connection is already scoped to one theatre's `.sqlite`, see `world-model/
CLAUDE.md`'s "one SQLite file per region" decision). Every route that takes
a `theatre` query param validates it against this bound `theatre` and
answers `400` on a mismatch, rather than silently querying with the wrong
projection (`describe_position` calls `coordinates.dcs_to_wgs84(theatre,
...)` internally -- a caller passing the wrong theatre string against this
process would otherwise get a plausible-looking but wrong lat/lon with no
indication anything went wrong).

`named_places_radius_m`/`navaids_radius_m`/`los_samples`/`probe_db_path`
are constructor args on `WorldModelAPIServer`, not query params -- no
caller-side reason for a per-call override, and exposing `probe_db_path`
as a client-suppliable path would be a needless surface even under this
project's current no-auth exemption (see root `CLAUDE.md`'s "Agents"
section). Each defaults to `None` here and is only forwarded to the
underlying `query` function when set, so the function's own module-level
default (see `query.describe`/`query.line_of_sight`) is what actually
applies -- this avoids re-declaring those private default constants a
second time in this module, where they could silently drift out of sync.

**Deliberate deviation from `aircraft-layer/src/api/server.py`: `HTTPServer`
(single-threaded), not `ThreadingHTTPServer`.** That server shares
in-memory caches across request threads, which is safe; this server shares
one `sqlite3.Connection`, which is not -- a `sqlite3.Connection` may only
be used from the thread that created it unless opened with
`check_same_thread=False`, and even then concurrent statement execution on
one connection object is not safe. Serializing all requests onto one
thread sidesteps both problems with no real cost: this is an offline,
low-volume, single-consumer read path (see the plan's Risks & Unknowns --
"dozens of calls, not thousands"). Note this only fixes the *concurrent
access* half of sqlite3's thread rules -- if `serve_forever()` is ever run
on a different thread than the one that opened `conn` (e.g. a background
server thread in a test), the connection must still be opened with
`check_same_thread=False` by the caller; this module does not open the
connection itself, so it cannot enforce that.

Response bodies for the two dataclass-returning routes are built with
stdlib `dataclasses.asdict()` -- every dataclass involved
(`PositionDescription` and its nested `*Info` types, `PlaceMatch`) is
`@dataclass(frozen=True)` with only primitives/`list`/`None`/other such
dataclasses as field types, so `asdict()` recurses through all of it
correctly and the result round-trips through `json.dumps` with no custom
`to_dict` method needed anywhere in `query/`.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import TracebackType
from typing import Any, Self
from urllib.parse import parse_qs, urlparse

from query.describe import describe_position
from query.line_of_sight import line_of_sight_clear
from query.search import find_place_by_name

logger = logging.getLogger(__name__)

#: LAN-facing by design, mirroring `aircraft-layer/src/api/server.py`'s
#: `DEFAULT_HOST`.
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 7792

_DESCRIBE_POSITION_PATH = "/describe_position"
_FIND_PLACE_BY_NAME_PATH = "/find_place_by_name"
_LINE_OF_SIGHT_PATH = "/line_of_sight"


def _parse_query(path: str) -> tuple[str, dict[str, str]]:
    """Splits a request path into `(route, params)`, taking only the first
    value of each query-string key (this API has no repeated-key params)."""
    parsed = urlparse(path)
    params = {key: values[0] for key, values in parse_qs(parsed.query).items()}
    return parsed.path, params


def _require_float(params: dict[str, str], key: str) -> float:
    """Raises `ValueError` (caller turns this into a `400`) if `key` is
    missing or not parseable as a `float`."""
    if key not in params:
        raise ValueError(f"missing required query param {key!r}")
    try:
        return float(params[key])
    except ValueError as exc:
        raise ValueError(f"query param {key!r} must be a number") from exc


def _require_theatre(params: dict[str, str], bound_theatre: str) -> None:
    """Raises `ValueError` if `theatre` is missing or does not match this
    server's own bound theatre -- see the module docstring for why this
    must be loud rather than silently accepted."""
    theatre = params.get("theatre")
    if theatre is None:
        raise ValueError("missing required query param 'theatre'")
    if theatre != bound_theatre:
        raise ValueError(
            f"theatre {theatre!r} does not match this server's bound theatre "
            f"{bound_theatre!r}"
        )


def _make_handler(
    conn: sqlite3.Connection,
    theatre: str,
    probe_db_path: Path | None,
    named_places_radius_m: float | None,
    navaids_radius_m: float | None,
    los_samples: int | None,
) -> type[BaseHTTPRequestHandler]:
    class WorldModelRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path, params = _parse_query(self.path)
            if path == _DESCRIBE_POSITION_PATH:
                self._handle_describe_position(params)
                return
            if path == _FIND_PLACE_BY_NAME_PATH:
                self._handle_find_place_by_name(params)
                return
            if path == _LINE_OF_SIGHT_PATH:
                self._handle_line_of_sight(params)
                return
            self._respond_json(404, {"error": f"not found: {path}"})

        def _handle_describe_position(self, params: dict[str, str]) -> None:
            try:
                x = _require_float(params, "x")
                z = _require_float(params, "z")
                _require_theatre(params, theatre)
            except ValueError as exc:
                self._respond_json(400, {"error": str(exc)})
                return

            kwargs: dict[str, Any] = {"probe_db_path": probe_db_path}
            if named_places_radius_m is not None:
                kwargs["named_places_radius_m"] = named_places_radius_m
            if navaids_radius_m is not None:
                kwargs["navaids_radius_m"] = navaids_radius_m

            result = describe_position(conn, theatre, x, z, **kwargs)
            self._respond_json(200, asdict(result))

        def _handle_find_place_by_name(self, params: dict[str, str]) -> None:
            text = params.get("text")
            if text is None:
                self._respond_json(
                    400, {"error": "missing required query param 'text'"}
                )
                return

            kinds_param = params.get("kinds")
            kinds = kinds_param.split(",") if kinds_param is not None else None

            matches = find_place_by_name(conn, text, kinds)
            self._respond_json(200, [asdict(match) for match in matches])

        def _handle_line_of_sight(self, params: dict[str, str]) -> None:
            try:
                ox = _require_float(params, "ox")
                oz = _require_float(params, "oz")
                oalt = _require_float(params, "oalt")
                tx = _require_float(params, "tx")
                tz = _require_float(params, "tz")
                talt = _require_float(params, "talt")
                _require_theatre(params, theatre)
            except ValueError as exc:
                self._respond_json(400, {"error": str(exc)})
                return

            kwargs: dict[str, Any] = {}
            if los_samples is not None:
                kwargs["samples"] = los_samples

            clear = line_of_sight_clear(
                conn, theatre, (ox, oz, oalt), (tx, tz, talt), **kwargs
            )
            self._respond_json(200, {"clear": clear})

        def _respond_json(self, status: int, body: Any) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            logger.debug("%s - %s", self.address_string(), format % args)

    return WorldModelRequestHandler


class WorldModelAPIServer:
    """Owns the read-only world-model LAN API; mirrors `aircraft-layer`'s
    `TelemetryAPIServer` shape (`open()`/`close()`/`serve_forever()`/
    `port`/context manager)."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        theatre: str,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        probe_db_path: Path | None = None,
        named_places_radius_m: float | None = None,
        navaids_radius_m: float | None = None,
        los_samples: int | None = None,
    ) -> None:
        self._conn = conn
        self._theatre = theatre
        self._host = host
        self._port = port
        self._probe_db_path = probe_db_path
        self._named_places_radius_m = named_places_radius_m
        self._navaids_radius_m = navaids_radius_m
        self._los_samples = los_samples
        self._httpd: HTTPServer | None = None

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def port(self) -> int:
        """Bound port. Useful when constructed with `port=0` (OS-assigned)."""
        if self._httpd is None:
            raise RuntimeError("call open() before reading port")
        return int(self._httpd.server_address[1])

    def open(self) -> None:
        """Bind and start listening. Does not block."""
        self._httpd = HTTPServer(
            (self._host, self._port),
            _make_handler(
                self._conn,
                self._theatre,
                self._probe_db_path,
                self._named_places_radius_m,
                self._navaids_radius_m,
                self._los_samples,
            ),
        )
        logger.info("world-model API listening on %s:%d", self._host, self.port)

    def close(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def serve_forever(self) -> None:
        """Serve requests until `close()` is called from another thread."""
        if self._httpd is None:
            raise RuntimeError("call open() before serve_forever()")
        self._httpd.serve_forever()
