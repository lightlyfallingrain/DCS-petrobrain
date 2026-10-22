> **SUPERSEDED 2026-10-22 by `plan.md` (v2)** — this plan assumed the AI axis is a position target with 874/876 as readback and the DCS AI overlay kept on; probe runs 1–10 overturned all three.

# BL-B80 — pointing the real 9K113 sight at Petrovich's modelled aim

## Goal

Make the real 9K113 sight head follow Petrovich's belief-side desired aim (`OpticState.
look_azimuth_deg`/`look_elevation_deg`), on the channel the 2026-10-21 probes settled: the AI axis
(device 7, `SetCommand(3061, …)`/`SetCommand(3060, …)`), a position target that works only while
DCS's own AI Petrovich is on and only while re-asserted every frame — and keep DCS's AI enabled and
the real readback flowing without the player ever seeing a wheel, while Petrovich's own sight
perception reads only where the head has actually reached.

## What is settled, and what this plan must still decide

Settled by the 2026-10-21 probes and the 2026-10-21/22 user direction (`explore-notes.md`, `BL-B80.md`'s
SUPERSEDED block): the channel, the "AI Petrovich on + re-assert every frame" conditions, that
Petrovich always holds the sight while OBSERV is on (idle included), that his side effects are
accepted, and that perception must read the actual position, never the desired one.

Not yet decided by anyone: how the per-frame reassertion and rate limit are split between
Export.lua (the only thing running every frame) and body-layer (which owns the desired aim and
polls at ~1 Hz) — this plan makes that split explicit below, because it is the one architectural
question the inputs leave open.

## Architecture: who owns what, and why

**Export.lua becomes the per-frame sight owner. Body-layer stays the once-per-poll aim-setter.**
This is forced, not chosen: the 2026-10-21 findings are that a single write is overwritten by ED's
AI (needs re-assertion every frame) and that the only readable position (874/876) is only
trustworthy under those same frame-rate conditions. Body-layer's poll loop runs at ~1–5 Hz; nothing
it does can reassert at 150 fps. So:

- **Export.lua** caches the last target body-layer sent, rate-limits a *commanded* value toward it
  every frame (mimicking the 20°/s az / 10°/s el slew the AI axis would show if driven for real —
  derived from `Devices_specs/9K113.lua`'s `h_axis_velocity`/`v_axis_velocity`, the same source
  already cited for the player axis in `mi24p-command-surface.md` §4.2), writes that commanded
  value to the AI axis every frame while OBSERV reads on, and runs the AI-on/off detector and the
  gyro-alignment suppression (both below) — all of this needs frame-rate reaction and a round trip
  through body-layer's poll loop cannot give it that.
- **Body-layer** computes the desired aim once per poll (unchanged — `optic_policy.decide`'s
  existing SIGHTING cycle), sends it to Export.lua as a new persistent target, and reads back the
  real position (already flowing via `GET /cockpit_switch/latest`'s `sight_az`/`sight_elev`) for
  perception and for `OpticState.actual_aim_*_deg`.

This reuses the existing seam (`AircraftLayerClient` HTTP ↔ collector ↔ loopback UDP ↔ Export.lua,
`aircraft-layer/CLAUDE.md` "What this is") and the existing wire shape (`CommandSender`'s one
method per op — `send_command`/`send_cockpit_switch`/`send_look_direction`). It does **not** reuse
the `cockpit_switch` op: that op's semantics are "write once now" (`performClickableAction`), and
conflating it with "hold and rate-limit toward this target forever" under one op would make the
same op mean two different persistence models depending on which device/cmd pair is sent. A third,
small, named op (**reuse the op mechanism's shape, not the switch op's semantics**) is the one
place this plan departs from "do not reinvent the wheel" in the transport layer, and the reason is
stated: no existing op holds state across frames.

**Elevation's command→degree conversion is derived, not independently probed, and that is this
plan's one real unknown — see Risks.**

## Affected Modules / Files

- `aircraft-layer/dcs-export/Export.lua` — new per-frame sight-owner state machine: cached target,
  rate-limited commanded value, per-frame AI-axis reassertion (`point_quiet`, the proven mechanism
  from `Export.probe-9k113-point.lua`), the AI-on/off detector, the gyro-alignment suppression
  window, `EXPORT_SCRIPT_VERSION` bump.
- `aircraft-layer/src/collector/command_sender.py` — `CommandSender.send_sight_target(az_cmd,
  elev_cmd)`, same shape as `send_cockpit_switch`/`send_look_direction`.
- `aircraft-layer/src/api/` — `POST /command/sight_target`, same shape as `/command/cockpit_switch`.
- `aircraft-layer/src/collector/server.py` — `EXPECTED_EXPORT_VERSION` bump (paired commit with the
  Export.lua version bump, per that file's own convention).
- `body-layer/src/aircraft_client.py` — `AircraftLayerClient.write_sight_target(az_cmd, elev_cmd)`.
- `body-layer/src/belief/sight_effector.py` — the new degree↔raw conversion functions (azimuth's
  inverse, plus both elevation directions), `GuidanceUnitState.observ_observed_since_sim` (new
  field, for the gyro-alignment window), `in_gyro_alignment()`, the write-through for the new op.
- `body-layer/src/logger.py` — sends the sight target every poll while `home_phase is SIGHTING`;
  the observed-arg-886-driven `home_phase` transition (closing the carried-forward BL-B66 gap);
  the gyro-alignment cap on `optic_decision.optic` in `run_once`, immediately after `decide_optic`
  returns and before it is assigned; `advance_sight_aim`'s call site reading the real readback when
  present, falling back to today's pass-through model otherwise.
- `body-layer/src/belief/optic_policy.py` — `advance_sight_aim`'s body (was `return desired`):
  prefers the real readback (converted via `sight_effector`'s new functions) over the model, same
  split `sight_trace_writer.py` already documents and expects.
- `body-layer/src/sight_trace_writer.py` — elevation gains an `actual_elevation_source ==
  "readback"` path once the conversion exists; no shape change otherwise.
- `body-layer/src/tuning.py` / `config/defaults.toml` — `GYRO_ALIGNMENT_S` (new tunable).
- `aircraft-layer/research/2026-10-22-9k113-ai-latency-probe-findings.md` — the probe this plan is
  staged to consume once flown (not written by this plan).

## Co-moving Fields

Two separate state machines, each spanning command (external) and observed (internal/derived)
fields, built by grepping every construction site (`OpticState(` has two fresh-construction sites
in `optic_policy.py`, both already carry the BL-B71 "replace, never construct fresh" rule in
comment; `GuidanceUnitState(` has one, in `logger.py`'s `default_factory` — no other site to worry
about there).

**Body-layer (`OpticState.phase`/`home_phase`, `GuidanceUnitState.observ_commanded`/
`observ_observed`/`observ_observed_since_sim`):**

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| `home_phase` | **changes in this plan**: today the pilot's "Observ on"/"off" command (internal, one-shot signal in `logger.py`); **must become** the observed arg-886 edge (`guidance_unit_state.observ_observed`) | OBSERV reads on (observed) | `home_phase is SIGHTING` |
| `home_phase` | as above | OBSERV reads off (observed, whoever caused it — pilot, DCS auto-off on hard manoeuvre, or our own write) | `home_phase is SCANNING` |
| `phase` | internal (`decide`'s own dispatch, `_back_to_home`) | any `home_phase` transition | moves to match `home_phase` only at the next phase boundary — unchanged by this plan, already correct per the BL-B71 precedent (`_apply_guidance_override` re-derives from `home_phase` fresh every call, never caches) |
| `observ_observed_since_sim` (new field) | `sight_effector.refresh_readback`, on the rising edge of `observ_observed` | OBSERV reads on (observed) | holds the sim time of that edge until the next edge |
| the sight-tier optic cap in `run_once` | **new**, immediately after `decide_optic` | `now_sim - observ_observed_since_sim < GYRO_ALIGNMENT_S` | `optic_decision.optic` is capped to `BINOCULAR_OPTIC` if `decide_optic` chose a sight-tier optic — same cap target `_apply_guidance_override` already uses when `home_phase is not SIGHTING`, re-derived every poll, never latched |

**Export.lua (new, entirely local to the per-frame loop):**

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| `target_az_deg`/`target_elev_cmd` | the `sight_target` command (external, from body-layer, persists across frames) | a new `sight_target` datagram arrives | holds until replaced or OBSERV reads off |
| `commanded_az_cmd`/`commanded_elev_cmd` | internal, rate-limited every frame toward `target_*` | every frame while OBSERV reads on | moves at most `rate × dt` per frame toward the target, never jumps |
| `ai_off_since` (detector timer) | internal, from the 874/876-vs-commanded comparison | commanded is non-trivial and 874/876 stay near 0 | accumulates only while **outside** the gyro-alignment window (below) |
| `observ_on_since` | internal, OBSERV (886) rising edge, read every frame | OBSERV reads on | gates the detector (`ai_off_since` does not start accumulating until `t - observ_on_since >= GYRO_ALIGNMENT_S`) |
| ShowMenu press | internal, fired when `ai_off_since` exceeds the timeout | detector fires | one press, then the timer resets and `ai_off_since` starts over — never fires while inside the alignment window, by construction (it never started accumulating) |
| all of the above | internal, OBSERV (886) falling edge | OBSERV reads off | `target_*`/`commanded_*`/`ai_off_since`/`observ_on_since` all reset to `nil` — a stale target must never survive to the next OBSERV-on |

## Implementation Plan

1. **Elevation calibration + the carried-forward BL-B66 gap (body-layer only, no cockpit write
   changes, testable without DCS).**
   - Add `sight_elevation_raw_to_deg`/`sight_elevation_deg_to_raw` to `sight_effector.py`, derived
     from two already-sourced facts: the manual's physical limits (`regard_elevation_up_deg=20.0`,
     `regard_elevation_down_deg=-15.0`, `optics.py`'s own sourced comment) and the measured
     piecewise gauge split (`arg_876`: value for value ≥ 0, `0.75 × value` for value < 0,
     `2026-10-21-9k113-slew-readback-probe-findings.md` table). The two combine to one linear
     formula, `elevation_deg = arg_876 × 20.0`, both signs (value=+1 → arg=+1.0 → 20°, matching the
     sourced up-limit exactly; value=−1 → arg=−0.75 → −15°, matching the sourced down-limit
     exactly) — and its inverse for the command direction (`value = elevation_deg / 20.0` for
     elevation_deg ≥ 0, `value = elevation_deg / 15.0` for elevation_deg < 0). **Mark this
     `status="derived"`, not `"measured"`**, in whatever doc-comment convention
     `_SIGHT_AZIMUTH_DEG_PER_RAW_UNIT` uses — it fits every data point on record but was never
     independently probed (see Risks).
   - Add `sight_azimuth_deg_to_raw` (azimuth's existing conversion only runs raw→deg today).
   - Add `GuidanceUnitState.observ_observed_since_sim: float | None`, set by `refresh_readback` on
     the rising edge of `observ_observed` (comparing the previous value before the `replace()`),
     cleared to `None` on the falling edge, `None` until the first sample ever arrives.
   - Add `sight_effector.in_gyro_alignment(state, now_sim) -> bool`:
     `state.observ_observed_since_sim is not None and now_sim - state.observ_observed_since_sim <
     GYRO_ALIGNMENT_S`.
   - `GYRO_ALIGNMENT_S: Final[float] = tuning.real("belief.sight_effector.GYRO_ALIGNMENT_S", 10.0,
     lo=5.0, hi=20.0, status="measured")` — sourced from `2026-09-11-SUMMARY-petrovich-control.md`
     ("every ON costs the ~10 s gyro alignment") and the fresh verbatim direction this plan
     responds to.
   - In `logger.py`'s `crew_console.observ_transition` handling (the block that currently sets
     `home_phase=OpticPhase.SIGHTING`/`SCANNING` synchronously with the command): **stop setting
     `home_phase` there.** Instead, derive `home_phase` from `runner.guidance_unit_state.
     observ_observed` on every poll, in the same place `_apply_active_gaze`/`decide_optic` is
     called — rising edge → `home_phase=SIGHTING`, falling edge → `home_phase=SCANNING`, re-checked
     fresh every poll (mirrors the `_apply_guidance_override` precedent the Co-moving Fields table
     cites). The command (`observ_transition`) still drives the cockpit write and the hands-busy
     suppression exactly as today — those are about the pilot's/Petrovich's hand moving to the
     switch, which is tied to the command event, not the observed edge.
   - Immediately after `decide_optic(...)` returns in `run_once`, before `self.optic =
     optic_decision.optic`: if `optic_decision.optic` is `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC` and
     `in_gyro_alignment(self.guidance_unit_state, ownship.t_sim)`, replace `optic_decision` with
     `optic` capped to `BINOCULAR_OPTIC` — same cap value `_apply_guidance_override` already uses
     for "home_phase is not SIGHTING", same "never cached, re-derived every poll" property. This is
     the "Petrovich must not perceive through the sight during alignment" requirement; `home_phase`
     itself is already `SIGHTING` (set above) so the cap is the only thing stopping perception —
     the moment the window ends, the very next poll's cap check passes with no special-casing.
   - Tests: `in_gyro_alignment` pure-function unit tests at the window's edges; a `run_once`-level
     test that an OBSERV-on edge followed immediately by a poll inside the window never yields
     `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC` even when `decide_optic` would otherwise choose one;
     one test confirming a falling-then-rising edge resets `observ_observed_since_sim` (no stale
     window from a previous OBSERV-on).

2. **The wire op and the Export.lua per-frame loop (needs a Windows redeploy to test live).**
   - `aircraft-layer/src/api/`: `POST /command/sight_target` taking `{"az_cmd": float, "elev_cmd":
     float}`, forwarding to `CommandSender.send_sight_target`, same validation/shape posture as
     `/command/cockpit_switch`.
   - `Export.lua`: a new inbound op `"sight_target"` in `poll_command_socket`, storing
     `target_az_cmd`/`target_elev_cmd` (persists across frames, like `pending_release_t` already
     does for a different purpose).
   - New per-frame function, called from `LuaExportAfterNextFrame` alongside `push_cockpit_switch_
     state`/`push_slew_trace`, gated on `observ_on` (read once per frame, as those two already do):
     - Rate-limit `commanded_az_cmd`/`commanded_elev_cmd` toward `target_az_cmd`/`target_elev_cmd`
       by at most `rate × dt` (az: `20°/60/s` in command-value units since `value = deg/60`; elev:
       convert similarly using the body-layer-side formula's inverse — **or**, simpler and avoiding
       a second elevation conversion inside Lua, have body-layer send the elevation *rate limit* in
       the same raw command units it already uses for the target, i.e. body-layer computes `10°/s`
       in raw-value units via its own conversion and Export.lua receives a plain command-value step
       size; **decide this at implementation time, default to the Lua-side conversion** since it
       keeps Export.lua self-contained and the rate constant never changes at runtime).
     - Bias the write: if the commanded value is within a small deadband of centre on both axes,
       offset the azimuth write by the fixed 0.5° (named constant) the explore notes specify, so the
       AI-off detector below is never comparing against an ambiguous all-zero target. The *tracked*
       `commanded_az_cmd` state is never biased, only the value passed to `point_quiet` that frame.
     - Call `point_quiet(commanded_az_cmd, commanded_elev_cmd)` every frame (the proven mechanism
       from the pointing probe).
   - AI-on/off detector, same per-frame function, gated the same way:
     - `observ_on_since`: set on the OBSERV rising edge (mirrors `slew_trace_observ_off_since`'s
       existing shape, inverted).
     - Only while `t - observ_on_since >= GYRO_ALIGNMENT_S` (a **Lua-side literal**, commented as
       mirroring `body-layer`'s `GYRO_ALIGNMENT_S` tunable — "Lua-side constants cannot use
       `tuning.py`; keep this value in sync by hand if that one changes," the same cross-file
       convention `EXPORT_SCRIPT_VERSION`/`EXPECTED_EXPORT_VERSION` already uses), accumulate
       `ai_off_since` whenever the commanded target is non-trivial and 874/876 read near 0.
     - On `ai_off_since` exceeding a timeout constant (placeholder default, flagged below — the
       2026-10-22 probe is what should set this), press `ShowMenu` (device 30, cmd `WHEEL_MENU_
       BUTTON`, the same constant `handle_petrovich_search_command` already uses) once, reset
       `ai_off_since`, and do not press again until a re-press interval constant has elapsed.
   - On the OBSERV falling edge: clear `target_*`/`commanded_*`/`ai_off_since`/`observ_on_since` to
     `nil` — the Co-moving Fields table's last row.
   - `EXPORT_SCRIPT_VERSION` bump; `aircraft-layer/src/collector/server.py`'s
     `EXPECTED_EXPORT_VERSION` bump in the same commit.
   - **Placeholder timeout/re-press values, explicitly flagged as provisional**: until the
     2026-10-22 latency probe reports, use the explore notes' own stated figure (~0.5 s stuck-at-
     zero before concluding AI is off) for the timeout, and a conservative re-press interval (e.g.
     2–3 s) so a single missed detection does not spam `ShowMenu`. **Both numbers should be
     revisited the moment that probe lands** — this is this plan's second open risk.

3. **Body-layer sends the target, every poll, and reads the real position back.**
   - `AircraftLayerClient.write_sight_target(az_cmd, elev_cmd)`, raising on failure like
     `write_cockpit_switch` — same posture, same caller-decides-what-to-do-with-a-failure division.
   - In `logger.py`'s poll loop, whenever `home_phase is SIGHTING` (post-alignment-cap, i.e. this
     runs regardless of the cap in step 1 — the cap only affects *perception*, not whether the head
     is told where Petrovich eventually wants to look; the head should already be most of the way
     there by the time alignment ends): convert `OpticState.look_azimuth_deg`/`look_elevation_deg`
     to raw command values via the Stage 1 conversions, call `write_sight_target`. **Always send a
     target while `home_phase is SIGHTING`, idle included** — the 9k113-narrow-search follow-on
     already guarantees the idle sight carries a real in-regard aim, so there is always something
     valid to send; this satisfies "always holds the sight… idle included" without a special case.
   - `advance_sight_aim` (today `return desired`): prefer the real readback
     (`sight_az_raw`/`sight_elev_raw`, converted via Stage 1's functions) when both are present;
     fall back to today's pass-through model otherwise (no readback yet this mission, or an older
     Export.lua). This is exactly the split `sight_trace_writer.py` already documents and expects —
     that file's `actual_elevation_source` only ever said `"model"` because no elevation conversion
     existed; after Stage 1 it can say `"readback"` too, no shape change to the writer itself.
   - Tests: `advance_sight_aim` prefers readback when present; falls back cleanly when absent;
     `sight_trace_writer` rows show `actual_elevation_source == "readback"` once both the
     conversion and a raw sample exist (extend its existing fixture-based tests, don't rewrite
     them).

4. **Acceptance (live sortie, Windows).**
   - Fly an OBSERV-on with the pilot watching the ASP-17 crosshair, confirming smooth motion (no
     1 Hz jumps) toward a few known bearings, same visual-check pattern the 2026-10-21 probe already
     used for azimuth.
   - **Verify the elevation calibration live**: command the two physical stops (+20°/−15°) and
     confirm the pilot sees the sight hit its mechanical limit at each, not short of it or past it
     — this is the one independent check the derived formula has not yet had.
   - Verify the gyro-alignment window: toggle OBSERV off then on, confirm (a) no spurious `ShowMenu`
     press fires during the ~10 s window even though 874/876 necessarily read near 0 through it, and
     (b) Petrovich does not report anything through the sight until the window has elapsed.
   - Observe ordinary flight for spurious `ShowMenu` presses outside any deliberate test — the
     detector should never fire when DCS's own AI Petrovich is in fact on and tracking.
   - Confirm `home_phase` now follows DCS's own automatic OBSERV-off (hard manoeuvre) rather than
     only the player's spoken command — this is the carried-forward BL-B66 gap's own acceptance
     test.

## Risks & Unknowns

- **Elevation's degree conversion is derived, not independently measured.** It fits every data
  point currently on record (the sourced ±20°/−15° physical limits, the measured piecewise gauge
  split) with no free parameter, but `CockpitMi24.dll`'s own true angle is native and unreachable
  from Lua (`mi24p-command-surface.md` §4.1), so no further file-grep or Investigator pass can
  close this — only a live check against the known mechanical stops (Stage 4) can. Flagged, not
  blocking: the formula is the best available account of sourced data, and the azimuth conversion
  was accepted on the same "sanity-check live" basis.
- **The AI-off detection timeout and re-press interval are placeholders** pending the 2026-10-22
  latency probe (not yet flown as of this plan). Shipping with a provisional value means the
  detector could be slower or twitchier than necessary until that probe lands and the Lua-side
  constants are revisited.
- **Rate-limiting elevation in raw command-value units inside Export.lua** needs the elevation
  rate (10°/s) converted through the same derived (not measured) formula — compounding the first
  risk onto the rate, not just the position. Keeping that conversion on the body-layer side (second
  bullet of Stage 2) avoids introducing a second derived-conversion site in Lua, at the cost of
  sending a rate rather than letting Export.lua own the whole physical model; worth revisiting once
  Stage 4 confirms or corrects the conversion.
- **A stray `ShowMenu` press is a cockpit-visible side effect** (it opens Petrovich's AI wheel,
  however briefly, with the wheel hidden in settings this should be invisible, but has not been
  confirmed invisible with the wheel hidden *while a press fires mid-flight* rather than at mission
  start). Low risk, flagged for the acceptance sortie to specifically watch for.
- **No automated test reaches `Export.lua` itself** (per `aircraft-layer/CLAUDE.md`'s own
  "Structure" section — this subproject's standing limitation, not new to this plan). Everything in
  Stage 2 is validated live only.

## Coordinator amendments (2026-10-22) — these override the text above where they differ

1. **Overlay OFF with OBSERV OFF was missing.** The user direction is explicit: *"Turn overlay OFF
   with OBSERV OFF."* ShowMenu is a toggle and, with OBSERV off, the readback cannot say whether
   DCS's AI is on. So Export.lua keeps `ai_believed_on`: true once the readback has obeyed a
   non-trivial target after alignment, false after a detector press that has not yet been
   confirmed by the readback obeying again. On the OBSERV falling edge, press ShowMenu once **only
   if `ai_believed_on`**, then clear it. If unsure, do not press — a wrongly-left-on overlay is
   harmless with the wheel hidden; a wrongly-pressed one turns DCS's AI on with nobody holding the
   sight.
2. **Decision 3 (proactive press) is settled by the same direction: reactive only.** The detector
   runs from the moment the alignment window ends, so *"Turn AI overlay ON with OBSERV ON"* is met
   within one timeout of the sight becoming usable. A blind proactive press would turn the AI
   **off** whenever it was already on, because the press toggles.
3. **A false detector fire corrects itself**, and the implementation must keep it that way: a press
   while the AI was in fact on turns it off, the readback drops to 0, and after the re-press
   interval the detector presses again. Never latch the detector off after N presses.
4. **Elevation rate lives in Export.lua** (Stage 2's default, not the Risks section's alternative):
   10°/s is 0.5 raw/s above centre (20°/unit) and 0.667 raw/s below (15°/unit). The rate is a mimic
   of the slew, so the derived-formula risk on it is cosmetic.
5. **Decisions 1 and 2 taken as recommended**: ship the derived elevation formula and verify it at
   the two mechanical stops in Stage 4; ship placeholder detector timing (0.5 s timeout, 2.5 s
   re-press) and retune from the 2026-10-22 latency probe.
6. **Batching**: Stages 1–3 are one implementation batch (one performance and one security pass
   after Stage 3); Stage 4 is the sortie.

## Decisions Requiring User Input (answered — see amendments 2 and 5)

- **Ship the derived elevation formula now, verified live in Stage 4, or hold Stage 1/3's elevation
  work until a dedicated calibration probe runs first?** Recommendation: ship and verify live — the
  formula has no free parameter and the live check is cheap (two known mechanical stops), the same
  basis azimuth's own conversion was accepted on.
- **Ship Stage 2 with placeholder AI-off-detection timing, or wait for the 2026-10-22 probe?**
  Recommendation: ship with the explore notes' own stated ~0.5 s timeout and a conservative re-press
  interval, and treat the probe's numbers as a follow-up tuning pass rather than a blocker — the
  detector's correctness (does it ever fire when it should not) does not depend on the exact
  timeout value, only its responsiveness does.
- **Should Export.lua press `ShowMenu` proactively once, the moment the gyro-alignment window
  elapses on a fresh OBSERV-on, rather than waiting passively for the reactive detector's first
  timeout?** This plan's default (Stage 2) is reactive-only, per the explore notes' own wording
  ("press ShowMenu once and recheck" describes the detector's response, not a proactive act). A
  proactive press would shave the detector's own timeout off the first engagement of a sortie, at
  the cost of one more cockpit-visible press on every single OBSERV-on regardless of whether DCS's
  AI was already on. Flagging rather than deciding, since the explore notes do not settle it either
  way.

## Second-order effect

`[[BL-B67]]` (the ATGM run) is what this unblocks — it needs a real, trustworthy pointing channel
to keep the sight on a moving target, and this plan is the one that makes "the head is actually
where Petrovich says it is" true rather than simulated. It also narrows `BL-B67`'s own design: the
elevation calibration this plan derives (and Stage 4 verifies) becomes the number that run's
guidance accuracy is built on, so if Stage 4 finds the derived formula wrong, that correction must
land here before `BL-B67` is planned, not after.
