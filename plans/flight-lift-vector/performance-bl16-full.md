### Performance Review — BL-16 cumulative (all stages)

Petrobrain is a hobby add-on for the DCS World flight-simulation video game (Mi-24P, AI copilot
"Petrovich"); everything below is simulated game logic, nothing controls real hardware.

Scope: the whole of BL-16 (`1561d370..cf03d63e`, ~249 commits, ~18k lines, 56 files) — mode 2
(AI-wheel), mode 1 (raw axes P0–P4, batch A, sortie fixes, takeover), the lift-vector law
(LV-0..LV-3), M3 (terrain floor/look-ahead) and M4 (SAU handover). Thirty-odd per-stage
performance passes already exist under `plans/flight-control/perf-*.md` and
`plans/flight-lift-vector/performance*.md`/`perf-plan-review.md`. This pass does **not** repeat
settled single-stage findings; it (a) verifies the NOW items those passes required were actually
built, (b) checks whether the accumulated MONITOR items now compound into something that crosses
into NOW once every stage is summed, and (c) measures the Export.lua per-frame cost as a whole
rather than per stage.

**Branch verified**: HEAD was an ancestor of the expected tip `cf03d63e`; fast-forwarded cleanly,
no mismatch to report.

### Prior NOW items — verified fixed in code (not re-flagged)

1. **`perf-batch-a.md` finding 1** (`run_ai_pilot_wheel`'s per-frame `list_indication(6)` read +
   full recursive-descent parse, running at DCS frame rate instead of the 5 Hz export gate) — the
   mitigation is in place: `Export.lua:461-465` calls only the cheap per-frame parts
   (`run_ai_pilot_wheel`'s release-deadline/park-edge checks); the device-6 read moved to the 5 Hz
   gate (`Export.lua:472-488`, one `get_helperai_indication()` call shared by both the overlay
   parse and `petrovich_indication`'s own push, confirmed by the comment at line 476 and the
   `helperai_raw` local it produces). Verified by reading the current file, not by trusting the
   plan's prose.
2. **`performance-m3.md`'s terrain-projection finding** (`run_active_frame` allocating `N+1` fresh
   `{d, T}` tables every DCS frame, ~140 Hz, when only `law_update` at ~30 Hz ever reads
   `measured.terrain`) — fixed: `flight_control.lua:3496-3511` now gates the whole projection
   block on the same `law_due(t, fc_law_last_update_t, flight_profile.ACTIVE)` test
   `run_active_frame`'s own call to `law_update` uses, with an explicit comment citing the finding
   number. The allocation now happens at ~30 Hz, not ~140 Hz — a 4.6x reduction in a cost that was
   already small (see measurement below).

### Cumulative Export.lua per-frame cost — measured, not estimated

The project's own `project_aircraft_layer_hotspots` memory flags that nothing in this repo has
ever measured raw `LoGet*`/`list_indication` call cost, which is DCS-engine-internal and
unmeasurable from here. What *is* measurable from here is the Lua-side compute BL-16 added on top
of those calls — table construction, trig, clamps — which is the part a Lua change actually
controls. Microbenchmarked with plain interpreted `lua` (5.5) and `luajit -joff` (interpreter-only
mode) as stand-ins for DCS's embedded Lua 5.1 — not bit-exact bytecode, but the right order of
magnitude for the operation mix (table literals, `math.*` calls, scalar arithmetic) that dominates
these functions; script and raw output are in this session's own scratch dir, not committed (the
numbers below are what matters, not the harness).

Counted real operation complexity rather than assuming it: `law_update` (flight_control.lua:1046-
1895, 850 lines) contains exactly 46 `math.*` calls total (16 `max`, 15 `abs`, 13 `min`, 1 `sqrt`,
1 `rad` — no `sin`/`cos`/`atan` at all), so it is cheaper than it looks from its line count: almost
entirely clamps and comparisons, not transcendental math.

| path | call site, cadence | measured cost (interpreted `lua`) | per-second cost at that cadence |
|---|---|---|---|
| `read_measured()` (22-field table build, ~9 `math.deg` calls) | every DCS frame, ~140 Hz | ~0.42 µs/call | ~59 µs/s |
| `law_outputs()` (scalar feedback combination, no alloc) | every DCS frame, ~140 Hz | ~0.04 µs/call | ~5 µs/s |
| `law_update()`-shaped load (trig+clamp mix, deliberately heavier than the real 46-call count) | gated to `law_hz` ≈ 30 Hz | ~0.3 µs/call | ~8.5 µs/s |
| terrain projection, 16-point grid, `{d,T}` tables | gated to `law_hz` ≈ 30 Hz (post-fix) | ~1.9 µs/call, 480 small tables/s | ~58 µs/s |

Summed, BL-16's entire Lua-side compute addition is on the order of **~130 µs of CPU per second**,
against a per-*frame* budget of ~7.1 ms at 140 fps (or ~16.7 ms at 60 fps) — three to four orders
of magnitude below a single frame, let alone a second of frames. This is the number the task asks
for ("per-frame µs and per-second garbage estimate for the whole, not per stage"): **not a
credible risk at any realistic DCS frame rate**, including on a slow machine running at 20-30 fps.
The table allocations (one 22-field table per frame from `read_measured`, ~16 small 2-field tables
per `law_hz` tick from the terrain projection) are the only GC-relevant additions; both are
fixed-size and bounded (never scale with contact count, mission size, or session length), so GC
pressure stays flat for the life of a sortie rather than growing.

