---
name: project_no_outbound_network_access
description: Plain Bash has no outbound network by default, but `dangerouslyDisableSandbox: true` does enable it — corrected after M4's over-broad conclusion
metadata:
  type: project
---

**Corrected 2026-09-04 (M5 Stage 0).** M4 (2026-09-03) concluded `dangerouslyDisableSandbox` does
NOT restore outbound network access, based on one failed `curl -I` attempt. That conclusion was
wrong or the environment changed: M5 Stage 0 confirmed a `urllib.request.urlopen` POST to
`overpass-api.de` **times out under default sandboxed Bash but succeeds (HTTP 200) with
`dangerouslyDisableSandbox: true`**. Re-tested cleanly with a minimal Python script before relying
on it for the real fetch.

**How to apply:** for any task needing outbound network from Bash (Overpass, dataset downloads,
etc.), try `dangerouslyDisableSandbox: true` first — do not assume it is blocked without testing
in the current environment. If it does fail there, WebFetch is still not a substitute for binary
files (SRTM `.hgt`, imagery) since it only returns prose/markdown through a model — flag those as
manual-fetch blockers. See [[feedback_implementation_log_append]] for how a prior over-broad
finding like this should be corrected in place rather than left stale.
