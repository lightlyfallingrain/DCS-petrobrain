### Performance Review

Batch: BL-16 parked-mode Stages P-ICS, P0 probe, P1. Diff reviewed: `fde7398e..618ec14f`.
Scope: the Reviewer's flagged `run_ai_pilot_wheel` per-frame cost
(`plans/flight-control/review-batch-a.md` "Hand to performance-reviewer"), plus the body-layer
poll-loop addition and `GET /ai_pilot_wheel/latest`.

### Findings

#### `run_ai_pilot_wheel`'s per-frame `list_indication(6)` read + full recursive-descent parse

- **Location:** `aircraft-layer/dcs-export/Export.lua:2164-2221` (`run_ai_pilot_wheel`), called
  unconditionally every `LuaExportAfterNextFrame` at line 2597, **above** the 5 Hz
  `last_export_t` gate at line 2599 — so it runs on DCS's own render thread at full frame rate
  (60-120 fps), not 5 Hz. While parked (`now_parked == true`, the sortie's normal "autopilot
  flying, crew busy" state — likely the common case, not a rare edge), every frame it calls
  `get_helperai_indication()` → `list_indication(HELPERAI_DEVICE_ID)` (line 2199) and then runs
  `parse_helperai_overlay_fields` (lines 2050-2097), a full recursive-descent walk of the entire
  returned dump, every frame.
- **Risk:** Two compounding costs, both real, neither invented beyond what the diff shows:
  1. **Call-rate multiplier is certain regardless of the per-call cost.** `HELPERAI_DEVICE_ID`
     (device 6) is the *same* device the existing 5 Hz `petrovich_indication` push already reads
     (`aircraft-layer/dcs-export/Export.lua:2741`, `get_helperai_indication()` again) — confirmed
     by `aircraft-layer/CLAUDE.md`'s own description of that feed and by the research note
     (`aircraft-layer/research/2026-11-14-mi24p-ai-pilot-wheel-layout.md` §3-4): device 6's one
     dump carries both Petrovich's detection-text leaves (`middle_list_text` etc.) and the AI-wheel
     overlay leaves (`mode_text`/`alt_text`/`course_text`/`alt_add_text`/`speed_text`) in one tree.
     This stage adds a **second caller of the same expensive device read, at 12-24x the rate**
     the project already treats as "the conservative starting rate" (`Export.lua:201`,
     `EXPORT_INTERVAL_S = 0.2`). `.claude/agent-memory/performance-reviewer/
     project_aircraft_layer_hotspots.md` already flags `list_indication()`'s own per-call DCS
     cost as **unmeasured anywhere in this repo**, and separately flags that `Export.lua` runs on
     DCS's own thread, where cost means cockpit stutter, not service latency — not a budget this
     phase has a number for, but exactly the risk class that memo says not to multiply blind.
  2. **The parse itself is full-dataset-shaped, not bounded-query-shaped.** `parse_
     helperai_overlay_fields` walks every node in the dump to pull five scalar leaves, and the
     dump it walks is the same one carrying however many detection-text nodes the scene currently
     has — so the per-frame cost does not stay flat as contact count grows, it was simply never
     exercised at scale because the fixture sorties used so far are small (same caveat the hotspots
     memo already raises for `list_indication` generally).
  3. **Nothing in the per-frame result is used per-frame.** `ai_pilot_mode_text`/`course_text`/
     `alt_text`/`alt_add_text`/`speed_text` are written to module locals every frame but read only
     at (a) the 5 Hz `push_ai_pilot_wheel_state` (line 2227) and (b) the one-shot nudge check on
     the rising edge (lines 2210-2219). The per-frame read+parse produces 11-23 discarded results
     for every one actually used.
- **Action:** NOW.
- **Mitigation:** Move the `get_helperai_indication()` call and `parse_helperai_overlay_fields`
  call out of `run_ai_pilot_wheel` and into the existing 5 Hz-gated block (same call site as
  `push_ai_pilot_wheel_state`, line 2606-2608), and have it reuse the *same* `list_indication(6)`
  read the existing `petrovich_indication` push at line 2741 already performs this tick — one
  device read per 5 Hz tick serving both feeds, instead of two separate reads (one per frame, one
  at 5 Hz). `run_ai_pilot_wheel` itself keeps only what is genuinely per-frame: the release-on-
  deadline check (a plain `t` comparison, no DCS call) and park-rising-edge detection (two cheap
  `get_argument_value` reads, not `list_indication`). On a rising edge, set a one-frame-lived
  pending-nudge flag instead of reading/parsing immediately; the next 5 Hz tick's freshly-parsed
  fields perform the actual `ai_pilot_should_nudge_altitude` comparison and clear the flag. This
  defers the one-shot nudge decision by at most one 5 Hz tick (≤200 ms) against a mechanical
  altitude-hold sink that unfolds over seconds — not a credible correctness cost, and explicitly
  not the 9K113 slew's continuous-servo timing class (`plans/9k113-sight-pointing/plan.md`), which
  is the precedent that actually justifies a true per-frame budget elsewhere in this file.

#### P2's "release when readback reaches target" — don't re-introduce the per-frame pattern

- **Location:** not yet implemented — `plans/flight-control/plan.md` Stage P2 ("released once
  the readback is within tolerance or the body-layer goal changes").
- **Risk:** If P2 is built by copying P1's current shape, the fix above gets undone the moment a
  long-hold press needs to watch the readback converge — "release on tolerance" reads like it
  wants a per-frame comparison. It likely does not: the AI-wheel's heading/altitude/speed fields
  advance in discrete, human-press-rate steps (confirmed by the wheel-layout research), not a
  continuously-moving analog value the way the 9K113 sight servo does. A 5 Hz comparison means at
  most one extra ~200 ms of an already-coarse-stepped hold before release — the same order of
  slack the mitigation above already accepts for the one-shot nudge.
- **Action:** MONITOR — flag to Architect/Implementer before P2 lands code, so the per-frame
  decision is made deliberately rather than inherited from P1's current (soon-to-be-fixed) shape.
  If a live P2 test shows visible overshoot at 5 Hz, that is the trigger to revisit, not an
  assumption to build around now.

#### Body-layer poll-loop addition (`advance_parked_flight_state`, `GET /ai_pilot_wheel/latest`)

- **Location:** `body-layer/src/belief/ai_pilot_wheel.py:84-105`, `body-layer/src/body.py:4330-4333`,
  `body-layer/src/aircraft_client.py:456-471`.
- **Risk:** None credible. One `GET` + one small-dict parse + one frozen-dataclass `replace`-style
  reconstruction, once per body-layer poll (5 Hz class, not per-frame) — the same "most-recent
  cache, cheap bounded `.to_dict()` on GET" shape the project's own hotspots memo already clears
  for the sibling `/telemetry/latest`-style endpoints. No full-dataset iteration, no per-request
  allocation beyond one small object, no blocking I/O on a thread other than the poll thread that
  already blocks on its own network calls each poll.
- **Action:** MONITOR (no action needed; noted for completeness since the batch's own instructions
  asked for the body-layer side explicitly).

### Verdict
NEEDS MITIGATION
