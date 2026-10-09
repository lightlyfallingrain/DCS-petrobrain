# WM-B12 — `?x=nan` / `?x=inf` kill the request

- [ ] **WM-B12 — `?x=nan` / `?x=inf` on `/describe_position` kill the request with no status and no
  body.** #status/open 2026-10-05 security audit, verified by execution: they pass `float()`, propagate through
  `dcs_to_wgs84` without raising, and die at `store/chunks.py:39`; the client gets
  `RemoteDisconnected`. A `math.isfinite` check at the boundary.
