---
name: body-layer-poll-loop-serial-unpooled-gets
description: body-layer's poll loops make 6-8 serial, unpooled HTTP GETs per 1Hz poll cycle against aircraft-layer -- a pre-existing shape, not introduced by any one feature, worth knowing before flagging a new /latest endpoint as a performance risk
type: project
---

`body-layer/src/aircraft_client.py`'s `AircraftLayerClient` opens and tears down its own TCP
connection on every `get_*`/`post_*` call (`urllib.request.urlopen`, no session/connection-pool
reuse anywhere in the class). `run_once()` (in `body-layer/src/logger.py`) already calls 6-7 of
these per poll before BL-15 added an 8th (`get_mission_start_latest`, in `_check_for_new_mission`):
`get_telemetry_latest` once, plus whatever each wired `PerceptionSource` calls
(`HybridPerceptionSource.poll`: `get_petrovich_indication_latest`, `get_world_objects_latest`;
`NakedEyePerceptionSource.poll`: `get_world_objects_latest` again, `get_unit_velocity_latest`,
`get_firing_latest`, `get_line_of_sight_latest`).

**Measured poll rate is `_DEFAULT_POLL_INTERVAL_S = 1.0` (1 Hz), not 5 Hz.** A stale "5 Hz" claim
propagated through three places in this codebase (two `belief/brain_client.py` docstrings and a
`logger.py` comment) before being corrected and mechanically pinned by
`test_no_stale_five_hertz_claims_remain_in_src` (`BL-11` Stage 1) — `Export.lua`'s *producer*
rate was never this consumer's rate. Check this test/the `_DEFAULT_POLL_INTERVAL_S` constant
directly before quoting a poll rate in any review; do not reuse a remembered number.

**Why this matters for a performance review**: a new feature adding "one more GET per poll" to
this file is not a new cost class — it is the Nth instance of an already-established pattern.
Flag it as MONITOR, not NOW, unless the new call is itself doing something heavier than the
existing ones (iterating a large payload, blocking longer, or firing more often than 1 Hz). The
one real, cross-cutting risk this pattern carries — no connection pooling, and a slow collector
response can stall the whole synchronous poll cycle for up to `timeout_s` (default 2.0 s) — is
pre-existing architectural debt across *all* of `AircraftLayerClient`'s methods, not something
any single feature introduced; a fix (session reuse, or moving off synchronous serial GETs)
would need an Architect pass across the whole client, not a special case for one endpoint.

**Scope note**: root `CLAUDE.md` states no hard real-time budget applies yet — that constraint
starts once Petrobrain Runtime work begins. This poll loop is pre-Runtime body-layer code, so the
applicable bar today is "no per-request allocation on hot paths / prefer batching," not a latency
SLA. Re-check this scoping note once Petrobrain Runtime work actually starts — the bar changes
then.

See `plans/bl15-mission-start/performance-review.md` for the full worked review this was
extracted from.
