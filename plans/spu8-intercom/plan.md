<!-- doc-provenance:start -->
**Decision for:** [[AA-3]]
<!-- doc-provenance:end -->

### Goal

Make Petrovich's audibility and listening gated by the SPU-8 intercom switches the real aircraft
has (pilot NET-1, arg 377, AND co-pilot ICS power, arg 664), make the SPU-8 volume knob (arg 457)
control his playback loudness, and give both of those a sensible automatic default at mission
start — without adding a dependency, a replay buffer, or any new suppression path alongside the
one (`silence`) that already ships.

### Spec vs. code — one correction worth recording before the stages

The dispatch brief's framing ("BL-6 added a wheel-state feed — check what it is") pattern-matches
on the word "wheel" but is wrong: BL-6's wheel feed (`WHEEL_INDICATOR_ID = 10`,
`list_indication(10)`) is Petrovich's **AI-Wheel search-mode indicator** (OBSERV. OFF → WAITING →
SEARCHING → TRACKING) — a detection/search UI, unrelated to landing gear or weight-on-wheels. There
is no weight-on-wheels signal anywhere in this codebase.

The signal this slice actually needs — "is the aircraft on the ground" — **already flows
end-to-end and is unrelated to BL-6's wheel**: `Export.lua`'s `LoGetAltitudeAboveGroundLevel()` →
wire field `alt_agl` → `aircraft_layer.schema.TelemetrySample` → body-layer's
`perception.source.OwnshipState.alt_agl_m`, present on every `OwnshipState` already consumed each
poll in `logger.py`. Stage 5 below uses that, not a new feed.

### Affected Modules / Files

**aircraft-layer** (Stages 1-4):
- `dcs-export/Export.lua` — read args 377/664/457 every frame, send on change (Stage 1); the
  5-second-after-start co-pilot ICS write (Stage 4). `EXPORT_SCRIPT_VERSION` bump for Stage 1 (new
  wire field), per this file's own version-bump rule.
- `src/schema/spu8.py` (new) — `Spu8Sample`: raw 377/664/457 plus `net1_on`/`ics_power_on`/
  `gate_open` properties, mirroring `schema/ptt.py`'s raw-plus-decided shape.
- `src/schema/__init__.py` — re-export `Spu8Sample`.
- `src/collector/cache.py` — `Spu8Cache` (latest-of-one, mirrors `PttCache`).
- `src/collector/server.py` — `_handle_line` gains a `"net1"`-keyed branch (same key-presence
  dispatch every other feed uses) pushing to `Spu8Cache`.
- `src/collector/audio_sender.py` — `AudioPlaybackSender` gains an injectable gate/volume
  provider, consulted once per queued item immediately before playback: drop silently if closed,
  scale PCM by the current volume if open.
- `src/api/server.py` — new `GET /spu8/state` endpoint (Stage 1); `_handle_ptt_state` combines
  `PttCache` + `Spu8Cache` so the served `"intercom"` boolean is already gated (Stage 2) —
  `TelemetryAPIServer.__init__` gains `spu8_cache: Spu8Cache | None = None`, same
  defaults-to-a-fresh-empty-cache pattern every other optional cache here already follows.
- `src/collector/__main__.py` — construct one `Spu8Cache`, wire it into both `TelemetryAPIServer`
  and `AudioPlaybackSender`.
- Tests: `tests/test_schema_spu8.py` (new), `tests/test_ptt.py` (existing API test updated — see
  Decision 3), new assertions in a server-cache test file, `tests/test_audio_sender.py` (new gate/
  volume cases).

**audio-adapter**: **no changes.** `DcsPTT.is_down()` already reads the served `"intercom"` field
verbatim off the wire (`ptt_source.py:445`); Stage 2 changes what that field *means* at the
collector, not how it's read. This is the "gating capture in the collector, not downstream" design
constraint satisfied literally, not just in spirit.

