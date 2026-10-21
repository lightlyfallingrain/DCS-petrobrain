# AC-B11 — Unbounded `Content-Length` read on every `TelemetryAPIServer` POST handler

- [ ] **AC-B11 — Cap the body size `TelemetryAPIServer`'s POST handlers will read.** #status/open

Every `POST` handler in `aircraft-layer/src/api/server.py` (`_handle_text_push`,
`_handle_audio_play`, `_handle_command_petrovich_search`, `_handle_command_look_direction`, and
`BL-B66`'s new `_handle_command_cockpit_switch`) does:

```python
length = int(self.headers.get("Content-Length", "0") or "0")
raw_body = self.rfile.read(length) if length > 0 else b""
```

with no upper bound on `length`. This server binds to all interfaces (LAN-reachable, per
`aircraft-layer/CLAUDE.md`'s "What this is") — on the stated threat model (an infected LAN machine
scanning/probing reachable ports), a caller that sends a large `Content-Length` header forces
`rfile.read` to allocate and wait for that many bytes before the handler even looks at the JSON,
tying up the handler thread (or its memory) regardless of which endpoint is hit.

**Flagged during BL-B66's deep security analysis** (`plans/9k113-effectors/security-review.md`,
2026-10-21) because the new `/command/cockpit_switch` endpoint reproduces the same unbounded-read
shape fresh, by direct structural copy of `/command/petrovich_search`'s existing handler — not a
new pattern, but the pattern is now on five endpoints instead of four.

**Probability:** low — single-user, LAN-only project; the realistic actor per root `CLAUDE.md`'s
threat model is a misbehaving/infected box on the same LAN or a careless script, not a remote
adversary.
**Impact:** low — one blocked handler thread/some extra memory per request;
`ThreadingHTTPServer` means other requests are not blocked; no code execution or data exposure,
just a resource-exhaustion nuisance.

**Recommended fix:** a small shared constant (e.g. `_MAX_BODY_BYTES`) checked against
`Content-Length` before `rfile.read`, responding `400`/`413` over it — one helper, reused by all
five (eventually six, once `BL-B67` lands) handlers rather than duplicated per-endpoint.

Not blocking BL-B66's own merge — pre-existing shape, not something this feature's diff
introduced as new risk, and low/low on this project's stated threat model. Filed so it is
schedulable rather than sitting in a security report's prose.
