# BR-B2 — `brain-layer`'s HTTP server trusts the `Content-Length` header itself

- [ ] **BR-B2 — `brain-layer/src/server.py:173-174` reads `Content-Length` and converts it without
  guarding the header, so a non-numeric value raises an uncaught `ValueError`.** #status/open Filed
  2026-10-16 from the whole-subproject security survey
  (`brain-layer/research/2026-10-16-security-audit.md`), which found no exploitable vulnerability and
  two low/low items; this is the first.

  **Impact is bounded and should not be overstated**: one dropped connection and a traceback, not a
  server-down event — `ThreadingHTTPServer` isolates per connection. Under the standing scoping
  (single-user, LAN-only, under active development) nothing here is reachable by anyone but the
  pilot's own machine.

  **The fix already exists in this repo**, which is the argument for doing it rather than deferring:
  `audio-adapter/src/server.py`'s `_read_body` guards this exact pattern. Porting it brings the two
  services to parity, and the asymmetry is the real finding — two HTTP servers in one project,
  written to different standards, with no rule saying which is right.

  Related: `[[BR-B3]]` (the same survey's other item), `[[BR-1.2]]`.
