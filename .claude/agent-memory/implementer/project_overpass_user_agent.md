---
name: overpass-requires-user-agent
description: Overpass API (overpass-api.de) rejects urllib requests with no User-Agent header (HTTP 406)
metadata:
  type: project
---

`urllib.request`'s default request carries no `User-Agent` header. Overpass API
(`overpass-api.de/api/interpreter`) returns `HTTP 406 Not Acceptable` for such requests, with
no payload — easy to mistake for a bbox/query problem.

**Fix**: set an explicit `User-Agent` header on the `urllib.request.Request` (any
non-empty descriptive string works, e.g. `"dcs-petrobrain-world-model/0.1 (...)"`).

**Why this matters here**: M3 (`world-model/src/osm/overpass.py`) is under a hard
one-network-call constraint. Hitting this on the first live attempt didn't cost a second
real fetch — the 406 came back with no data before any file was cached, so the fix-then-retry
was still within the "one call that actually returns data" budget — but it's worth knowing
this *before* attempting any future OSM/Overpass fetch, to avoid burning attempts under a
similarly strict network-call budget.

See `world-model/research/2026-09-03-m3-osm-overlay.md` for the full incident record.
