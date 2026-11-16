---
name: int-digit-length-at-lan-http-path-boundary
description: A URL path segment captured by a bare \d+ regex and passed to int() with no digit-count/magnitude bound reaches two distinct uncaught-exception paths (ValueError past 4300 digits, OSError if the value later becomes part of a filename) -- check every LAN-facing route that does this.
metadata:
  type: reference
---

**Pattern**: any `http.server`/stdlib-only LAN route whose handler regex captures a numeric path
segment as `\d+` and converts it with bare `int(...)` -- no `try`/`except`, no bound on the
digit-string's length or the resulting value's magnitude.

**Two distinct uncaught-exception paths, both reproduced (not inferred) on
`raster-chart-viewer`'s `GET /tile/<terrain>/<tier>/<level>/<x>/<y>.jpg`** (Mode 2 security review,
`[[RC-B1]]`, 2026-11-16):

1. **A digit string over `sys.int_info.default_max_str_digits`** (4300 on Python 3.11+, the
   CPython-side fix for CVE-2020-10735's quadratic int-parsing DoS) makes `int()` itself raise
   `ValueError`. Not a CPU-exhaustion vector any more (that is exactly what the 4300 cap prevents)
   -- just an unhandled exception at the request boundary.
2. **A digit string well under that 4300 ceiling** (a few hundred digits is enough) still parses to
   an `int` whose `str()` is that many characters long. If that value is later used to build a
   filesystem path component (a per-tile cache file keyed by the coordinate, for instance), the
   write raises `OSError: [Errno 36] File name too long` once the component exceeds the
   filesystem's limit (255 bytes on ext4; 255 UTF-16 code units on NTFS -- confirmed the same
   failure mode applies on both, not a POSIX-only artifact).

**Blast radius, measured, not assumed**: under `http.server.ThreadingHTTPServer`
(`socketserver.ThreadingMixIn.process_request_thread`), an uncaught exception inside a request
handler is caught per-thread by `handle_error` (a traceback to stderr) and does **not** crash the
server or disturb any other connection -- only that one request drops. So on this stdlib server
shape specifically, this pattern is a low-severity finding (one dropped connection + log noise per
attempt), not a service-level DoS. **Re-check this blast-radius claim if the server is ever not
`ThreadingHTTPServer`** (a different framework may not isolate exceptions per-request the same
way).

**Check every LAN-facing route in this repo that captures a numeric path segment via regex and
converts with `int()`** -- `aircraft-layer`, `world-model`, `brain-layer`, `audio-adapter`, and
`raster-chart-viewer` all run small stdlib HTTP servers with this exact shape. Grep for `\\d+` in a
route regex followed by a bare `int(` in the same handler.

**Recommended fix, cheap**: reject the value before `int()` if the digit count exceeds a small
fixed cap, or reject the parsed value if its magnitude exceeds what the route could ever
legitimately need (e.g. a zoom level or tile-grid coordinate has a known, small realistic upper
bound) -- return a clean `400` instead of letting the exception propagate.
