# Slip ball (sideslip) recon for BL-16 mode 1's pedal law

**Date:** 2026-11-20
**DCS version:** not verified locally this session — no DCS install reachable (Mac dev machine,
`DCS_INSTALL_PATH` unset). This project's own most recent live-confirmed version for this cockpit
surface is **2.9.29.27278** (`mi24p-command-surface.md` header); treat anything below that is not
separately marked "cross-checked" as unverified against the *current* install.
**Theatre:** n/a — cockpit/scripting-API question, not terrain.

### Question

User direction, 2026-11-20 (`docs/acceptance/2026-11-20-sortie-feedback.md`): *"we need a to read
the slip ball as one of the important values since it guides pedal adjustmens."* BL-16 mode 1's
pedal law (`aircraft-layer/dcs-export/Petrobrain/flight_control.lua`, Step 5) currently runs on a
collective-coupling feedforward only (`K_PEDAL_FROM_COLLECTIVE_RATE`) — the law's own `K_beta`
term (ball-centring feedback, plan step 5: `u_y_dot = K_beta*beta + K_cy*u_c_dot`) was never
implemented, flagged in the module's own comment: *"`LoGetSlipBallPosition` exists (confirmed in
the DCS Control API reference) but its return shape/units were never measured by any probe... so
guessing a unit conversion here risks a wrong-sign pedal command."* This note resolves what is
knowable from documentation/community sources before a live probe, and designs that probe.

### Findings

**(a) `Export.LoGetSlipBallPosition()` / `Export.LoGetAngleOfSideSlip()` — the Lo-API route**

- **Both names exist in this project's own shipped API reference, in the `allow_ownship_export`
  tier, alongside every other confirmed-live getter** (`LoGetSelfData`, `LoGetADIPitchBankYaw`,
  `LoGetRadarAltimeter`) — **evidence: reproduced-locally (symbol existence only)** — **source:**
  `aircraft-layer/research/reference/Sim_ControlAPI.md:519,531`.
- **No official return shape, units, or sign convention for either call was found anywhere** —
  not in ED's own material, not on the Hoggit wiki (`wiki.hoggitworld.com/view/DCS_export` lists
  both names under "Ownship" with no further detail), not in any community export project found
  this session (`s-d-a/DCS-ExportScripts`, `jboecker/dcs-export-core` — neither documents or uses
  either name in anything surfaced by search). — **evidence: absent.**
- **One forum snippet (via WebSearch, not independently fetched — 403'd, see Unresolved) gives a
  range for `LoGetSlipBallPosition`**: a poster's own Export.lua comment reads *"(args - 0,
  results - 1)( -1 < result < 1)"* — i.e. no arguments, one scalar result, nominally -1..1. No
  units are named (a "ball position" is a normalised instrument-travel fraction, not an angle —
  unlike `LoGetAngleOfSideSlip`, whose name implies radians by this project's own established
  convention for every other `LoGet*` angle, per `2026-10-26-bl16-flight-control-desk-recon.md`
  finding 4, but this is **inferred from naming, not confirmed**). — **evidence:
  forum-claim-unverified** — **source:** WebSearch snippet of
  `forum.dcs.world/topic/226224-logetslipballposition-not-working-any-more` (title itself is the
  second warning sign, below).
- **Two threads (2020) report the call returning `nil`** for the poster's aircraft at the time —
  *"it must return a null as I cannot output the local slipball variable"*, and a second poster
  the same year, *"I don't think it is working for me either."* Old (DCS ~2020), module/version
  unstated, and not reproduced this session — but it means **this call's current reliability, let
  alone its behaviour specifically on the Mi-24P (a module that did not exist in DCS in 2020), is
  not established by anything found.** — **evidence: forum-claim-unverified, and explicitly
  stale/uncertain** — **source:** same thread, `/topic/226224`.
- **A third thread (2022) frames `LoGetSlipBallPosition` as the *only* sideslip-shaped export call
  anyone has found**, with a reply suggesting no raw slip-angle value is exposed to scripts at all
  — consistent with (but not proof of) the ball-position-not-angle reading above. — **evidence:
  forum-claim-unverified** — **source:** WebSearch snippet of
  `forum.dcs.world/topic/96066-lua-use-beta-sideslip`.
- **Both `/topic/226224` and `/topic/96066` returned HTTP 403 on direct `WebFetch` this session**
  — per project convention (`feedback_forum_403_fallback`), recorded as **unread**, not as a dead
  end. If sign/range precision matters before the probe, ask the user to open these two URLs and
  paste the content back.
