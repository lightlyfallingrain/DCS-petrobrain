"""Local collector: receives Export.lua's telemetry feed, caches it.

This package holds the trusted, single-writer collector process that runs
alongside DCS on the Windows box. It has two independently testable pieces:

- `cache.TelemetryCache` — most-recent-state + a short ring buffer, so a
  later consumer can ask "what changed since I last looked" as well as
  "what's the current state". Pure in-memory logic, no I/O — this is the
  piece stage 2 asks to be designed now even though the query API that
  consumes `since()` doesn't land until a later stage.
- `server.CollectorServer` — the local TCP listener that accepts Export.lua's
  loopback connection, parses each line via `schema.TelemetrySample`, and
  feeds `TelemetryCache`. This is the thin, live-network piece that can only
  really be exercised against a real Export.lua (or a hand-driven socket) —
  per the plan, its correctness is validated by the live DCS mission test,
  not by unit tests.
"""
