# Aircraft-layer performance review

**Date:** 2026-09-26. User-requested, whole-subproject pass (not a feature diff). Reviewed at
`main` tip `ace280e`. No live DCS session or Windows box was reachable from this sandbox — every
conclusion below is either derived from reading the code/wire formats, or explicitly marked as
needing a live run, per this review's own honesty rule.

**Why this subsystem is different from the rest of the project:** `Export.lua` and the two Hook
scripts execute *inside DCS's own process*, on threads DCS itself schedules. Cost here is frame
time in the cockpit, not latency in a service the user never watches. The collector and its HTTP
API run in a separate Windows process and are ordinary service code by comparison — a slow request
there costs a body-layer poll cycle, not a stutter while flying.

## Findings

### 1. `push_ptt_state` runs one `pcall` + one native call every DCS frame

- **Location:** `Export.lua` `LuaExportAfterNextFrame`, calls `push_ptt_state(t)` unconditionally
  before the 5 Hz throttle check.
- **Mechanism:** `GetDevice(0):get_argument_value(738)` wrapped in `safe_call`'s `pcall`, plus one
  `math.abs` comparison, every frame (~125 Hz, going by the collector's own observed ~8 ms cadence
  recorded in the file's comments).
- **Risk:** none credible. One native getter + one comparison at DCS's own frame rate is far below
  anything that shows up as stutter, and the design is deliberate and documented in-file (a press
  gated behind the 5 Hz telemetry throttle could lose up to 200 ms off the front of an utterance).
  This is exactly the "work at the right frequency" case — it has to run every frame because the
  signal it watches is edge-driven and short-lived, and the alternative (polling less often) would
  reintroduce the latency this design exists to avoid.
- **Action:** NOTED. No change needed; recorded so a future reviewer doesn't re-flag this as
  hot-path bloat without reading why it's there.

### 2. `LoGetWorldObjects` + two `list_indication` calls, unfiltered, at 5 Hz, on the DCS thread

- **Location:** `Export.lua` `LuaExportAfterNextFrame`, inside the `last_export_t` gate: one
  `LoGetWorldObjects()` call walked via `pairs()` into a hand-built JSON string, then two
  `list_indication()` calls (`HELPERAI_DEVICE_ID`, `WHEEL_INDICATOR_ID`) whose return is a
  recursive text dump of Petrovich's indicator tree, pushed through unparsed.
- **Risk:** this is the one place in the subsystem where per-call cost genuinely scales with
  mission population, and the project's own roadmap already flags it as unmeasured
  (`aircraft-layer/ROADMAP.md` backlog: "no confirmed, quantified per-call cost exists at realistic
  unit counts (~50–200) — only qualitative forum/Tacview-wiki folklore"). I can't refute or confirm
  that from code alone — `LoGetWorldObjects` is an opaque DCS-engine call, not something whose cost
  is derivable by reading Lua. The string-building around it (`encode_world_objects_line`) is not
  the risk: it appends into a Lua table and joins once with `table.concat`, which is the correct
  amortized pattern, not the O(n²) re-concatenation antipattern.
- **What would measure it, precisely:** fly the same mission three times, toggling
  `EXPORT_INTERVAL_S` (already a single named constant) between values that change only the
  world-objects/indication poll rate — or, more directly, temporarily stub out the
  `LoGetWorldObjects`/`list_indication` calls in one build and compare DCS's own frame-time counter
  (`Ctrl+Pause` stats or `dcs.log` FPS) against the unmodified build, same mission, same flight
  path, at a realistic complex size (50–200 units — the "twelve-unit complex" the acceptance
  sorties have flown so far is roughly 10x too small to see this). This is exactly the run the
  roadmap already specifies; nothing about this review changes that plan, it only confirms no
  substitute for it exists in code.
- **Action:** MONITOR (already tracked as a backlog item, correctly scoped). Not NOW — no evidence
  of a real budget violation exists yet, and inventing a mitigation ahead of a measurement would be
  guessing. Escalate to the user only in the form the roadmap already has: fly the measurement run
  above at 50–200 units before deciding whether the throttle split (finding 4) is worth doing.

### 3. Mission-scripting velocity bridge: `O(N)` unit enumeration at 1 Hz, cost never returned to the repo

- **Location:** `petrobrain-mission-telemetry-hook.lua`'s `VELOCITY_CODE`, executed via
  `net.dostring_in("scripting", ...)` from `onSimulationFrame`'s 1 Hz gate.
- **Mechanism:** enumerates every group/unit across all three coalitions via
  `coalition.getGroups`/`getUnits`, calling `pcall(unit:getVelocity())` per live unit, plus a
  fixed-cost pass over every static object. This crosses a Hook→mission-scripting state boundary
  (`net.dostring_in`) each poll, which is a different, and plausibly more expensive, mechanism than
  a same-state Lua call — the F10 command hook uses the identical bridge at the same 1 Hz rate and
  was accepted live, which is a reasonable existence proof that 1 Hz over this bridge is tolerable
  in general, but says nothing about how the bridge's cost scales with the *size of the returned
  payload*, since the F10 poll returns at most a few small tokens while this one returns one entry
  per unit.
- **Self-measurement already exists and is the right design**: the Hook logs `unit_count` and
  `bridge_call_ms` (measured with `os.clock()` around the `dostring_in` call itself) to `dcs.log`
  on every poll, and `UnitVelocitySnapshot` carries both fields through to
  `GET /unit_velocity/latest` — so the next sortie flown for any reason answers this for free. I
  checked whether that number has already been captured anywhere in the repo (research notes,
  acceptance-sortie docs) — it has not. The 2026-09-22 acceptance sortie's own doc
  (`docs/acceptance/2026-09-22-five-fixes-sortie.md`) describes a twelve-unit mission, well below
  the 50–200 range that would stress this, and doesn't record `bridge_call_ms` at all.
- **Risk:** credible as unit count grows, uncredible at the population flown so far. The mechanism
  that would surface a real problem (per-poll logging to `dcs.log`) is already in place; what's
  missing is a run with a large enough population and someone reading the log afterward.
- **What would measure it, precisely:** fly a mission with 50–200 units/statics (a real complex,
  not the twelve-unit test fixture), then `grep "velocity poll:" ` in `Saved
  Games\DCS\Logs\dcs.log` and read the `bridge_call_ms` trend as `unit_count` grows across the
  sortie (units die, spawn, patrol in and out — count will vary naturally in one flight). No new
  logging needs to be written; this is a read of existing output.
- **Action:** MONITOR now, with one concrete ask: **capture and record `bridge_call_ms` from the
  next sortie that has a realistic unit count**, even if performance isn't the flight's stated
  purpose. This is cheap (the logging already runs) and closes a real gap — right now nobody knows
  the number, and the mechanism to know it is deployed but unread.

### 4. Split export throttle — recommend against doing it before finding 2/3's measurements land

- **Location:** `Export.lua`'s single `EXPORT_INTERVAL_S = 0.2` gating self-data, world-objects, and
  both indication polls together (roadmap backlog item, proposed fix: two interval constants).
- **Assessment:** the roadmap's own reasoning is sound — BL-2's contact-decay timescales (30s/120s)
  are ~2 orders of magnitude slower than either 5 Hz or a candidate 2 Hz, so slowing the
  world-objects/indication polls costs no belief quality. But there is no measured FPS cost yet to
  react to (finding 2), so a split now would be guessing at a fix for an unconfirmed problem —
  itself a violation of "don't demand optimization without evidence." The shape of the proposed fix
  (two named constants, same gating pattern `last_export_t` already uses) is also right if it turns
  out to be needed: no architectural objection, just a sequencing one.
- **Action:** RECOMMENDED, but only after finding 2's measurement, and only if that measurement
  shows a real frame-time cost at realistic population. Doing the split first would spend
  implementation/review/DoD effort on a fix whose need is still unverified — the same shape of
  mistake the project's own retro records elsewhere (measure before optimizing).

### 5. HTTP `/latest` endpoints re-serialize the full cached object on every GET

- **Location:** `api/server.py`'s `_handle_world_objects_latest`/`_handle_unit_velocity_latest`/etc.,
  each calling `.to_dict()` on the cached snapshot fresh per request; `WorldObjectsSnapshot.to_dict`
  and `UnitVelocitySnapshot.to_dict` both rebuild a new list/dict comprehension over every object/
  unit in the snapshot, per call.
- **Risk:** low at today's scale. Parsing (the actually expensive step — `from_dict`/`from_wire`)
  already happens once at ingest, on the collector's own socket thread — confirmed by reading
  `collector/server.py`'s `_handle_line`, which calls `from_dict` once per received line and pushes
  the already-typed object into the cache. `to_dict()` is a second, cheap pass (attribute reads,
  no re-parsing) over an already-small collection (tens to low hundreds of objects), run once per
  HTTP request from what the docs describe as a single poller per endpoint
  (`/unit_velocity/latest`, `/world_objects/latest`) — this is not the "full-dataset iteration on
  every request against an unbounded dataset" failure mode, it's a bounded, small re-serialization.
- **Action:** NOTED, not NOW. Precomputing the JSON string once at push time (instead of at every
  GET) would be a legitimate cheapen-later move if a second concurrent poller is ever added to
  either endpoint — the API docs already flag `/f10_commands/poll` as "assumes exactly one
  poller," and the same assumption quietly holds for these `/latest` endpoints too, just without
  the mutation risk that makes it load-bearing there. Worth doing opportunistically if either
  endpoint is touched for another reason; not worth a dedicated pass now.

### 6. Audio playback queue has no upper bound, unlike its F10 sibling

- **Location:** `collector/audio_sender.py`'s `AudioPlaybackSender._queue: queue.Queue[str | None]`
  — constructed with no `maxsize`, unlike `collector/cache.py`'s `F10CommandQueue`, which is
  explicitly bounded (`_MAX_QUEUE_LEN = 64`) with a documented rationale ("a pathological flood...
  cannot grow this queue unboundedly").
- **Mechanism:** `play_audio()` writes the WAV to a temp file *before* enqueueing
  (`tempfile.mkstemp` + a blocking file write), then puts the path on the queue. If the producer
  (body-layer's crew-text/audio path) ever outpaces the consumer — a bug that stops
  callouts from being decided/dropped correctly, or simply a long multi-hour sortie with dense
  contact traffic — queued paths, and their backing temp files on disk, accumulate without limit.
  This is not a hot-path allocation concern (the worker thread still drains and plays one at a
  time, correctly serialized) — it's an unbounded-growth-over-a-long-session concern, which the
  Diagnostic Questions explicitly ask after ("can fewer items be processed / can this be bounded").
- **Risk:** currently low — the producer side (crew dialogue) is inherently rate-limited by how
  much Petrovich has to say, and playback duration (seconds per line) means the queue self-limits
  under any plausible callout rate. But it is the one asymmetry in this codebase between two
  structurally similar queues, and the F10 queue's own comment states the reasoning that would
  apply here too almost verbatim.
- **Action:** RECOMMENDED (cheap, not urgent). Cap `AudioPlaybackSender`'s queue the same way
  `F10CommandQueue` is capped, with an oldest-dropped (or newest-rejected — whichever matches
  "missed callout is better than unbounded disk growth") policy, and log when it triggers. This is
  a small, local, reversible change per `AGENTS.md`'s Escalation Rules — no architectural
  discussion needed, just parity with the pattern this codebase already uses elsewhere for the
  same reason.

### 7. HTTP request thread never blocks on playback or disk I/O in a way that stalls other clients

- **Location:** `api/server.py`'s `_handle_audio_play`, `AudioPlaybackSender.play_audio`.
- **Assessment:** checked specifically because the task asked whether anything blocks the HTTP
  thread. `play_audio()` does a synchronous temp-file write in the request-handling thread (small,
  fast, one WAV per push), but never touches `winsound`/blocking playback there — that only
  happens in the dedicated worker thread via the queue. `ThreadingHTTPServer` gives each connection
  its own thread, so even the temp-file write cannot stall a concurrent poller on a different
  endpoint. No finding here beyond confirming the design is already correct.
- **Action:** NOTED — confirms a designed invariant holds, not a new finding.

## What was ruled out without a live run

- **Whole-dataset iteration on every request** (this review's usual top hotspot elsewhere in the
  project): does not apply here. Every `/latest` endpoint reads a single cached object; nothing
  iterates the full history of anything, because there is no history — by design (finding 5's
  ingest-once-parse-once pattern, and the deliberate absence of a ring-buffer/delta endpoint,
  already documented and justified in `aircraft-layer/CLAUDE.md`).
- **Redundant queries**: each Export.lua/Hook poll is throttled to its own fixed interval and reads
  fresh DCS state once per interval — no evidence of the same DCS call being made more than once
  per tick anywhere in the reviewed files.

## Verdict

**APPROVED — MONITOR.**

No REQUIRED FIX. The one credible in-cockpit performance risk (`LoGetWorldObjects`/
`list_indication` cost at realistic unit counts, finding 2, and its mission-bridge sibling in
finding 3) is already known, already tracked, already instrumented for self-measurement, and
correctly *not yet acted on* pending a number nobody has captured yet — the honest state here is
"the harness is built, the flight that would fill it in hasn't happened." This review's only
concrete addition to that is finding 6 (bound the audio queue, cheap parity fix) and a firm
recommendation not to pre-emptively split the export throttle (finding 4) before finding 2/3's
measurement exists.

**What the user should actually do:** next time a sortie includes a realistic-sized complex
(50–200 units), read `dcs.log` afterward for `ActivityNextEvent`/`AfterNextFrame` frame-time
symptoms and `grep "velocity poll:"` for the `bridge_call_ms` trend. Both logging paths already
exist; this needs a flight and five minutes reading a log, not new code.