**body-layer** (Stage 5):
- `src/belief/crew_console.py` — `CrewConsole.maybe_apply_on_ground_default`, one-shot, plus
  `ON_GROUND_AGL_THRESHOLD_M`.
- `src/logger.py` — call it from `_run_crew_text_poll_loop`, once per poll (no-op after the first
  successful call).
- Tests: `tests/test_crew_console.py` (new cases).

### Implementation Plan

**Stage 1 — SPU-8 state telemetry.** *(aircraft-layer only)*

Add a third "raw state, read every frame, sent only on change" channel alongside `push_ptt_state`,
covering args 377 (NET-1, pilot's "intercom 1" switch — user-confirmed 2026-10-05, superseding the
roadmap table's 456+376/377 guess), 664 (co-pilot ICS power, operator panel, cross-seat write
already confirmed live), and 457 (pilot SPU-8 volume, continuous 0..1). One combined line,
`{"t":...,"net1":...,"ics_power":...,"vol":...}`, all three read via `GetDevice(0):
get_argument_value(<arg>)` (device 0, mainpanel — same read path as every other arg this file
already reads). `Spu8Sample` carries the three raw values plus `net1_on`/`ics_power_on` (threshold
`>= 0.5`, never equality — both args animate through intermediate values for ~0.1s, same
reasoning as `PttSample`'s own tolerance) and `gate_open = net1_on and ics_power_on`.
`GET /spu8/state` serves `sample.to_api_dict()` or JSON `null` before the first sample, identical
shape to `/ptt/state`.

Bump `EXPORT_SCRIPT_VERSION` (new wire field) and `EXPECTED_EXPORT_VERSION` in `server.py` together.

*Live acceptance (aircraft-layer):* fly, `curl GET /spu8/state`, toggle NET-1 and the co-pilot ICS
switch (operator seat or the Stage-4 auto-write), sweep the volume knob; confirm raw values and
the two booleans track the cockpit and match the 2026-10-05 recon's observed ranges.

**Stage 2 — capture gating.** *(aircraft-layer only, depends on Stage 1)*

`_handle_ptt_state` reads both caches and serves `"intercom": sample.intercom and spu8_gate_open`
— `"radio"` is untouched (a full press is talking to ATC/another player, not to Petrovich, and is
independent of the SPU-8 gate). `spu8_gate_open` is `False` whenever `Spu8Cache.latest() is None`
(see Decision 1 on why that default is fail-safe-closed here, unlike Stage 3's provider default).

Because `audio-adapter`'s `DcsPTT` already reads the `"intercom"` field verbatim, this is the
entire capture-gating mechanism — no audio-adapter change, per the module boundary CLAUDE.md
already draws for this seam.

*Live acceptance:* with NET-1 or co-pilot ICS off, hold the ICS PTT and speak; confirm no capture
is triggered (collector/`--debug` log shows no change, or `audio-adapter`'s capture log shows no
posted clip). Switch back on, confirm capture resumes.

**Stage 3 — playback gating + volume.** *(aircraft-layer only, depends on Stage 1, independent of
Stage 2)*

`AudioPlaybackSender` gains an injected `gate_state: Callable[[], Spu8GateState] = _always_open`
provider (`Spu8GateState(gate_open: bool, volume: float)`), consulted once per item, in the worker
thread (`_run`), immediately before `self._player.play(path)` — see Decision 2 for why this single
point, not enqueue time. If closed: log, clean up the temp file, do not call `play()`, move on —
no special-casing for `urgent` (an off switch means off, unconditionally). If open: scale the WAV's
PCM samples by the current `volume` (0..1 linear) with stdlib `wave` + `array` (16-bit signed
samples: `array('h')`, byteswap on big-endian hosts, multiply, clamp to int16, write back) — a
`winsound` volume call is impossible (`winsound` has none, `audio-adapter/ROADMAP.md`). **Not
`audioop`** (main-loop amendment 2026-10-05): it was deprecated in 3.11 and removed in Python 3.13,
and the collector's `requires-python = ">=3.11"` does not pin below 3.13 — on a 3.13 Windows
interpreter `import audioop` fails. If the WAV is not 16-bit PCM, play it unscaled and log once
rather than guess — then play. "Next-utterance
granularity" per spec: the factor used is whatever is current when this item reaches the front of
the queue, not resampled mid-playback.

Real wiring in `__main__.py` passes `spu8_cache.gate_state` (closed-when-unknown, matching Stage 2).
The constructor default (`_always_open`, full volume) exists so every pre-existing
`AudioPlaybackSender` test and call site that doesn't care about gating keeps working unchanged —
see Decision 3 for why this default differs from Stage 2's.

*Live acceptance:* with the gate open, turn the volume knob between two callouts and confirm an
audible change; close the gate mid-sortie (either switch) and confirm total silence on the audio
channel while the overlay/text output (ungated — `self.silenced`/this gate are audio-only) keeps
updating.

**Stage 4 — automatic co-pilot ICS ON at mission start.** *(aircraft-layer, `Export.lua` only — no
Python change, no automated test)*

Self-contained in `Export.lua`, following the BL-6 wheel-effector precedent exactly (no round trip
through the collector): capture `mission_start_model_t` on the first frame where `LoGetSelfData()`
succeeds (i.e., actually in the cockpit, not the briefing screen) — same guard
`push_ptt_state`/`DUMPED_SELF_DATA` already use. Once `t - mission_start_model_t >= 5.0` and the
write hasn't fired yet this session, call `GetDevice(55):performClickableAction(3015, 1)` once
(`CMD_SPU8_O_ICS`, confirmed live 2026-10-05) and set a `copilot_ics_set` flag so it never
refires. Reset both `mission_start_model_t` and `copilot_ics_set` in `LuaExportStop`, mirroring
`pending_release_t`'s reset, so a mission restart re-triggers the 5-second wait rather than
staying latched from a previous sortie.

*Live acceptance only* (Lua, no live-DCS CI): `luac5.1 -p` syntax check, then fly — watch the
co-pilot ICS switch in the cockpit (or poll `GET /spu8/state`) move to ON ~5s after spawn.

**Stage 5 — on-ground default silent mode.** *(body-layer only, independent of Stages 1-4)*

`CrewConsole.maybe_apply_on_ground_default(ownship: OwnshipState) -> None`: on its first call only
(an internal one-shot flag, not re-evaluated afterward regardless of later altitude), if
`ownship.alt_agl_m <= ON_GROUND_AGL_THRESHOLD_M`, sets `self.silenced = True` **directly** — not
through `_handle_silence()`, which would speak the one-word acknowledgement first; an automatic
startup default has nothing to acknowledge and should not be the very first thing a cold-starting
crew channel says. Reuses the already-shipped `silenced` flag and its already-shipped behaviour
(audio-only gate, ends on any subsequent command) with zero new suppression logic, per the spec's
own instruction.

Called from `_run_crew_text_poll_loop`, right after `runner.run_once()` succeeds and before
`crew_console.drain_events(...)`, so a mission-start default (if applied) takes effect before
anything from that same poll could be spoken.

*Decided (user, 2026-10-05, locked):* silent mode stays exactly as already shipped — **only a
command ends it; leaving the ground does not.** No auto-end-on-takeoff stage. The user expects
richer when/what logic later ("will change later at some point with more logic on what and when")
— this stage is deliberately the simplest version that satisfies the current spec, not a
foundation being built toward that richer system.

*Live acceptance:* start a mission on the ground with the SPU-8 gate open; confirm no spoken
contact reports before the first command, even if contacts are detected and overlay/text output
is still updating; give any command; confirm normal speech resumes and stays resumed even after a
later touch-down in the same sortie (one-shot, mission-start-only — not re-armed by landing again).

### Decisions

1. **The capture gate is enforced by overriding `GET /ptt/state`'s served `"intercom"` boolean at
   the collector, not by adding SPU-8 awareness to `audio-adapter`'s `DcsPTT`.** Satisfies "gating
   capture in the collector, not downstream" literally: zero audio-adapter changes.
2. **Playback gating and volume scaling both happen at one point — immediately before
   `WavPlayer.play()`, in the worker thread — not at `play_audio()`/enqueue time.** A line sitting
   briefly behind another in the FIFO gets re-checked against current switch/volume state right
   before it actually plays, which is closer to "what was true when he actually spoke" than
   checking at arrival would be, and needs no second check site.
3. **Two different "no SPU-8 data yet" defaults, deliberately not the same value.** `Spu8Cache`
   empty → **gate closed** (fail-safe: an unknown intercom state should not let anything through,
   either direction) — this is `/ptt/state`'s and the real `AudioPlaybackSender` wiring's behavior.
   `AudioPlaybackSender`'s own constructor default (`gate_state` unset) → **always open, full
   volume** — this is a backward-compatibility default for every existing/unrelated test and call
   site that predates this feature and never wires a provider, not a real production path.
4. **The mission-start co-pilot ICS write lives entirely in `Export.lua`**, no collector/Python
   involvement — mirrors the BL-6 AI-Wheel effector's shape exactly, and avoids inventing a second
   command-dispatch round trip for a self-contained timer-plus-single-write behaviour.
5. **The on-ground silent-mode default is evaluated once, at the first successful poll, and never
   again.** Matches the spec's "when mission starts... if on ground" framing (a startup default,
   not a continuous ground/air re-assertion) and composes cleanly with Decision 6/the locked user
   decision below — there is nothing to "leave the ground" from if the check never re-runs.
6. **(Locked, user direction 2026-10-05) Silent mode's end condition is unchanged: any command
   ends it, leaving the ground does not.** Recorded here as decided, not as an open question.

### Risks & Unknowns

- **`ON_GROUND_AGL_THRESHOLD_M` is an uncalibrated guess** (same debt class as
  `mission_phase.WAYPOINT_CAPTURE_RADIUS_M`) — no weight-on-wheels signal exists, so this is
  `alt_agl_m` against a placeholder metres value. Needs live-flight confirmation that it reads
  "on ground" on the ramp and does not false-trigger during a low hover.
- **377/664's ~0.1s animation through intermediate values could flicker `gate_open` open↔closed
  for ~100ms during any switch flip.** By design this just drops audio momentarily (no replay
  buffer, per spec) — low risk, but worth confirming by ear it doesn't sound like a glitch/click
  rather than clean silence.
- **Linear PCM scaling is not a perceptual loudness curve.** Accepted per the
  spec's own reduced-scope language ("modify the audio waveform for volume... acceptable
  tradeoff"); revisit only if the knob feels non-linear in the cockpit.
- **Stage 2 changes an existing test's expected payload.** `test_ptt.py`'s
  `test_serves_the_raw_value_and_both_predicates` doesn't wire a `Spu8Cache`, so under Decision 3
  it will start seeing `"intercom": False` instead of `True` for the same input — this is the
  correct new behaviour (fail-safe-closed default), and the test must be updated (push an
  open `Spu8Sample`) rather than treated as a regression to chase.
- **The cross-seat write (664) was demonstrated once, on the ground, in one mission** (2026-10-05
  probe). The mechanism is the same one BL-6 already ships, so risk is low, but Stage 4's live
  acceptance is the first time it's exercised unattended/automatically rather than via a manual
  probe script.

### Second-Order Effect

This slice hard-codes two independent automatic triggers (mission-start timer, ground altitude)
straight into `silenced`/a single cockpit write, with no shared "automatic behaviour" abstraction
between them — reasonable now, but the user has already flagged intent to add "more logic on what
and when" to silent mode later; that future work will likely want to generalize past a single
one-shot boolean, and this plan does not build toward that generalization, only satisfies today's
simpler spec.
