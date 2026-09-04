"""Overpass API fetch-and-cache for a single OSM bounding box.

HARD CONSTRAINT (see `plans/m3-osm-overlay/plan.md`): this module makes at
most one network call per cache miss, ever. `fetch_bbox` checks for the
cache file first and returns it unread over the network if present -- no
retry-with-backoff loop, no pagination, no per-feature follow-up queries. If
the request fails, it raises rather than silently retrying.

Uses stdlib `urllib.request` only -- no new dependency for a one-off HTTP
call (see plan's "Data source" section).
"""

import urllib.request
from dataclasses import dataclass
from pathlib import Path

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Client-side socket timeout for urlopen -- independent of the query's
# server-side `[timeout:25]` above, which bounds Overpass's own query
# execution. This value just needs to comfortably exceed that.
_TIMEOUT_S = 60
# Overpass rejects requests with no User-Agent (HTTP 406) -- urllib's default
# has none, so one must be set explicitly.
_USER_AGENT = "dcs-petrobrain-world-model/0.1 (offline research pipeline)"


@dataclass(frozen=True)
class BBox:
    """A WGS84 bounding box, south/west/north/east in decimal degrees."""

    south: float
    west: float
    north: float
    east: float


def _build_query(bbox: BBox) -> str:
    """M5's widened query (see
    `plans/m5-first-persistent-model/plan.md` "Affected Modules / Files" ->
    `osm/overpass.py`): M3's `highway`/`building`/`place` node/`waterway`
    set, plus `landuse`, `natural=water`, and `place` way/relation --
    settlement and water features need *extent* (a polygon), not just a
    labelled point, and M3's original query had neither. Validated by M5
    Stage 0's census fetch
    (`world-model/research/2026-09-04-m5-stage0-census.md`) before becoming
    the default here."""
    coords = f"{bbox.south},{bbox.west},{bbox.north},{bbox.east}"
    return (
        "[out:json][timeout:25];\n"
        "(\n"
        f'  way["highway"]({coords});\n'
        f'  way["building"]({coords});\n'
        f'  node["place"]({coords});\n'
        f'  way["place"]({coords});\n'
        f'  relation["place"]({coords});\n'
        f'  way["waterway"]({coords});\n'
        f'  way["natural"="water"]({coords});\n'
        f'  relation["natural"="water"]({coords});\n'
        f'  way["landuse"]({coords});\n'
        ");\n"
        "out geom;\n"
    )


def fetch_bbox(bbox: BBox, cache_path: Path, query: str | None = None) -> Path:
    """Return the path to the cached Overpass JSON response for `bbox`.

    If `cache_path` already exists, returns it immediately with no network
    call. Otherwise performs exactly one Overpass API request, writes the
    raw response body to `cache_path` (creating parent directories as
    needed), and returns `cache_path`.

    `query` overrides the default `highway`/`building`/`place`
    node/`waterway` query built by `_build_query` -- callers that need a
    widened tag set (e.g. M5 Stage 0's census fetch) pass their own Overpass
    QL string instead of duplicating this module's caching/User-Agent/
    single-call discipline.

    Raises `urllib.error.URLError` (or a subclass, e.g. `HTTPError`) if the
    request fails -- no automatic retry.
    """
    if cache_path.exists():
        return cache_path

    if query is None:
        query = _build_query(bbox)
    request = urllib.request.Request(
        _OVERPASS_URL,
        data=query.encode("utf-8"),
        headers={"User-Agent": _USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
        body = response.read()

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(body)
    return cache_path
