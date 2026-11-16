---
name: bl-b118-altimeter-qnh-sync-cost
description: BL-B118's operator-altimeter QNH closed loop (body-layer/src/belief/altimeter_qnh_sync.py) -- exact per-poll blocking cost, convergence window, and why it reviewed cheaper than the effector_engine one-shot-read pattern it mirrors
metadata:
  type: project
---

Reviewed 2026-11-16, `plans/bl16-qnh-mission-start/perf.md`, verdict APPROVED — MONITOR.

## Shape

`advance_altimeter_qnh_sync` runs on the single shared poll thread
(`body.py::_run_crew_text_poll_loop`), called **unconditionally once per poll** right after
`_check_for_new_mission` and **before** `runner.run_once()` (perception/belief/attack-run tick) —
so a blocking read here delays that same poll's perception and callout work, every poll, for as
long as the run stays `"running"`.

Per call: **at most one `read_args` + at most one `write_cockpit_switch`**, strictly tighter than
`effector_engine.advance`'s own one-shot reads, which can issue up to N sequential blocking
`read_args` calls in one `advance()` (one per concurrently-running trigger). Zero cost once
terminal (`phase != "running"` is the first line, immediate return, no I/O) — confirmed, not
inferred.

## The timeout split that matters for any `read_args`-based mechanism in this codebase

Two different timeouts apply to the same call, and conflating them overstates the typical cost by
8×:
- **`ARG_READ_TIMEOUT_S = 0.25` s** (`aircraft-layer/src/collector/arg_read_broker.py:38`) — the
  collector's *own* bound on how long it waits for `Export.lua` to answer before replying (success
  or a bounded error). This is the realistic per-poll cost whenever Export.lua simply hasn't
  answered yet.
- **`_DEFAULT_TIMEOUT_S = 2.0` s** (`body-layer/src/aircraft_client.py:179`) — the client-side
  `urlopen` timeout, which only binds if the aircraft-layer HTTP server itself is unreachable/
  wedged at the TCP/HTTP level (not just a slow `Export.lua` reply) — the pathological case, not
  the typical one.

Same split already established for `effector_engine`'s one-shot reads
(`plans/effector-sequences/performance-stage4.md`) — check both constants, not just the client
default, before quoting a "blocks for N seconds" figure for any `read_args` caller.

## Convergence window

Bounded by the plan's own `ALTIMETER_QNH_MAX_ITERATIONS=20` (5–60) /
`ALTIMETER_QNH_MAX_DURATION_S=15.0 s` (5.0–60.0); at the default 1 Hz poll and
`ALTIMETER_QNH_SETTLE_S=0.3 s` (< poll interval, so never skips a poll at defaults), roughly one
iteration per poll → **~15-20 s of wall time after any mission (re)start** during which every
poll pays the typical ~0.25 s / pathological ~2.0 s stretch above. This is armed at the
first-event-adopted site too, i.e. reachable at an **air start already in combat**, not just a
safe pre-flight moment — the credible risk is this window's overlap with an attack-run/callout
need, not the mechanism's steady-state cost (which is zero).

## Why this reviewed as cheaper than an already-MONITORed sibling, not a new risk class

Same order of magnitude and same architectural shape as the pre-existing
[[body-layer-poll-loop-serial-unpooled-gets]] risk (5-8 serial unpooled GETs/poll, 2.0 s timeout
each) — already reviewed, already MONITOR, not introduced by this feature. A new one-shot-read
consumer on this poll thread is the Nth instance of an established, already-accepted pattern, not
automatically NOW — check whether it's heavier (more calls/poll, longer block, higher frequency)
than what's already there before escalating.
