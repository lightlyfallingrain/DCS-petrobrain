# Export.lua Time-of-Day API, Ownship Lat/Lon Reuse, and Firing/Damage Events as Night Light Sources (BL-B124)

**Date:** 2026-11-25
**DCS version:** not verified locally this session (no DCS install reachable from this worktree)
**Theatre:** n/a — scripting-API / wire-format question

### Question
For BL-B124 (light-level-dependent detection ranges), three sub-questions:
(2) Can body-layer compute real-world date+time from `LoGetModelTime()` alone, or does it need
`LoGetMissionStartTime()`/a new `Export.lua` call?
(4) Are explosions (ordnance impact) observable as a position-resolvable event today?
(5) Does the existing firing-events channel already carry what a night-time missile/rocket-launch
light source needs, with no new DCS read?

### Findings

**Q2 — mission clock time of day**

- **`Export.LoGetMissionStartTime` is documented, shipped Export-channel API, distinct from
  `LoGetModelTime`.** — **evidence: documented** — **source:**
  `aircraft-layer/research/reference/Sim_ControlAPI.md:563-564` (the shipped Export API list) and
  `aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md:313` ("**Time of day *is*
  available from Export.lua alone**... `LoGetMissionStartTime()` + `LoGetModelTime()`, both
  documented in the shipped file (lines 433-434)"). That note already concluded: with the mission
  date (parsed from `.miz`) and ownship lat/lon (already in telemetry), sun elevation is ordinary
  local astronomy — no Hook, no `net.dostring_in`, no new channel needed *for the time-of-day part*.
- **`aircraft-layer/dcs-export/Export.lua` currently calls `LoGetModelTime()` only — `LoGetMissionStartTime()` is not called anywhere in the deployed script.** — **evidence: reproduced-locally** —
  **source:** `grep -n "LoGetModelTime\|LoGetMissionStartTime" aircraft-layer/dcs-export/Export.lua`
  → two hits, both `LoGetModelTime` (lines 350, 386; a documentation comment at line 39 also only
  names `LoGetModelTime`). So the architect's premise is correct: `LoGetModelTime()` alone (sim-
  elapsed seconds since mission start, resets on pause/restart per `aircraft-layer/CLAUDE.md`) is
  **not** sufficient for wall-clock time of day — it needs an anchor. `LoGetMissionStartTime()` is
  that anchor and is already proven reachable from the Export environment (it is in the same
  documented getter list `LoGetModelTime`/`LoGetAltitude`/etc. already in production use from), but
  the collector/schema side has never read it. This is a small, same-shape addition to
  `TelemetrySample` — one new numeric field, same cost class as any other `Lo*` getter already
  polled at 5 Hz.
- **What `LoGetMissionStartTime()` actually returns (seconds since midnight? a Unix-style epoch? mission-date-relative?) is not confirmed by any source read this session** — **evidence: documented
  (existence), inferred (exact semantics)**. The name and DCS forum/Hoggit convention strongly
  suggest "seconds since local midnight on the mission's `date`," matching the Mission Editor's own
  "Start Time" field, but no primary source text giving the exact return-value definition was
  quoted in either prior research file. This should be confirmed with a one-line live probe
  (`LoGetMissionStartTime()` printed alongside a Mission-Editor-set known start time) before any
  pipeline code trusts its units.

**Q4 — explosions as a light source**

- **`S_EVENT_HIT` is NOT in the production firing-events Hook's allow-list.** — **evidence:
  reproduced-locally** — **source:** `aircraft-layer/dcs-export/petrobrain-firing-events-hook.lua`
  lines 162-168, `ALLOWED_KINDS = { S_EVENT_SHOOTING_START, S_EVENT_SHOOTING_END, S_EVENT_SHOT,
  S_EVENT_DEAD, S_EVENT_CRASH }` — no `S_EVENT_HIT`. The research note that originally scoped this
  Hook (`aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-bridge.md`,
  findings 13-14) confirmed `S_EVENT_HIT`/`S_EVENT_DEAD` both exist and are documented, but the Hook
  that shipped only picked up `DEAD`/`CRASH`/`SHOT`/`SHOOTING_START`/`SHOOTING_END` — an ordnance
  impact that does **not** kill its target (the common "explosion near/on a unit" case) raises
  `S_EVENT_HIT` only, and is dropped at the Hook's own event handler today, never reaching the wire.
- **Even `S_EVENT_DEAD`/`S_EVENT_CRASH`, which the Hook *does* forward, carry no position.** —
  **evidence: reproduced-locally** — **source:** same file, lines 210-224 — `x`/`z` are only
  resolved (`initiatorPosition(event.initiator)`) when `kind == "S_EVENT_SHOT"`; every other kind's
  wire entry carries the literal string `"nil"` in both position fields (confirmed again in
  `schema/firing.py`'s own module docstring: "`x`/`z` are... populated... only for `S_EVENT_SHOT`...
  every other kind carries the literal string `'nil'`"). So a unit's death/crash is visible on this
  channel today, but **with no coordinate** — unusable as a positioned night light source as-is.
- **Conclusion: an exploding wreck/ordnance-impact light source does not exist on today's wire.**
  New DCS-side plumbing is needed: either (a) add `S_EVENT_HIT` to `ALLOWED_KINDS` and resolve the
  *target*'s position at hit time (mirroring the existing `initiatorPosition` pattern, applied to
  `event.target` instead of `event.initiator`), or (b) resolve position for `S_EVENT_DEAD`/
  `S_EVENT_CRASH` too (same mechanism, applied to `event.initiator`, which still exists at the
  moment of its own death event). Both are same-shape extensions of code already proven live
  (`world.addEventHandler` registration, `pcall`-guarded `getPosition()`), not a new mechanism —
  cheapest path is a small Hook-script diff plus one new wire field per added kind, no new
  registration/port/collector architecture.