- **Whether either call is actually implemented/non-nil for the Mi-24P specifically is
  unverified** — no source found tests it against this module, and the two "returns nil" reports
  are both pre-Mi-24P and not module-specific.

**(b) The cockpit draw-argument route — same pattern this project already uses for rotor RPM,
the altimeter, and the 9K113 sight angle**

- **The Mi-24P's ADI slip ball has named, numbered draw arguments in `DCS-Skunkworks/dcs-bios`**
  (`Scripts/DCS-BIOS/lib/modules/aircraft_modules/Mi-24P.lua`, fetched 2026-11-20 via raw GitHub,
  same cross-reference source class this project already leaned on for rotor RPM,
  `2026-11-19-mi24p-readable-args-recon.md` finding 1):

  | identifier | arg | seat | category | declared range |
  |---|---|---|---|---|
  | `PLT_ADI_BALL` | **943** | pilot | `"PKP72M Gauges"` | `{1, -1}` |
  | `OP_ADI_BALL` | **784** | operator | `"PKP72M Gauges"` | `{1, -1}` |

  Nearby, same device family: `PLT_ADI_PITCH_G` (939, `{-1, 1}`), `PLT_ADI_BANK_G` (942,
  `{0.5, -0.5}`), and their operator mirrors (780, 783). — **evidence: documented (third-party
  GPL-3.0 source), not reproduced-locally against this project's own installed tree** — **source:**
  `raw.githubusercontent.com/DCS-Skunkworks/dcs-bios/master/.../Mi-24P.lua` (ball/pitch/bank
  entries as quoted).
- **This project's own `mi24p-command-surface.md` independently corroborates the device family,
  not the arg**: device ids `PKP72M_P`/`PKP72M_O`/`PKP72M_INTERFACE` (32/33/34) are already
  reproduced-locally in that file (line 580-582), with sibling clickable controls on the same
  device at nearby arg/cmd numbers (`PKP-INIT-PITCH-KNOB-PTR` cmd near `PKP-TEST-PTR` cmd). The
  ball itself is a pure gauge (no click action), which is exactly the class of element this
  project's own `clickabledata.lua` generator is known to skip — **consistent with, not
  contradicted by, its absence from that file's draw-arg table** (the same generator gap already
  documented for `COLLECTIVE-CORR-PTR` and the PTT triggers). — **evidence: reproduced-locally
  (device family only) / documented (third-party, the specific arg numbers)** — **source:**
  `aircraft-layer/research/mi24p-command-surface.md:580-582`.
- **The read mechanism is already proven in this exact module for this exact call shape**:
  `GetDevice(0):get_argument_value(<n>)`, confirmed live for 874/876 (9K113 sight angle,
  `2026-10-21-dcs-bios-mi24p-9k113-controls.md`) and used identically for every `SEAT_ARGS` entry
  `flight_control.lua` already reads (pitch/roll/collective/pedal draw args 1100-1103/1110-1113).
  Adding arg 943/784 is the same call, no new Lua pattern. — **evidence: reproduced-locally (the
  mechanism) / documented (the specific arg, not yet cross-checked)**.
- **The declared range `{1, -1}` (reversed order) is the same convention DCS-BIOS uses for the
  bank gauge (`{0.5, -0.5}`) on this module** — `defineFloat`'s own semantics put the *maximum*
  cockpit-arg value first when the gauge's positive visual direction corresponds to a *decreasing*
  raw arg. This means the raw arg's sign is **not** safely assumed to match "ball right = positive
  arg" by analogy with the pitch gauge (`{-1, 1}`, not reversed) — **evidence: inferred from the
  declared-range convention, explicitly not a measured sign** — this is exactly what Reproducible
  Test below settles.
