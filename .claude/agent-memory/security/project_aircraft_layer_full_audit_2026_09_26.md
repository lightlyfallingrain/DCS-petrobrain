---
name: aircraft-layer-full-audit-2026-09-26
description: Full-subproject security audit of aircraft-layer on 2026-09-26 — dostring_in is clean, daemon-thread supervision is the recurring gap
metadata:
  type: project
---

Full-subproject review of `aircraft-layer/` (write path into DCS, LAN listener, read-only-install
rule, thread liveness, Saved Games deploys) landed no REQUIRED FIX. Report:
`aircraft-layer/research/2026-09-26-security-review.md`.

**dostring_in audit result (reusable, don't re-derive from scratch next time):** all three
`net.dostring_in` call sites (`petrobrain-f10-commands-hook.lua`'s `REGISTRATION_CODE`/`POLL_CODE`,
`petrobrain-mission-telemetry-hook.lua`'s `VELOCITY_CODE`) are compile-time fixed string literals,
never built from runtime/network input — confirmed by grep for `..` concatenation into any
`dostring_in` argument, none found. `Export.lua`'s inbound command channel (collector→Export.lua,
7793) doesn't use `dostring_in` at all — it's a regex field-extractor (`[%w_]+` only) compared
against two literal mode strings. If this pattern changes (a future Hook script builds a
`dostring_in` string from a variable), that's the first REQUIRED FIX this project would produce —
grep `dostring_in` call sites again rather than trusting this memory to still hold.

**Recurring pattern worth checking every pass: unsupervised daemon threads.** `collector/__main__.py`
starts 4 background daemon threads (collector, api, f10_command_receiver, unit_velocity_receiver)
with no join/health-check/restart. `CollectorServer.serve_forever()`'s `accept()` call itself is
unwrapped (only `_handle_connection` has a try/except) — an unexpected `OSError` there kills Export.lua
ingestion silently for the rest of the sortie, same shape as the watch-reporting review's prior
finding ([[brain_layer_wide_bind_no_benefit]] sibling pattern, different mechanism — that one was a
bind default, this one is thread supervision). No live trigger found this pass (the actual datagram/line
handlers are well-guarded, only raise their declared ParseError types), so this is latent/structural,
not a demonstrated bug — flagged RECOMMENDED not REQUIRED FIX. Re-check whether `__main__.py` gained
any supervision before re-flagging this as pre-existing-and-known.

**Also RECOMMENDED, not blocking:** no request-body size cap on `/text/push`,
`/command/petrovich_search`, `/audio/play` (LAN API, `api/server.py`) — `Content-Length`-driven
`rfile.read()` with no cap, `/audio/play` writes the whole decoded body to a temp file uncapped. Only
reachable via the trusted body-layer caller under this project's threat model (single-user LAN, no
adversary) — not exploitable today, cheap insurance if ever revisited.
