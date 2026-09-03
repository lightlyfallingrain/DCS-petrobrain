---
name: project_no_outbound_network_access
description: Bash tool has no outbound network access in this sandbox, even with dangerouslyDisableSandbox — affects fetching external datasets like SRTM
metadata:
  type: project
---

Confirmed during M4 (elevation, 2026-09-03): `curl -I https://example.com` via Bash is denied by
the permission layer, even with `dangerouslyDisableSandbox: true`. This is not domain-specific
blocking — plain outbound network access is unavailable to the Implementer agent in this
environment.

**Why:** discovered while trying to fetch an SRTM `.hgt` DEM tile from viewfinderpanoramas.org
for M4 Stage 2's DCS-vs-external elevation comparison.

**How to apply:** any future task needing to download an external dataset/file (DEM tiles,
imagery, etc.) cannot be done directly by this agent. Flag it to the user/coordinator as a
manual-fetch blocker (same category as the DCS live-mission-run blocker), rather than retrying
curl/wget with different flags or domains. WebFetch is not a substitute — it fetches
prose/markdown through a model, not binary files. See [[feedback_implementation_log_append]] for
how this was recorded mid-plan without overwriting prior implementation notes.
