# RC-B1 — Unbounded `level`/`vx`/`vy` digit length crashes a single request with an uncaught exception

- [ ] **RC-B1 — `GET /tile/<terrain>/<tier>/<level>/<x>/<y>.jpg` does not bound the magnitude of
  `level`/`vx`/`vy` before using them, so a crafted request causes an uncaught exception instead
  of a clean 4xx.** #status/open

  **Found during Security deep analysis (Mode 2) of `raster-chart-viewer` RC-1, 2026-11-16**
  (`plans/raster-chart-viewer/security-review.md`, Finding 1). Not a blocker — reproduced and
  confirmed low-impact, not filed as a Required Fix.

  `server.py`'s `_TILE_RE` captures `level`/`vx`/`vy` as `\d+` with no length cap, and
  `_handle_tile` converts each with bare `int(...)` before any terrain/tier validation. Two
  distinct uncaught-exception paths follow, both reproduced directly (not inferred):

  1. A digit string longer than `sys.int_info.default_max_str_digits` (4300 on Python 3.11+)
     makes `int()` itself raise `ValueError` — CPython's own guard against the quadratic
     int-parsing DoS (the fix for CVE-2020-10735), so this is not a CPU-exhaustion vector, just an
     unhandled exception.
  2. A `vx`/`vy` of a few hundred digits (well under that 4300-digit ceiling, so `int()` succeeds)
     produces a composed-tile cache filename (`cache.py`'s `f"{vx}_{vy}.jpg"`) longer than the
     filesystem's per-component limit (255 bytes on ext4/NTFS alike). `TileCache._write`'s
     `path.write_bytes(data)` then raises `OSError: [Errno 36] File name too long` — reproduced
     directly against a real temp directory on this machine with a 300-digit value.

  Neither `_handle_tile` nor `TileCache._write` has a `try/except` around these calls, so the
  exception propagates out of `do_GET` uncaught. `http.server.ThreadingHTTPServer`'s own
  `process_request_thread` catches it at the top (`handle_error`, a traceback to stderr) — **this
  does not crash the service or affect other connections**, only the one request, which gets a
  dropped/reset connection instead of a clean error response.

  **Why this is filed, not fixed in-line or blocked on:** reachable by any LAN peer with zero
  prerequisites (no valid terrain/tier needed — the parse happens before those checks), and
  trivial to trigger by poking the open port with an unusual numeric path segment — exactly the
  "infected machine on the LAN scanning ports" case the project's security threat model names.
  But the impact is bounded to log noise and one dropped connection per attempt; no crash, no data
  exposure, no cache corruption (the write fails before anything is partially written), no
  persistent effect. Risk matrix: **probability medium** (trivial to trigger, no special
  knowledge needed), **impact low** (single request fails cleanly at the OS/interpreter level,
  service and cache stay healthy). See `plans/raster-chart-viewer/security-review.md` for the
  full reproduction.

  **Recommended fix** (cheap, narrowly scoped): in `_handle_tile`, reject `level`/`vx`/`vy` whose
  magnitude is implausible for this service — e.g. refuse any value `>= 10**9` (`grid.max_level`
  never exceeds single digits, `vx`/`vy` never approach the low millions for the largest
  discovered grid) with a clean `400`, before calling `int()` on a string longer than a small fixed
  cap (e.g. 15 digits) at all. Add a regression test exercising both the `ValueError` and the
  `OSError` paths above. No design change, no new dependency.
