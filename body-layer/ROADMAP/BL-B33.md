# BL-B33 — Five sequential HTTP GETs with no connection reuse

- [ ] **BL-B33 — The poll body makes five sequential HTTP GETs with no connection reuse, each with
  a 2.0 s timeout.** #status/open Same pass. The loopback floor is 3.4 ms, so this is not the median cause — but
  it is a **~10–20 s worst-case blocking budget on one thread**, which is the right shape for the
  2026-10-05 sortie's otherwise-unexplained p90 of 4.98 s. Dropping the `/latest` timeouts to
  0.3–0.5 s is a constant change; a shared `http.client.HTTPConnection` is the fuller fix. A stale
  `/latest` is worth nothing anyway — these endpoints have no history.