- **Not yet cross-checked locally** (no DCS install reachable this session) — same caveat already
  carried by the rotor-RPM arg numbers from the same source
  (`2026-11-19-mi24p-readable-args-recon.md` finding 1): step 1 there ("confirm arg X is real and
  calibrated, log it against the visible instrument") is the identical next step this note needs
  for arg 943/784.

**(c) Deriving sideslip from `LoGetVectorVelocity` + attitude — fallback, not recommended first**

- Feasible in principle (`beta ≈ atan2(v_body_lateral, v_body_forward)`, rotating the world-frame
  velocity vector into the body frame via `LoGetADIPitchBankYaw`'s already-confirmed-live pitch/
  bank/yaw), but **`LoGetVectorVelocity`'s return frame (world vs. body) is itself unestablished**
  — `2026-10-26-bl16-flight-control-desk-recon.md` finding 4 already flags it as one of the five
  getters "never called anywhere in this project's code" with no community source giving its
  shape. Building this fallback would mean verifying *two* unknown shapes (`LoGetVectorVelocity`'s
  frame, and the rotation math) to avoid verifying *one* (an already-identified draw arg) —
  **evidence: inferred; this route trades a cheaper problem for a more expensive one.**

### Reproducible Test

Not run this session — no DCS install reachable. The probe below is new, for whoever next has the
Windows box (same shape as the existing `SEAT_ARGS` reads `flight_control.lua` already does per
frame):

1. **Add arg 943 (pilot) and 784 (operator) to the flight-control status push**, e.g. a new
   `fc_slip_ball_raw` field on the existing 5 Hz `GET /flight_control/latest` line (`ai_pilot_wheel`'s
   own status feed is the precedent for "read one more draw arg, add one more wire field" —
   `aircraft-layer/CLAUDE.md`'s `flight_control` bullet). Read via
   `GetDevice(0):get_argument_value(943)` exactly as `SEAT_ARGS` already reads 1100-1113 — no new
   Lua pattern.
2. **Optionally, log `Export.LoGetSlipBallPosition()` once per tick alongside it** (cheap — one
   extra call, same tier as the already-confirmed `LoGetADIPitchBankYaw`) purely as a cross-check
   against the draw arg, given finding (a)'s unresolved nil-return risk; do not block the test on
   it if it comes back nil or missing.
3. **Fly straight and level, wings level, no turn.** Confirm the raw arg reads at its
   nominally-centred value (expect ≈0 for an in-range, in-order gauge; confirm what "centred"
   actually reads given the reversed-range declaration in finding (b)).
4. **Step left pedal, hold, release; step right pedal, hold, release** (same probe shape as
   `M0-B`'s pedal-axis calibration, `2026-11-18-bl16-m0-flight-axes-findings.md`) while watching
   the physical slip-ball instrument in the cockpit (screenshot or eyes-on) and logging the raw
   arg value each step. This settles, in one short flight:
   - **Sign**: does a ball displacement *right* of centre read a *larger* or *smaller* raw arg
     value than centred (the reversed-range declaration means this is not safe to assume).
   - **Scale/saturation**: does the raw arg reach ±1 at full physical ball travel, or does it clip
     earlier/later.
   - **Whether `LoGetSlipBallPosition` (if logged) tracks the same physical motion**, resolving
     whether it is a usable, simpler alternative to the draw-arg read, or genuinely nil/dead on
     this module.
5. **Report**: the raw arg trace against pedal step direction, and (if logged) the Lo-API value
   alongside it — enough for Architect/Implementer to fix `K_beta`'s sign and scale without a
   second flight.

### Possible Approaches

- **Recommended: read cockpit draw arg 943 (pilot) / 784 (operator)**, via
  `GetDevice(0):get_argument_value(n)` — reuses a mechanism already proven in this module, needs
  no dependency on an Lo-API call with a documented history of returning `nil` for at least some
  aircraft/version combinations, and sits in the same `SEAT_ARGS`-style table
  `flight_control.lua` already has. This is the fix for the module's own comment ("guessing a unit
  conversion here risks a wrong-sign pedal command") — the calibration flight above removes the
  guess.
- **Log `LoGetSlipBallPosition()` in parallel during the calibration flight, not as the primary
  source.** It costs nothing extra to call once per tick and would settle finding (a)'s "does it
  even return non-nil on this module" question for free, as a secondary confirmation of the
  draw-arg reading — but should not be the sole source given its unresolved reliability history.
- **Do not build the velocity-derived fallback (c) unless both direct routes fail live** — it
  substitutes one unverified shape for two.
- **Wire the ball value through `K_beta` only after the calibration flight's sign/scale are
  known** — the module's existing posture (omit the term rather than guess) is correct and should
  hold until this probe runs, not be relaxed speculatively.

### Unresolved

1. **Sign and scale of arg 943/784** — the one thing the calibration flight above settles; nothing
   found this session establishes it from documentation alone.
2. **Whether `Export.LoGetSlipBallPosition()`/`LoGetAngleOfSideSlip()` return non-nil on the
   Mi-24P specifically, in the current DCS version** — absent from every source checked; the two
   "returns nil" reports found are both pre-dating this module and not version-matched to
   2.9.29.27278 or later.
3. **`forum.dcs.world/topic/226224` and `/topic/96066`** — both 403'd on direct fetch this
   session, recorded as unread per project convention. If their full text matters before the
   probe (e.g. a more precise range/sign claim than the WebSearch snippet gave), ask the user to
   open them and paste the content back.
4. **`LoGetVectorVelocity`'s return frame** — unresolved from a prior session
   (`2026-10-26-bl16-flight-control-desk-recon.md`), relevant only if the fallback (c) is ever
   pursued; not needed for the recommended route.
5. **Arg 943/784 are not yet cross-checked against this project's own installed tree** — same
   open status as the rotor-RPM args from the same third-party source
   (`2026-11-19-mi24p-readable-args-recon.md`); the calibration flight above is also that
   cross-check.

## Calibration flight, 2026-11-20 (user-flown, `main`, card `docs/acceptance/2026-11-20-slip-ball-calibration-card.md`)

User's report, verbatim (columns: sim time, arg 943 pilot, arg 784 operator, `LoGetSlipBallPosition`):

> about centered
> 46.186 0.02674 0.02674 None
>
> some left pedal while maintaining about zero bank, slip ball moves to right
> 65.076 0.30279 0.30279 None
>
> some right pedal while maintaining about zero bank, slip ball moves to left
> 83.148 -0.32696 -0.32696 None
>
> full right pedal
> 101.201 -0.38382 -0.38382 None
>
> full left pedal
> 116.881 0.51377 0.51377 None
>
> Aircraft speed affects how much slip there is, it's not straightworfard function of pedal
> deflection.

**Settled (resolves Unresolved items 1, 2 and 5 above):**
- **Args 943/784 are the slip ball**, confirmed live; both seats read the same value.
- **Sign:** ball right of centre = positive raw value; left = negative. Centred reads about +0.03.
- **Scale:** full pedal moved the ball to about −0.38 (right pedal) and +0.51 (left pedal); the
  usable range is roughly ±0.5, not ±1.
- **`LoGetSlipBallPosition` returns nil on the Mi-24P**, so it is dead here; use the draw arg.
- **Centring direction:** left pedal moved the ball right and right pedal moved it left, so a ball
  right of centre is centred with more right pedal ("step on the ball"). With positive pedal
  command = right (`aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`, via
  `SIGN.pedals = -1` and arg 1103 vs yaw rate), the ball-centring term is
  `pedal_dot = +K_beta * (ball - ball_centre)`.

  **Correction, 2026-11-24** (`plans/flight-lift-vector/debug-2026-11-24.md`): "positive pedal
  command = right" was wrong. The 2026-11-24 sortie (the first flight of this exact loop, LV-0
  never implemented it) diverged with the ball running right while the pilot directly observed
  "lots of left pedal" — combined with this note's own solid finding immediately above (left pedal
  moves the ball right), that is decisive: **positive pedal command is physically LEFT.** The arg-
  1103-vs-yaw-rate correlation this note chained through was explicitly flagged as weak
  (+0.23..+0.40, hands-on-cyclic cruise, no isolated pedal test) and the chain through it was wrong.
  The ball-centring term's actual sign is `pedal_dot = -K_beta * (ball - ball_centre)`
  (`k_ball_pedal = -0.3` in `flight_profile.lua`, corrected along with the collective→pedal
  feed-forward's `rotor_dir` and the turn-coordination nudge, which shared the same assumption).

  **Correction to the correction, 2026-11-24, after the re-fly** (`plans/flight-lift-vector/
  debug-2026-11-24b.md`): the correction above is itself wrong, and the original statement stands
  — **positive pedal command = RIGHT**, and the ball-centring term is
  `pedal_dot = +K_beta * (ball - ball_centre)` (`k_ball_pedal = +0.3`). With the flip applied, the
  re-fly drove the command from −0.30 to −0.83 while the user saw heavy **left** pedal and said
  *"the pedal write is definetely reversed now, so apparently it was not before."* The "lots of
  left pedal" in the first flight was not this loop: the pedal moves left at the instant of the
  take, before the law changes its output (user, same day: *"There is an immediate pedal movement
  to left. It does not hold, what player was holding, but moves immediately."*), on all four takes
  logged that day under both sign conventions. The weak arg-1103-vs-yaw-rate correlation above was
  never the evidence for the convention; the re-fly is.
- **Not a fixed mapping:** the slip per unit of pedal depends on airspeed (user). The pedal law must
  centre the ball by feedback (integrating until centred, possibly gain-scheduled by IAS), not by a
  pedal-from-ball map. That matches the lift-vector law's "steer by observation" direction
  (`body-layer/ROADMAP/BL-16.md`).