**Action: none.** This closes the task's central question — the cumulative frame cost across all
of BL-16's stages is not where the project's performance risk lives. Confirmed MONITOR, not an
upgrade to NOW.

### Findings

#### Flight-trace logging does a blocking `write()` + `flush()` on the DCS render thread, ~30/s when the debug flag is on

- **Location:** `aircraft-layer/dcs-export/Petrobrain/flight_control.lua:2750-2762`
  (`flight_trace_log`), called from `run_flight_control:3738-3742` only when
  `estimator_due_this_frame` is true — i.e. at `law_hz` (~30 Hz), not every frame.
- **Risk:** `flight_trace_file:flush()` runs on every call when `FLIGHT_TRACE_ENABLED`. That is a
  genuine disk I/O syscall ~30 times/second on DCS's own render thread (not a background
  thread — `Export.lua` has none), which is exactly the "blocking the main thread" class this
  review is asked to look for. On a fast local SSD this is unlikely to be visible; on a
  Windows box with antivirus scanning the `Saved Games` tree, or a slower/networked drive, 30
  flushes/second is the kind of thing that produces an intermittent stutter specifically correlated
  with flying with the trace on — a debugging aid becoming itself the symptom being chased. This
  mirrors the project's own `aircraft_layer_slew_trace.log` pattern (`sight.lua`'s per-frame
  trace), which this review has no evidence runs any differently.
- **Action:** MONITOR, not NOW. `FLIGHT_TRACE_ENABLED` defaults off — this is the project's own
  established "testing aid, true no-op when absent" posture (root `CLAUDE.md` "Workflow"), and a
  flush-per-write is also the only way to guarantee the last line survives a crash, which is the
  whole point of a debugging trace. Worth a one-line note for whoever next flies with the trace
  on for an extended sortie: if a stutter shows up only with `FLIGHT_TRACE_ENABLED` set, this is
  where to look first, and the fix (buffer N lines, flush every M) is cheap when it's actually
  needed.

#### M4's four SAU-channel writes land in one poll — carried forward from its own review, not newly found

- **Location:** `body-layer/src/belief/effector_sequences.py` / `effector_engine.py` sequences
  for `controls-to-petrovich`/`controls-to-player` (H/K/T/B), `step-delay-s | 0`.
- **Risk:** Already measured and accepted in `plans/bl-b141-single-command-seq/performance.md`
  (APPROVED–MONITOR) — restated here only because the task asks for the cumulative picture: this
  is a body-layer poll-rate event (on a mode-1 take/hand-back), not a per-frame cost, and it is a
  fixed count of 4 writes regardless of mission size. Nothing about the rest of BL-16 changes that
  analysis.
- **Action:** MONITOR (unchanged) — `#needs-flight` per the roadmap entry; watch for a stutter at
  take on the live sortie, not before.

#### Rotor-RPM read is dormant, not yet costing what its code shape implies

- **Location:** `aircraft-layer/dcs-export/Petrobrain/flight_control.lua:371-406`
  (`read_rotor_rpm_pct`), called every active frame from `read_measured`.
- **Risk:** Carried forward from `project_bl16_mode1_rotor_rpm_seam_dormant_arg_proxy` (memory) —
  ships with `ROTOR_RPM_SOURCE = "dummy"`, so the one `GetDevice(0)`/`safe_call` closure this
  function could run never actually fires yet. Not a cost today; flagged so whoever flips the
  source to `"arg_proxy"` re-checks the per-frame read tally then, since that is the point this
  review's own per-frame table stops being free.
- **Action:** LATER (re-check only when the source flips, not now).

#### body-layer poll-loop additions across BL-16 — no new risk found

Checked `flight_authority.py` (`advance_flight_authority`, pure dict→dataclass parsing of the
`flight_desired` sample, no I/O of its own), `terrain_ahead.py` (`compose_terrain_grid`/
`build_terrain_relay`, pure geometry + string encode, bounded at `MAX_TERRAIN_POINTS = 32`, sent
once per poll via the existing `aircraft_client` HTTP call body.py already makes every poll — not
an added network round trip), and the effector-engine's SAU sequence advance (bounded queue drain,
no full-dataset scan). All are poll-rate (≈5 Hz class), not per-frame; none iterates a
mission-sized collection; none adds a blocking call beyond the network I/O the poll loop already
performs on its own thread each cycle. Nothing here compounds with the Export.lua side — the two
run on separate processes/threads by construction (LAN HTTP boundary).

### Verdict

APPROVED — MONITOR

The cumulative Lua-side per-frame/per-poll cost BL-16 added across all of mode 1, mode 2, the
lift-vector law, M3 and M4 is measured at roughly ~130 µs of CPU per second against a multi-
millisecond-per-frame budget — not a credible risk at any realistic frame rate, and every prior
NOW finding (batch-a's `list_indication` call-rate fix, M3's terrain-projection frequency fix) is
confirmed present in the current code by direct read. The two open MONITOR items (flight-trace
flush frequency, the SAU four-write batch) are both debug-flag-gated or fixed-count, cannot grow
with mission size or session length, and do not compound with anything else in this diff. No
change is required before DoD.