**Q5 — missile/rocket launch position as a night light source**

- **`S_EVENT_SHOT`'s wire entry already carries initiator name, sim timestamp, and the initiator's
  position at launch time — confirmed by direct code read, not inference.** — **evidence:
  reproduced-locally** — **source:** `petrobrain-firing-events-hook.lua` lines 210-216 (position
  resolved once, at event time, via `initiatorPosition(event.initiator)`, specifically built per
  `schema.firing`'s own docstring as the seam for `[[BL-B74]]`, "the SAM launch position must be
  frozen at the moment of launch, never the launcher's current position") and `schema/firing.py`'s
  `FiringRawEvent` dataclass (`kind`, `t_sim`, `initiator: str`, `targets_ownship: bool`,
  `x: float | None`, `z: float | None`). Exact fields available for `S_EVENT_SHOT`: unit name
  (`initiator`), DCS sim time (`t_sim`), x/z in DCS-native planar coordinates (not lat/lon —
  `world-model`'s `dcs_to_wgs84` would be needed if lat/lon is wanted downstream), and
  `targets_ownship` (always `False` for `S_EVENT_SHOT` today — the Hook only resolves that bit for
  `SHOOTING_START`).
- **A "visible for a few seconds" window does not need a new state machine — `collector.
  firing_receiver.EmitterTracker` already is one, but it does not act on `S_EVENT_SHOT` yet.** —
  **evidence: reproduced-locally** — **source:** `firing_receiver.py`'s `_apply()` method and its
  own trailing comment: *"`S_EVENT_SHOT` -- the `[[BL-B74]]` seam, deliberately a no-op here... The
  raw event is still parsed and reaches this method; it is simply not acted on."* The tracker's
  existing latch/watchdog mechanism (`FIRING_MIN_VISIBLE_S = 1.5`, `FIRING_WATCHDOG_S = 180.0`,
  mission-restart reset, `GET /firing/latest` snapshot) is exactly the "a few seconds" visibility
  shape this question is asking about for gun fire (`EMITTER_KIND_FIRING`) — reusing the *pattern*
  for a launch-flash light source means adding a new `ActiveEmitter` kind (e.g.
  `EMITTER_KIND_LAUNCH_SMOKE`, the name the docstrings already reserve for this) with its own
  since/expiry handling in `_apply()`'s `S_EVENT_SHOT` branch, not inventing a new mechanism.
  Cheapest path: extend `EmitterTracker._apply` for `S_EVENT_SHOT` (a same-shape addition to code
  that already exists and is already tested), not a new body-layer state machine.

### Reproducible Test
```
grep -n "LoGetModelTime\|LoGetMissionStartTime" aircraft-layer/dcs-export/Export.lua
grep -n "ALLOWED_KINDS\|S_EVENT_HIT\|initiatorPosition" aircraft-layer/dcs-export/petrobrain-firing-events-hook.lua
grep -n "x: float\|z: float\|only for .S_EVENT_SHOT" aircraft-layer/src/schema/firing.py
grep -n "S_EVENT_SHOT.*no-op\|deliberately a no-op" aircraft-layer/src/collector/firing_receiver.py
```
To confirm `LoGetMissionStartTime()`'s exact return semantics, run on the Windows DCS box with a
mission whose Mission-Editor "Start Time" is set to a known value, log `LoGetMissionStartTime()`
once at mission start, and compare.

### Possible Approaches
- **Time anchor**: add `LoGetMissionStartTime()` to `Export.lua`'s poll and `TelemetrySample`
  (one new field), confirm its units with a one-line live probe, then compute wall-clock
  date+time as `mission.date + mission.start_time + LoGetModelTime()` (pending resolution of
  mission-interpreter's `start_time` question, see sibling note).
- **Explosions**: extend `petrobrain-firing-events-hook.lua` to add `S_EVENT_HIT` to
  `ALLOWED_KINDS` with target-position resolution, and/or resolve position for `S_EVENT_DEAD`/
  `S_EVENT_CRASH` — both same-shape Hook-script diffs, no new channel/port.
- **Missile/rocket launches**: no new DCS plumbing needed — extend `EmitterTracker._apply`'s
  `S_EVENT_SHOT` branch to create a time-bounded `ActiveEmitter` entry (reusing the existing
  latch/watchdog shape), surfaced through the existing `GET /firing/latest` snapshot.

### Unresolved
- Exact return units/semantics of `LoGetMissionStartTime()` — needs a live probe, not found
  documented at the value-semantics level in either prior research file.
- Whether `S_EVENT_HIT`'s `target` reference stays valid long enough in a `pcall` to read its
  position at the moment of a lethal hit (the `S_EVENT_DEAD` case) — not tested; existing
  `pcall`-guards in the Hook (the "a unit that died in the same frame... can raise on
  `getName()`/`getID()`" comment) suggest this edge case is already anticipated defensively but
  not yet exercised for position reads specifically.
- No live-mission cost measurement exists for any of these additions (same open-ended "not
  measured" status every prior firing/damage-events note already carries).
